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
        self.data[file_id] = {
            "original_text": original_text,
            "translated_text": translated_text,
            "comments": existing.get("comments", []),
            "feedback": existing.get("feedback", []),
            "assigned_team": existing.get("assigned_team", "IT"),
            "criticality": existing.get("criticality", "Medium"),
        }
        self.save()

    def update_assignment(self, file_id: str, assigned_team: str, criticality: str) -> None:
        if file_id not in self.data:
            self.data[file_id] = {
                "original_text": "",
                "translated_text": "",
                "comments": [],
                "feedback": [],
            }
        self.data[file_id]["assigned_team"] = assigned_team
        self.data[file_id]["criticality"] = criticality
        self.save()

    def add_feedback(self, file_id: str, feedback_text: str, area: str, rating: int) -> None:
        if file_id not in self.data:
            self.data[file_id] = {
                "original_text": "",
                "translated_text": "",
                "comments": [],
                "feedback": [],
            }
        self.data[file_id].setdefault("feedback", []).append(
            {
                "area": area,
                "feedback_text": feedback_text,
                "rating": rating,
            }
        )
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
                "feedback": [],
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
