"""Groq translation helpers."""

from __future__ import annotations

import os
from typing import Iterable

from groq import Groq


SYSTEM_PROMPT = (
    "You are a professional multilingual translator. "
    "Preserve tone, meaning, and formatting."
)

DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"


class TranslationError(Exception):
    """Raised when translation fails."""


def get_groq_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise TranslationError(
            "GROQ_API_KEY is not set. Please configure it in your environment."
        )
    return Groq(api_key=api_key)


def chunk_text(text: str, max_chars: int = 6000) -> list[str]:
    """Chunk text into roughly model-friendly blocks.

    This uses character-based chunking as a practical approximation of
    1000-2000 token chunks for most plain-language documents.
    """
    cleaned = text.strip()
    if not cleaned:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for paragraph in cleaned.split("\n"):
        paragraph_len = len(paragraph) + 1
        if current and current_len + paragraph_len > max_chars:
            chunks.append("\n".join(current).strip())
            current = [paragraph]
            current_len = paragraph_len
        else:
            current.append(paragraph)
            current_len += paragraph_len

    if current:
        chunks.append("\n".join(current).strip())

    return [chunk for chunk in chunks if chunk]


def translate_text(text: str, target_language: str, client: Groq | None = None) -> str:
    """Translate text into the target language using the Groq Chat Completions API."""
    if not text.strip():
        return ""

    groq_client = client or get_groq_client()

    model = os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)

    try:
        response = groq_client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Translate the following text into {target_language}:\n\n{text}"
                    ),
                },
            ],
        )
        output_text = response.choices[0].message.content if response.choices else ""
    except Exception as exc:  # noqa: BLE001 - surface clean app-level error
        raise TranslationError(f"Groq translation request failed: {exc}") from exc

    if not output_text:
        raise TranslationError("Groq returned an empty translation response.")

    return output_text.strip()


def translate_chunks(
    chunks: Iterable[str], target_language: str, client: Groq | None = None
) -> str:
    """Translate a sequence of chunks and merge them."""
    translated_parts: list[str] = []
    for chunk in chunks:
        translated_parts.append(translate_text(chunk, target_language, client=client))
    return "\n\n".join(translated_parts).strip()
