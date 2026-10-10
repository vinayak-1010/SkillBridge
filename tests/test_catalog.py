"""Tests for catalog scanning, lazy loading, and skill validation."""

from __future__ import annotations

from pathlib import Path

from skillbridge.catalog import load_body, scan, validate_skill

SKILLS = Path(__file__).resolve().parents[1] / "skills"


def test_scan_finds_three_shipped_skills():
    skills = scan([SKILLS])
    names = {s.name for s in skills}
    assert {"contrib-scout", "pr-prep", "repo-onboarding"} <= names


def test_scan_reads_frontmatter_only():
    skills = scan([SKILLS])
    for s in skills:
        # Progressive disclosure: body not loaded during scan.
        assert s.body is None
        assert s.description


def test_load_body_is_lazy_and_cached():
    skills = scan([SKILLS])
    skill = next(s for s in skills if s.name == "contrib-scout")
    body = load_body(skill)
    assert "contrib-scout" in body
    assert skill.body is not None  # cached after first load


def test_shipped_skills_pass_validation():
    for name in ("contrib-scout", "pr-prep", "repo-onboarding"):
        assert validate_skill(SKILLS / name) == []


def test_validate_catches_name_mismatch(tmp_path: Path):
    d = tmp_path / "wrong-name"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: other\ndescription: x\n---\nbody\n", encoding="utf-8"
    )
    errors = validate_skill(d)
    assert any("folder name must equal" in e for e in errors)


def test_validate_catches_bad_characters(tmp_path: Path):
    d = tmp_path / "Bad_Name"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: Bad_Name\ndescription: x\n---\nbody\n", encoding="utf-8"
    )
    errors = validate_skill(d)
    assert any("lowercase letters" in e for e in errors)


def test_validate_requires_description(tmp_path: Path):
    d = tmp_path / "nodesc"
    d.mkdir()
    (d / "SKILL.md").write_text("---\nname: nodesc\n---\nbody\n", encoding="utf-8")
    errors = validate_skill(d)
    assert any("description" in e for e in errors)
