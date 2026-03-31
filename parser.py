"""File parsing utilities for the Multilingual File Review System."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pdfplumber
from docx import Document


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


class FileParsingError(Exception):
    """Raised when file parsing fails."""


def extract_text_from_file(file_name: str, file_bytes: bytes) -> str:
    """Extract plain text from PDF, DOCX, or TXT file bytes.

    Args:
        file_name: Original filename (used for extension detection).
        file_bytes: Raw file bytes.

    Returns:
        Extracted text.

    Raises:
        FileParsingError: If the file type is unsupported or extraction fails.
    """
    ext = Path(file_name).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise FileParsingError(
            f"Unsupported file type '{ext}'. Supported types: PDF, DOCX, TXT."
        )

    try:
        if ext == ".pdf":
            return _extract_pdf(file_bytes)
        if ext == ".docx":
            return _extract_docx(file_bytes)
        return _extract_txt(file_bytes)
    except Exception as exc:  # noqa: BLE001 - return user-friendly parser errors
        raise FileParsingError(f"Failed to parse {file_name}: {exc}") from exc


def _extract_pdf(file_bytes: bytes) -> str:
    text_parts: list[str] = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts).strip()


def _extract_docx(file_bytes: bytes) -> str:
    document = Document(BytesIO(file_bytes))
    paragraphs = [paragraph.text for paragraph in document.paragraphs]
    return "\n".join(paragraphs).strip()


def _extract_txt(file_bytes: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return file_bytes.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    raise FileParsingError("Could not decode text file with supported encodings.")
