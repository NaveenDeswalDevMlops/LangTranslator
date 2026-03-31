"""Streamlit app for multilingual file review and translated comments."""

from __future__ import annotations

import hashlib

import streamlit as st

from parser import FileParsingError, extract_text_from_file
from storage import Storage
from translator import (
    TranslationError,
    chunk_text,
    get_openai_client,
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


def build_file_id(file_name: str, file_bytes: bytes) -> str:
    digest = hashlib.md5(file_bytes, usedforsecurity=False).hexdigest()[:12]
    return f"{file_name}-{digest}"


def ensure_storage() -> Storage:
    if "storage" not in st.session_state:
        st.session_state["storage"] = Storage(path="session_data.json")
    return st.session_state["storage"]


def main() -> None:
    st.set_page_config(page_title="Multilingual File Review System", layout="wide")
    st.title("📄 Multilingual File Review System")
    st.caption("Upload a file, translate it, review side-by-side, and add multilingual comments.")

    storage = ensure_storage()

    st.subheader("1) File Upload")
    uploaded_file = st.file_uploader("Upload PDF, DOCX, or TXT", type=["pdf", "docx", "txt"])
    target_language = st.selectbox("Target language", LANGUAGES, index=1)

    process_clicked = st.button("Process File", type="primary", use_container_width=False)

    if process_clicked:
        if not uploaded_file:
            st.error("Please upload a file before processing.")
        else:
            file_name = uploaded_file.name
            file_bytes = uploaded_file.getvalue()
            file_id = build_file_id(file_name, file_bytes)
            st.session_state["current_file_id"] = file_id

            try:
                with st.spinner("Extracting text from file..."):
                    original_text = extract_text_from_file(file_name, file_bytes)

                if not original_text.strip():
                    st.warning("No extractable text was found in this file.")
                else:
                    with st.spinner("Translating content with OpenAI..."):
                        client = get_openai_client()
                        chunks = chunk_text(original_text, max_chars=6000)
                        translated_text = translate_chunks(chunks, target_language, client=client)

                    storage.upsert_file(file_id, original_text, translated_text)
                    st.success("File processed successfully.")
            except FileParsingError as exc:
                st.error(str(exc))
            except TranslationError as exc:
                st.error(str(exc))

    current_file_id = st.session_state.get("current_file_id")
    file_record = storage.get_file(current_file_id) if current_file_id else None

    if file_record:
        st.subheader("2) Review")
        left, right = st.columns(2)
        with left:
            st.markdown("#### Original Text")
            st.text_area(
                "Original text view",
                value=file_record.get("original_text", ""),
                height=350,
                disabled=True,
                label_visibility="collapsed",
            )

        with right:
            st.markdown("#### Translated Text")
            translated_value = file_record.get("translated_text", "")
            st.text_area(
                "Translated text view",
                value=translated_value,
                height=350,
                disabled=True,
                label_visibility="collapsed",
            )
            st.download_button(
                "Download translated text",
                data=translated_value.encode("utf-8"),
                file_name="translated_output.txt",
                mime="text/plain",
            )

        st.subheader("3) Comments")
        comment_language = st.selectbox("Comment translation language", LANGUAGES, index=0)
        comment_text = st.text_area("Add Comment", placeholder="Write your review comment...")

        if st.button("Submit Comment"):
            if not comment_text.strip():
                st.warning("Comment cannot be empty.")
            else:
                try:
                    with st.spinner("Translating comment..."):
                        client = get_openai_client()
                        translated_comment = translate_text(
                            comment_text, comment_language, client=client
                        )
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

        st.markdown("#### Saved Comments")
        comments = file_record.get("comments", [])
        if not comments:
            st.info("No comments yet.")
        else:
            for idx, comment in enumerate(comments, start=1):
                st.markdown(f"**Comment {idx}**")
                st.write(f"Original: {comment.get('original_comment', '')}")
                st.write(
                    f"Translated ({comment.get('target_language', 'N/A')}): "
                    f"{comment.get('translated_comment', '')}"
                )
                st.divider()


if __name__ == "__main__":
    main()
