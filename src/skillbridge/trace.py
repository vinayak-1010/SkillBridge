"""JSONL trace logging, one line per event per run.

Keeps a durable, inspectable record of every step: the raw model output,
the parsed action, verifier results, and tool observations.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable


class Trace:
    def __init__(
        self,
        path: Path | None = None,
        on_event: Callable[[dict], None] | None = None,
    ) -> None:
        """
        Args:
            path: optional file to append each event to, as JSONL.
            on_event: optional callback invoked synchronously with each event
                as it is logged. Used by consumers (e.g. the web API) that
                need to stream progress live instead of reading events back
                from `self.events` only after the run finishes.
        """
        self.path = path
        self.on_event = on_event
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
        if self.on_event is not None:
            self.on_event(event)
