"""Skill router.

The model sees only skill names and one-line descriptions (progressive
disclosure) and picks exactly one skill, with output enum-constrained to
the available names. If the model cannot decide, a BM25 lexical match over
name + description provides a deterministic fallback.
"""

from __future__ import annotations

import json

from rank_bm25 import BM25Okapi

from .backend import LLMBackend
from .catalog import Skill


def _catalog_text(skills: list[Skill]) -> str:
    return "\n".join(f"- {s.name}: {s.description}" for s in skills)


def _route_schema(skills: list[Skill]) -> dict:
    return {
        "type": "object",
        "properties": {"skill": {"type": "string", "enum": [s.name for s in skills]}},
        "required": ["skill"],
        "additionalProperties": False,
    }


def route(task: str, skills: list[Skill], backend: LLMBackend) -> Skill | None:
    """Pick one skill for the task, or None if no skills are available."""
    if not skills:
        return None
    if len(skills) == 1:
        return skills[0]

    by_name = {s.name: s for s in skills}
    messages = [
        {
            "role": "system",
            "content": (
                "Choose the single most relevant skill for the user's task.\n"
                "Respond with JSON: {\"skill\": \"<name>\"}.\n\n"
                "Available skills:\n" + _catalog_text(skills)
            ),
        },
        {"role": "user", "content": task},
    ]
    try:
        text, _tokens = backend.generate(messages, schema=_route_schema(skills), max_tokens=64)
        chosen = _parse_choice(text)
        if chosen and chosen in by_name:
            return by_name[chosen]
    except Exception:
        # Any backend failure falls through to the deterministic BM25 path.
        pass

    return bm25_fallback(task, skills)


def bm25_fallback(task: str, skills: list[Skill]) -> Skill | None:
    """Deterministic lexical routing over name + description."""
    if not skills:
        return None
    corpus = [f"{s.name} {s.description}".lower().split() for s in skills]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(task.lower().split())
    best = max(range(len(skills)), key=lambda i: scores[i])
    return skills[best]


def _parse_choice(text: str) -> str | None:
    text = text.strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and "skill" in obj:
            return str(obj["skill"]).strip()
    except json.JSONDecodeError:
        pass
    # Tolerate a bare name on its own line.
    first = text.splitlines()[0].strip().strip('"') if text else ""
    return first or None
