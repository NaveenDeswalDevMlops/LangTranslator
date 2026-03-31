"""Streamlit app for multilingual file review and translated comments."""

from __future__ import annotations

import base64
import difflib
import hashlib

import streamlit as st
from fpdf import FPDF

from parser import FileParsingError, extract_text_from_file
from storage import Storage
from translator import (
    TranslationError,
    chunk_text,
    get_groq_client,
    translate_chunks,
    translate_text,
)

LANGUAGES = [
    "Hindi",
    "Spanish",
    "French",
    "German",
    "Arabic",
    "Japanese",
    "Portuguese",
    "Chinese (Simplified)",
]

TEAMS = ["IT", "Finance", "Operations", "Legal", "HR", "Security"]
CRITICALITY = ["High", "Medium", "Low"]


def build_file_id(file_name: str, file_bytes: bytes) -> str:
    digest = hashlib.md5(file_bytes, usedforsecurity=False).hexdigest()[:12]
    return f"{file_name}-{digest}"


def ensure_storage() -> Storage:
    if "storage" not in st.session_state:
        st.session_state["storage"] = Storage(path="session_data.json")
    return st.session_state["storage"]


def render_pdf_view(pdf_bytes: bytes, title: str) -> None:
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    pdf_display = (
        f'<iframe src="data:application/pdf;base64,{b64}" '
        f'width="100%" height="500" type="application/pdf"></iframe>'
    )
    st.markdown(f"#### {title}")
    st.markdown(pdf_display, unsafe_allow_html=True)


def text_to_pdf_bytes(text: str) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=10)

    safe_text = text.encode("latin-1", "replace").decode("latin-1")
    for line in safe_text.splitlines() or [safe_text]:
        pdf.multi_cell(0, 5, line)

    return pdf.output(dest="S").encode("latin-1")


def render_diff(original_text: str, translated_text: str) -> None:
    st.markdown("### 3) Difference Between Original and Converted Files")
    original_lines = original_text.splitlines()
    translated_lines = translated_text.splitlines()
    html_diff = difflib.HtmlDiff(tabsize=4, wrapcolumn=90).make_table(
        original_lines,
        translated_lines,
        fromdesc="Original Extracted Text",
        todesc="Converted/Translated Text",
        context=True,
        numlines=2,
    )
    st.components.v1.html(html_diff, height=400, scrolling=True)


