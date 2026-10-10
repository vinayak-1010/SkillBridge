"""Loop and router tests using the offline EchoBackend (no Ollama needed)."""

from __future__ import annotations

import json
from pathlib import Path

from skillbridge.backend import EchoBackend
from skillbridge.catalog import scan
from skillbridge.loop import run
from skillbridge.router import bm25_fallback, route

SKILLS = Path(__file__).resolve().parents[1] / "skills"


def test_loop_finishes_on_finish_action(tmp_path: Path):
    skill = scan([SKILLS])[0]
    backend = EchoBackend([json.dumps({"tool": "finish", "args": {"answer": "done"}})])
    result = run("do something", skill, backend, read_roots=[tmp_path])
    assert result.finished
    assert result.answer == "done"
    assert result.steps == 1


def test_loop_runs_tool_then_finishes(tmp_path: Path):
    (tmp_path / "note.txt").write_text("file contents here", encoding="utf-8")
    skill = scan([SKILLS])[0]
    backend = EchoBackend(
        [
            json.dumps({"tool": "read_file", "args": {"path": "note.txt"}}),
            json.dumps({"tool": "finish", "args": {"answer": "read it"}}),
        ]
    )
    result = run("read the note", skill, backend, read_roots=[tmp_path])
    assert result.finished
    assert result.steps == 2
    kinds = [e["kind"] for e in result.trace_events]
    assert "observation" in kinds


def test_loop_retries_on_invalid_then_valid(tmp_path: Path):
    skill = scan([SKILLS])[0]
    backend = EchoBackend(
        [
            "not json at all",  # attempt 0 -> parse hint
            json.dumps({"tool": "finish", "args": {"answer": "recovered"}}),  # attempt 1
        ]
    )
    result = run("task", skill, backend, read_roots=[tmp_path])
    assert result.finished
    assert result.answer == "recovered"


def test_loop_respects_max_steps(tmp_path: Path):
    skill = scan([SKILLS])[0]
    # Always ask to list_dir, never finish.
    responses = [json.dumps({"tool": "list_dir", "args": {"path": "."}})] * 20
    backend = EchoBackend(responses)
    result = run("loop forever", skill, backend, max_steps=3, read_roots=[tmp_path])
    assert not result.finished
    assert result.steps == 3
    assert result.partial


def test_router_single_skill_shortcut():
    skills = scan([SKILLS])[:1]
    backend = EchoBackend([])
    assert route("anything", skills, backend) is skills[0]


def test_bm25_fallback_picks_relevant_skill():
    skills = scan([SKILLS])
    chosen = bm25_fallback("find beginner good first issues to contribute", skills)
    assert chosen.name == "contrib-scout"


def test_router_uses_model_choice():
    skills = scan([SKILLS])
    backend = EchoBackend([json.dumps({"skill": "repo-onboarding"})])
    chosen = route("map this repo for me", skills, backend)
    assert chosen.name == "repo-onboarding"
