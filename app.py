"""Streamlit app for multilingual file review and translated comments.

UI/UX layer refreshed for enterprise-grade usability while preserving core logic.
"""

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


# ----------------------------
# Core helpers (unchanged behavior)
# ----------------------------

def build_file_id(file_name: str, file_bytes: bytes) -> str:
    digest = hashlib.md5(file_bytes, usedforsecurity=False).hexdigest()[:12]
    return f"{file_name}-{digest}"


def ensure_storage() -> Storage:
    if "storage" not in st.session_state:
        st.session_state["storage"] = Storage(path="session_data.json")
    return st.session_state["storage"]


def init_session_state() -> None:
    """Initialize session keys so UI interactions don't reprocess data."""
    defaults = {
        "current_file_id": None,
        "uploaded_name": "",
        "uploaded_bytes": None,
        "file_target_language": {},
        "demo_mode": False,
        "is_authenticated": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def render_pdf_view(pdf_bytes: bytes, title: str) -> None:
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    pdf_display = (
        f'<iframe src="data:application/pdf;base64,{b64}" '
        f'width="100%" height="500" type="application/pdf"></iframe>'
    )
    st.markdown(f"#### {title}")
    st.markdown(pdf_display, unsafe_allow_html=True)


def text_to_pdf_bytes(text: str) -> bytes:
    def _split_line_to_fit(pdf_doc: FPDF, raw_line: str, max_width: float) -> list[str]:
        """Split a line into chunks that fit the target width."""
        if not raw_line:
            return [""]

        parts: list[str] = []
        start = 0
        while start < len(raw_line):
            end = start + 1
            while end <= len(raw_line) and pdf_doc.get_string_width(raw_line[start:end]) <= max_width:
                end += 1
            parts.append(raw_line[start : end - 1])
            start = end - 1
        return parts

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=10)

    available_width = max(pdf.epw, 1)
    safe_text = text.encode("latin-1", "replace").decode("latin-1")
    for line in safe_text.splitlines() or [safe_text]:
        pdf.multi_cell(0, 5, line)
        wrapped_lines = _split_line_to_fit(pdf, line, available_width)
        for wrapped_line in wrapped_lines:
            pdf.set_x(pdf.l_margin)
            pdf.cell(available_width, 5, wrapped_line, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output(dest="S"))


def render_diff(original_text: str, translated_text: str) -> None:
    st.markdown("### Difference Between Original and Converted Files")
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


# ----------------------------
# UI helpers
# ----------------------------

