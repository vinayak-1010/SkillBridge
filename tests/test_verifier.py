"""Tests for action parsing and verification."""

from __future__ import annotations

from skillbridge.verifier import parse_action, verify


def test_parse_clean_json():
    action, hint = parse_action('{"tool": "finish", "args": {"answer": "ok"}}')
    assert hint is None
    assert action == {"tool": "finish", "args": {"answer": "ok"}}


def test_parse_json_with_surrounding_prose():
    text = 'Here is my action: {"tool": "list_dir", "args": {"path": "."}} done.'
    action, hint = parse_action(text)
    assert hint is None
    assert action["tool"] == "list_dir"


def test_parse_non_json_returns_hint():
    action, hint = parse_action("I will list the directory now.")
    assert action is None
    assert hint


def test_verify_accepts_valid_finish():
    assert verify({"tool": "finish", "args": {"answer": "x"}}) is None


def test_verify_rejects_unknown_tool():
    hint = verify({"tool": "delete_everything", "args": {}})
    assert hint and "Unknown tool" in hint


def test_verify_rejects_missing_required_arg():
    hint = verify({"tool": "read_file", "args": {}})
    assert hint and "path" in hint


def test_verify_rejects_non_object_args():
    hint = verify({"tool": "finish", "args": "oops"})
    assert hint and "args" in hint
