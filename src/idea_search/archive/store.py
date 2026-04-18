"""JSONL archive. Human-readable append-only store."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, Optional

from idea_search.schema import Idea, Evaluation


class ArchiveStore:
    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, idea: Idea, evaluation: Evaluation | None = None, session: str | None = None) -> None:
        record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "session": session,
            "idea": idea.model_dump(),
            "evaluation": evaluation.model_dump() if evaluation else None,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def append_many(self, records: Iterable[tuple[Idea, Evaluation | None]], session: str | None = None) -> None:
        for idea, ev in records:
            self.append(idea, ev, session=session)

    def clear(self) -> None:
        """Remove all records from the archive.

        Creates the parent directory if missing and leaves an empty
        (0-byte) file at ``self.path``. Useful for test isolation and
        manual resets.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")

    def iter_records(self, session: Optional[str] = None) -> Iterator[dict]:
        """Yield records. If ``session`` is given, filter to that session only."""
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if session is not None and rec.get("session") != session:
                    continue
                yield rec

    def iter_idea_texts(
        self, session: Optional[str] = None
    ) -> Iterator[tuple[str, str]]:
        """Yield (idea_id, text) for similarity comparisons.

        If ``session`` is given, only records from that session are yielded.
        """
        for rec in self.iter_records(session=session):
            idea = rec.get("idea") or {}
            iid = idea.get("id")
            title = idea.get("title", "")
            statement = idea.get("statement", "")
            if iid:
                yield iid, f"{title}. {statement}"