def main() -> None:
    st.set_page_config(page_title="Multilingual File Review System", layout="wide")
    st.title("📄 Multilingual File Review System")
    st.caption(
        "Upload and compare files, review translation output, assign ownership, "
        "and capture feedback/comments."
    )

    storage = ensure_storage()

    st.subheader("1) File Upload")
    uploaded_file = st.file_uploader("Upload PDF, DOCX, or TXT", type=["pdf", "docx", "txt"])
    target_language = st.selectbox("Target language", LANGUAGES, index=1)
    process_clicked = st.button("Process File", type="primary")

    if process_clicked:
        if not uploaded_file:
            st.error("Please upload a file before processing.")
        else:
            file_name = uploaded_file.name
            file_bytes = uploaded_file.getvalue()
            file_id = build_file_id(file_name, file_bytes)
            st.session_state["current_file_id"] = file_id
            st.session_state["uploaded_name"] = file_name
            st.session_state["uploaded_bytes"] = file_bytes

            try:
                with st.spinner("Extracting text from file..."):
                    original_text = extract_text_from_file(file_name, file_bytes)

                if not original_text.strip():
                    st.warning("No extractable text was found in this file.")
                else:
                    with st.spinner("Translating content with Groq..."):
                        client = get_groq_client()
                        chunks = chunk_text(original_text, max_chars=6000)
                        translated_text = translate_chunks(chunks, target_language, client=client)

                    storage.upsert_file(file_id, original_text, translated_text)
                    st.success("File processed successfully.")
            except (FileParsingError, TranslationError) as exc:
                st.error(str(exc))

    current_file_id = st.session_state.get("current_file_id")
    record = storage.get_file(current_file_id) if current_file_id else None

    if record:
        st.markdown("---")
        st.markdown("## 2) Uploaded PDF View (Left) and Converted PDF (Right)")
        left, right = st.columns(2)

        file_name = st.session_state.get("uploaded_name", "")
        uploaded_bytes = st.session_state.get("uploaded_bytes")

        with left:
            if file_name.lower().endswith(".pdf") and uploaded_bytes:
                render_pdf_view(uploaded_bytes, "Uploaded PDF")
            else:
                st.info("Uploaded file is not a PDF. Showing extracted source text instead.")
                st.text_area("Original text", record.get("original_text", ""), height=500)

        with right:
            converted_pdf = text_to_pdf_bytes(record.get("translated_text", ""))
            render_pdf_view(converted_pdf, "Converted (Translated) PDF")
            st.download_button(
                "Download converted PDF",
                data=converted_pdf,
                file_name="converted_translation.pdf",
                mime="application/pdf",
            )

        render_diff(record.get("original_text", ""), record.get("translated_text", ""))

        st.markdown("---")
        st.markdown("### 4) Feedback for Difference / Converted File")
        feedback_area = st.selectbox(
            "Feedback area",
            ["Difference section", "Converted file quality"],
        )
        feedback_rating = st.slider("Rating", min_value=1, max_value=5, value=3)
        feedback_text = st.text_area("Your feedback", placeholder="Share quality issues or approval notes")
        if st.button("Submit Feedback"):
            if not feedback_text.strip():
                st.warning("Feedback cannot be empty.")
            else:
                storage.add_feedback(current_file_id, feedback_text, feedback_area, feedback_rating)
                st.success("Feedback saved.")
                st.rerun()

        st.markdown("### 5) User Comments")
        comment_language = st.selectbox("Comment translation language", LANGUAGES, index=0)
        comment_text = st.text_area("Add Comment", placeholder="Write reviewer comments...")
        if st.button("Submit Comment"):
            if not comment_text.strip():
                st.warning("Comment cannot be empty.")
            else:
                try:
                    with st.spinner("Translating comment..."):
                        client = get_groq_client()
                        translated_comment = translate_text(comment_text, comment_language, client=client)
                    storage.add_comment(
                        file_id=current_file_id,
                        original_comment=comment_text,
                        translated_comment=translated_comment,
                        target_language=comment_language,
                    )
                    st.success("Comment added.")
                    st.rerun()
                except TranslationError as exc:
                    st.error(str(exc))

        st.markdown("### 6) Assignment to Team")
        assigned_team = st.selectbox("Assign to team", TEAMS)

        st.markdown("### 7) Criticality of File Update")
        criticality = st.selectbox("Criticality", CRITICALITY, index=1)
        if st.button("Save Assignment & Criticality"):
            storage.update_assignment(current_file_id, assigned_team, criticality)
            st.success("Assignment and criticality saved.")
            st.rerun()

        latest = storage.get_file(current_file_id) or {}
        st.markdown("#### Current Assignment")
        st.write(f"Team: **{latest.get('assigned_team', 'IT')}**")
        st.write(f"Criticality: **{latest.get('criticality', 'Medium')}**")

        st.markdown("#### Saved Feedback")
        feedback_items = latest.get("feedback", [])
        if not feedback_items:
            st.info("No feedback yet.")
        else:
            for idx, item in enumerate(feedback_items, 1):
                st.write(
                    f"{idx}. [{item.get('area')}] Rating {item.get('rating')}/5 - "
                    f"{item.get('feedback_text')}"
                )

        st.markdown("#### Saved Comments")
        comments = latest.get("comments", [])
        if not comments:
            st.info("No comments yet.")
        else:
            for idx, comment in enumerate(comments, 1):
                st.write(
                    f"{idx}. Original: {comment.get('original_comment', '')}"
                    f" | Translated ({comment.get('target_language', 'N/A')}): "
                    f"{comment.get('translated_comment', '')}"
                )


if __name__ == "__main__":
    main()
