"""Storage helpers for in-session and optional JSON persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Storage:
    """Simple JSON-backed storage for file reviews."""

    def __init__(self, path: str = "session_data.json") -> None:
        self.path = Path(path)
        self.data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self.data = {}
            return

        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self.data = {}

    def save(self) -> None:
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def upsert_file(self, file_id: str, original_text: str, translated_text: str) -> None:
        existing = self.data.get(file_id, {})
        comments = existing.get("comments", [])
        self.data[file_id] = {
            "original_text": original_text,
            "translated_text": translated_text,
            "comments": comments,
        }
        self.save()

    def add_comment(
        self,
        file_id: str,
        original_comment: str,
        translated_comment: str,
        target_language: str,
    ) -> None:
        if file_id not in self.data:
            self.data[file_id] = {
                "original_text": "",
                "translated_text": "",
                "comments": [],
            }

        self.data[file_id].setdefault("comments", []).append(
            {
                "original_comment": original_comment,
                "translated_comment": translated_comment,
                "target_language": target_language,
            }
        )
        self.save()

    def get_file(self, file_id: str) -> dict[str, Any] | None:
        return self.data.get(file_id)
