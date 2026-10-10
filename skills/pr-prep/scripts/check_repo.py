#!/usr/bin/env python3
"""Inspect a GitHub repo for contribution expectations.

Fetches (where present) CONTRIBUTING, a PR template, commit convention hints
and the test command, then prints a JSON summary to stdout.

Standalone: python check_repo.py --repo owner/repo
Also invoked by the pr-prep skill via the harness run_script tool.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"
USER_AGENT = "SkillBridge-pr-prep/0.1"

CONTRIBUTING_PATHS = [
    "CONTRIBUTING.md",
    ".github/CONTRIBUTING.md",
    "docs/CONTRIBUTING.md",
]
PR_TEMPLATE_PATHS = [
    ".github/pull_request_template.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    "docs/pull_request_template.md",
]


def _headers() -> dict:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fetch_text(url: str) -> str | None:
    try:
        req = urllib.request.Request(url, headers=_headers())
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            if resp.status != 200:
                return None
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def _fetch_json(url: str) -> dict | list | None:
    text = _fetch_text(url)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _normalize_repo(repo: str) -> str:
    repo = repo.strip().rstrip("/")
    for prefix in ("https://github.com/", "http://github.com/", "github.com/"):
        if repo.startswith(prefix):
            repo = repo[len(prefix):]
    return repo


def _default_branch(repo: str) -> str:
    data = _fetch_json(f"{API}/repos/{repo}")
    if isinstance(data, dict) and data.get("default_branch"):
        return str(data["default_branch"])
    return "main"


def _first_present(repo: str, branch: str, paths: list[str]) -> tuple[str | None, str | None]:
    for path in paths:
        text = _fetch_text(f"{RAW}/{repo}/{branch}/{path}")
        if text:
            return path, text
    return None, None


def _guess_test_command(repo: str, branch: str) -> str | None:
    # package.json scripts.test
    pkg = _fetch_text(f"{RAW}/{repo}/{branch}/package.json")
    if pkg:
        try:
            scripts = json.loads(pkg).get("scripts", {})
            if "test" in scripts:
                return f"npm test  ({scripts['test']})"
        except json.JSONDecodeError:
            pass
    # Common Python / build markers
    for marker, cmd in (
        ("pyproject.toml", "pytest"),
        ("tox.ini", "tox"),
        ("Makefile", "make test"),
        ("Cargo.toml", "cargo test"),
        ("go.mod", "go test ./..."),
    ):
        if _fetch_text(f"{RAW}/{repo}/{branch}/{marker}"):
            return cmd
    return None


def check(repo: str) -> dict:
    repo = _normalize_repo(repo)
    branch = _default_branch(repo)

    contrib_path, contrib_text = _first_present(repo, branch, CONTRIBUTING_PATHS)
    pr_path, pr_text = _first_present(repo, branch, PR_TEMPLATE_PATHS)

    commit_convention = None
    if contrib_text:
        low = contrib_text.lower()
        if "conventional commit" in low:
            commit_convention = "Conventional Commits"
        elif "sign-off" in low or "signed-off-by" in low:
            commit_convention = "Sign-off (DCO) required"

    return {
        "repo": repo,
        "default_branch": branch,
        "contributing": {
            "found": contrib_path is not None,
            "path": contrib_path,
            "url": f"https://github.com/{repo}/blob/{branch}/{contrib_path}" if contrib_path else None,
            "excerpt": (contrib_text or "")[:600] if contrib_text else None,
        },
        "pr_template": {
            "found": pr_path is not None,
            "path": pr_path,
            "excerpt": (pr_text or "")[:600] if pr_text else None,
        },
        "commit_convention": commit_convention,
        "test_command": _guess_test_command(repo, branch),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect a repo for PR expectations.")
    parser.add_argument("--repo", required=True, help="owner/repo or a GitHub URL")
    args = parser.parse_args(argv)
    print(json.dumps(check(args.repo), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
