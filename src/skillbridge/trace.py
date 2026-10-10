"""JSONL trace logging, one line per event per run.

Keeps a durable, inspectable record of every step: the raw model output,
the parsed action, verifier results, and tool observations.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class Trace:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.events: list[dict] = []
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Truncate any prior trace at this path.
            self.path.write_text("", encoding="utf-8")

    def log(self, kind: str, **fields: Any) -> None:
        event = {"ts": round(time.time(), 3), "kind": kind, **fields}
        self.events.append(event)
        if self.path is not None:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, ensure_ascii=False) + "\n")
