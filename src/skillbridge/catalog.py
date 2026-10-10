"""Skill catalog: scan skill folders and load bodies lazily.

Implements the Agent Skills standard discovery:
- a skill is a folder containing SKILL.md
- SKILL.md starts with a YAML frontmatter block delimited by `---`
- the frontmatter must carry `name` and `description`

Progressive disclosure: `scan` reads only the frontmatter so the router
sees roughly one line per skill. The full Markdown body is read on demand
by `load_body`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

# Agent Skills standard constraints.
NAME_RE = re.compile(r"^[a-z0-9-]+$")
MAX_NAME_LEN = 64
MAX_DESCRIPTION_LEN = 1024
MAX_BODY_LINES = 500

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)


@dataclass
class Skill:
    name: str
    description: str
    path: Path
    body: str | None = None
    # Extra frontmatter kept for validation / activation.
    license: str | None = None
    compatibility: str | None = None
    allowed_tools: list[str] | None = None


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body) from a SKILL.md string.

    Raises ValueError if there is no valid frontmatter block.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("SKILL.md must begin with a YAML frontmatter block delimited by '---'")
    raw, body = match.group(1), match.group(2)
    data = yaml.safe_load(raw) or {}
    if not isinstance(data, dict):
        raise ValueError("SKILL.md frontmatter must be a YAML mapping")
    return data, body


def _skill_from_dir(skill_dir: Path) -> Skill:
    """Build a Skill from a folder, reading frontmatter only (no body)."""
    md = skill_dir / "SKILL.md"
    text = md.read_text(encoding="utf-8")
    data, _body = _split_frontmatter(text)
    name = str(data.get("name", "")).strip()
    description = str(data.get("description", "")).strip()
    allowed = data.get("allowed-tools")
    if isinstance(allowed, str):
        allowed = [t.strip() for t in allowed.split(",") if t.strip()]
    return Skill(
        name=name,
        description=description,
        path=skill_dir,
        body=None,
        license=data.get("license"),
        compatibility=data.get("compatibility"),
        allowed_tools=allowed,
    )


def scan(dirs: list[Path]) -> list[Skill]:
    """Scan the given directories for skill folders (frontmatter only).

    A skill folder is any immediate subdirectory containing SKILL.md.
    Skills whose SKILL.md cannot be parsed are skipped silently here;
    use `validate` to surface those errors.
    """
    skills: list[Skill] = []
    seen: set[str] = set()
    for d in dirs:
        if not d.exists():
            continue
        for child in sorted(d.iterdir()):
            if not child.is_dir():
                continue
            if not (child / "SKILL.md").exists():
                continue
            try:
                skill = _skill_from_dir(child)
            except (ValueError, yaml.YAMLError, OSError):
                continue
            if skill.name and skill.name not in seen:
                seen.add(skill.name)
                skills.append(skill)
    return skills


def load_body(skill: Skill) -> str:
    """Lazily load and cache the Markdown body of a skill."""
    if skill.body is not None:
        return skill.body
    text = (skill.path / "SKILL.md").read_text(encoding="utf-8")
    _data, body = _split_frontmatter(text)
    skill.body = body.strip()
    return skill.body


def validate_skill(skill_dir: Path) -> list[str]:
    """Validate one skill folder against the Agent Skills standard.

    Returns a list of human-readable error strings; empty means valid.
    """
    errors: list[str] = []
    folder_name = skill_dir.name
    md = skill_dir / "SKILL.md"
    if not md.exists():
        return [f"{folder_name}: missing SKILL.md"]

    try:
        text = md.read_text(encoding="utf-8")
        data, body = _split_frontmatter(text)
    except (ValueError, yaml.YAMLError) as exc:
        return [f"{folder_name}: {exc}"]

    name = str(data.get("name", "")).strip()
    description = str(data.get("description", "")).strip()

    if not name:
        errors.append(f"{folder_name}: frontmatter missing 'name'")
    else:
        if name != folder_name:
            errors.append(f"{folder_name}: folder name must equal name field '{name}'")
        if len(name) > MAX_NAME_LEN:
            errors.append(f"{folder_name}: name exceeds {MAX_NAME_LEN} characters")
        if not NAME_RE.match(name):
            errors.append(f"{folder_name}: name must be lowercase letters, digits and hyphens")

    if not description:
        errors.append(f"{folder_name}: frontmatter missing 'description'")
    elif len(description) > MAX_DESCRIPTION_LEN:
        errors.append(f"{folder_name}: description exceeds {MAX_DESCRIPTION_LEN} characters")

    body_lines = body.strip().splitlines()
    if len(body_lines) > MAX_BODY_LINES:
        errors.append(
            f"{folder_name}: body has {len(body_lines)} lines, exceeds {MAX_BODY_LINES}"
        )

    return errors


def validate_all(dirs: list[Path]) -> dict[str, list[str]]:
    """Validate every skill folder found under the given dirs.

    Returns a mapping of folder name -> list of errors (empty list = valid).
    """
    results: dict[str, list[str]] = {}
    for d in dirs:
        if not d.exists():
            continue
        for child in sorted(d.iterdir()):
            if child.is_dir() and (child / "SKILL.md").exists():
                results[child.name] = validate_skill(child)
    return results