def inject_global_styles() -> None:
    """Provide card-like sections and chat-style comments."""
    st.markdown(
        """
        <style>
        .app-card {
            background: #f7f9fc;
            border: 1px solid #e7ecf3;
            border-radius: 14px;
            padding: 1rem 1.2rem;
            margin-bottom: 1rem;
        }
        .header-wrap {
            text-align: center;
            padding: 0.5rem 0 1rem;
            border-bottom: 1px solid #e9edf5;
            margin-bottom: 1rem;
        }
        .header-title {
            font-size: 2rem;
            font-weight: 700;
            color: #0f2747;
            margin: 0;
        }
        .header-subtitle {
            color: #4f5f73;
            margin-top: 0.2rem;
        }
        .chat-bubble {
            background: #ffffff;
            border-left: 4px solid #2f6cf6;
            border-radius: 10px;
            padding: 0.9rem;
            margin: 0.7rem 0;
            box-shadow: 0 1px 2px rgba(0,0,0,0.04);
        }
        .footer {
            text-align: center;
            color: #6b7280;
            margin-top: 2rem;
            padding-top: 0.8rem;
            border-top: 1px solid #e5e7eb;
            font-size: 0.85rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.markdown(
        """
        <div class="header-wrap">
          <h1 class="header-title">Multilingual Review System</h1>
          <div class="header-subtitle">Powered by GenAI</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def card_open(title: str) -> None:
    st.markdown(f'<div class="app-card"><h4>{title}</h4>', unsafe_allow_html=True)


def card_close() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def render_comments_chat(comments: list[dict]) -> None:
    if not comments:
        st.info("No comments yet.")
        return

    for idx, comment in enumerate(comments, 1):
        st.markdown(
            f"""
            <div class="chat-bubble">
                <strong>Comment {idx}</strong><br/>
                <div><b>Original:</b> {comment.get('original_comment', '')}</div>
                <div><b>Translated ({comment.get('target_language', 'N/A')}):</b>
                    {comment.get('translated_comment', '')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_dashboard(storage: Storage) -> None:
    data = storage.data
    files_processed = len(data)
    comments_count = sum(len(item.get("comments", [])) for item in data.values())
    language_set = {
        comment.get("target_language")
        for item in data.values()
        for comment in item.get("comments", [])
        if comment.get("target_language")
    }

    st.subheader("Operations Dashboard")
    m1, m2, m3 = st.columns(3)
    m1.metric("Files Processed", files_processed)
    m2.metric("Comments Logged", comments_count)
    m3.metric("Languages Used", len(language_set))

    if language_set:
        st.caption("Languages observed in comments: " + ", ".join(sorted(language_set)))


def process_uploaded_file(storage: Storage, uploaded_file, target_language: str) -> None:
    """Extract + translate once, then persist in session state/storage."""
    file_name = uploaded_file.name
    file_bytes = uploaded_file.getvalue()
    file_id = build_file_id(file_name, file_bytes)

    st.session_state["current_file_id"] = file_id
    st.session_state["uploaded_name"] = file_name
    st.session_state["uploaded_bytes"] = file_bytes
    st.session_state["file_target_language"][file_id] = target_language

    progress = st.progress(0)

    try:
        if len(file_bytes) > 5 * 1024 * 1024:
            st.warning("Large file detected (>5MB). Processing may take longer.")

        with st.spinner("Processing file and extracting text..."):
            progress.progress(20)
            original_text = extract_text_from_file(file_name, file_bytes)

        if not original_text.strip():
            progress.progress(100)
            st.warning("No extractable text was found in this file.")
            return

        with st.spinner("Translating text..."):
            progress.progress(65)
            client = get_groq_client()
            chunks = chunk_text(original_text, max_chars=6000)
            translated_text = translate_chunks(chunks, target_language, client=client)

        storage.upsert_file(file_id, original_text, translated_text)
        progress.progress(100)
        st.success("File processed successfully.")
    except (FileParsingError, TranslationError) as exc:
        st.error(str(exc))


def render_upload_translate_page(storage: Storage) -> None:
    tabs = st.tabs(["Upload", "Translation Output", "Comments"])

    with tabs[0]:
        card_open("Upload and Translate")
        uploaded_file = st.file_uploader("Upload PDF, DOCX, or TXT", type=["pdf", "docx", "txt"])
        target_language = st.selectbox("Target language", LANGUAGES, index=1)

        # Centered action button via columns for better visual balance.
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            process_clicked = st.button("Process File", type="primary", use_container_width=True)

        if process_clicked:
            if not uploaded_file:
                st.error("Please upload a file before processing.")
            else:
                process_uploaded_file(storage, uploaded_file, target_language)
        card_close()

    current_file_id = st.session_state.get("current_file_id")
    record = storage.get_file(current_file_id) if current_file_id else None

    with tabs[1]:
        card_open("Translation Output")
        if not record:
            st.info("Process a file to view translated output.")
            card_close()
        else:
            col_left, col_right = st.columns(2)
            file_name = st.session_state.get("uploaded_name", "")
            uploaded_bytes = st.session_state.get("uploaded_bytes")

            # 2-column enterprise review layout: original vs translated.
            with col_left:
                if file_name.lower().endswith(".pdf") and uploaded_bytes:
                    render_pdf_view(uploaded_bytes, "Original File")
                else:
                    st.text_area("Original text", record.get("original_text", ""), height=420)

            with col_right:
                translated_text = record.get("translated_text", "")
                translated_pdf = text_to_pdf_bytes(translated_text)
                render_pdf_view(translated_pdf, "Translated Output")
                st.download_button(
                    "Download translated PDF",
                    data=translated_pdf,
                    file_name="translated_output.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
                st.download_button(
                    "Download translated text (.txt)",
                    data=translated_text,
                    file_name="translated_output.txt",
                    mime="text/plain",
                    use_container_width=True,
                )

            render_diff(record.get("original_text", ""), record.get("translated_text", ""))
            card_close()

    with tabs[2]:
        render_review_comments_page(storage, compact=True)


def render_review_comments_page(storage: Storage, compact: bool = False) -> None:
    current_file_id = st.session_state.get("current_file_id")
    record = storage.get_file(current_file_id) if current_file_id else None

    if not record:
        st.info("Upload and process a file first.")
        return

    if not compact:
        st.subheader("Review & Comments")

    card_open("Feedback")
    feedback_area = st.selectbox(
        "Feedback area",
        ["Difference section", "Converted file quality"],
        key="feedback_area_select_compact" if compact else "feedback_area_select",
    )
    feedback_rating = st.slider(
        "Rating",
        min_value=1,
        max_value=5,
        value=3,
        key="feedback_rating_compact" if compact else "feedback_rating",
    )
    feedback_text = st.text_area(
        "Your feedback",
        placeholder="Share quality issues or approval notes",
        key="feedback_text_compact" if compact else "feedback_text",
    )
    if st.button("Submit Feedback", key="submit_feedback_compact" if compact else "submit_feedback"):
        if not feedback_text.strip():
            st.warning("Feedback cannot be empty.")
        else:
            storage.add_feedback(current_file_id, feedback_text, feedback_area, feedback_rating)
            st.success("Feedback saved.")
            st.rerun()
    card_close()

    card_open("Comments")
    comment_language = st.selectbox(
        "Comment translation language",
        LANGUAGES,
        index=0,
        key="comment_language_compact" if compact else "comment_language",
    )
    comment_text = st.text_area(
        "Add Comment",
        placeholder="Write reviewer comments...",
        key="comment_text_compact" if compact else "comment_text",
    )
    if st.button("Submit Comment", key="submit_comment_compact" if compact else "submit_comment"):
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

    st.markdown("##### Saved Comments")
    render_comments_chat(record.get("comments", []))
    card_close()

    card_open("Assignment")
    assigned_team = st.selectbox("Assign to team", TEAMS, key="team_compact" if compact else "team")
    criticality = st.selectbox(
        "Criticality",
        CRITICALITY,
        index=1,
        key="criticality_compact" if compact else "criticality",
    )
    if st.button(
        "Save Assignment & Criticality",
        key="save_assignment_compact" if compact else "save_assignment",
    ):
        storage.update_assignment(current_file_id, assigned_team, criticality)
        st.success("Assignment and criticality saved.")
        st.rerun()

    latest = storage.get_file(current_file_id) or {}
    st.write(f"Team: **{latest.get('assigned_team', 'IT')}**")
    st.write(f"Criticality: **{latest.get('criticality', 'Medium')}**")

    st.markdown("##### Saved Feedback")
    feedback_items = latest.get("feedback", [])
    if not feedback_items:
        st.info("No feedback yet.")
    else:
        for idx, item in enumerate(feedback_items, 1):
            st.write(
                f"{idx}. [{item.get('area')}] Rating {item.get('rating')}/5 - "
                f"{item.get('feedback_text')}"
            )
    card_close()


def render_footer() -> None:
    st.markdown(
        '<div class="footer">© 2026 Your Company Name | GenAI POC | Confidential</div>',
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="Multilingual Review System", layout="wide")

    init_session_state()
    inject_global_styles()
    render_header()
    storage = ensure_storage()

    # Sidebar navigation and lightweight optional enhancements.
    st.sidebar.title("📁 Navigation")
    menu = st.sidebar.radio(
        "Go to",
        ["Upload & Translate", "Review & Comments", "Dashboard"],
    )
    st.sidebar.toggle("Demo Mode", key="demo_mode")

    with st.sidebar.expander("Optional Login"):
        password = st.text_input("Enter password", type="password", key="login_password")
        if st.button("Login"):
            if password == "admin123":
                st.session_state["is_authenticated"] = True
                st.success("Logged in.")
            else:
                st.error("Invalid password.")

    if menu == "Upload & Translate":
        render_upload_translate_page(storage)
    elif menu == "Review & Comments":
        render_review_comments_page(storage)
    else:
        render_dashboard(storage)

    render_footer()


if __name__ == "__main__":
    main()
