"""Sandbox tests: path escape, URL allowlist, script confinement."""

from __future__ import annotations

from pathlib import Path

import pytest

from skillbridge.tools import (
    SandboxError,
    SandboxPolicy,
    ToolError,
    list_dir,
    read_file,
    run_script,
)
from skillbridge.tools import http_get  # noqa: F401 (imported for completeness)


def _policy(root: Path, skill_dir: Path | None = None) -> SandboxPolicy:
    return SandboxPolicy(read_roots=[root], skill_dir=skill_dir)


def test_read_file_within_root(tmp_path: Path):
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    out = read_file({"path": "a.txt"}, _policy(tmp_path))
    assert out == "hello"


def test_read_file_path_escape_blocked(tmp_path: Path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (tmp_path / "secret.txt").write_text("nope", encoding="utf-8")
    policy = _policy(sub)
    with pytest.raises(SandboxError):
        read_file({"path": "../secret.txt"}, policy)


def test_read_file_absolute_escape_blocked(tmp_path: Path):
    sub = tmp_path / "sub"
    sub.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("nope", encoding="utf-8")
    with pytest.raises(SandboxError):
        read_file({"path": str(outside)}, _policy(sub))


def test_list_dir_within_root(tmp_path: Path):
    (tmp_path / "x").mkdir()
    (tmp_path / "y.txt").write_text("", encoding="utf-8")
    out = list_dir({"path": "."}, _policy(tmp_path))
    assert "x/" in out
    assert "y.txt" in out


def test_http_get_rejects_disallowed_host():
    policy = SandboxPolicy(read_roots=[Path(".")])
    with pytest.raises(SandboxError):
        policy.check_url("https://evil.example.com/data")


def test_http_get_allows_github_hosts():
    policy = SandboxPolicy(read_roots=[Path(".")])
    # Should not raise for allowlisted hosts.
    policy.check_url("https://api.github.com/repos/x/y")
    policy.check_url("https://raw.githubusercontent.com/x/y/main/README.md")


def test_run_script_confined_to_scripts_folder(tmp_path: Path):
    skill = tmp_path / "myskill"
    (skill / "scripts").mkdir(parents=True)
    # A script outside scripts/ must be blocked even if it exists.
    evil = tmp_path / "evil.py"
    evil.write_text("print('x')", encoding="utf-8")
    policy = _policy(tmp_path, skill_dir=skill)
    with pytest.raises(SandboxError):
        run_script({"script": "../evil.py"}, policy)


def test_run_script_executes_allowed_script(tmp_path: Path):
    skill = tmp_path / "myskill"
    scripts = skill / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "hello.py").write_text("print('hi from script')", encoding="utf-8")
    policy = _policy(tmp_path, skill_dir=skill)
    out = run_script({"script": "hello.py"}, policy)
    assert "hi from script" in out


def test_run_script_timeout(tmp_path: Path):
    skill = tmp_path / "myskill"
    scripts = skill / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "slow.py").write_text("import time; time.sleep(5)", encoding="utf-8")
    policy = SandboxPolicy(read_roots=[tmp_path], skill_dir=skill, script_timeout=1)
    with pytest.raises(ToolError):
        run_script({"script": "slow.py"}, policy)
