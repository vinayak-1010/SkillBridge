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
import urllib.request
from concurrent.futures import ThreadPoolExecutor

API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"
USER_AGENT = "SkillBridge-pr-prep/0.1"

# Per-request timeout for raw.githubusercontent.com fetches. Multiple
# candidate paths are checked concurrently (see _first_present_concurrent and
# _guess_test_command) so total wall time stays close to this single-request
# timeout rather than the sum of every candidate, keeping the script inside
# the harness's 10s sandbox cap.
RAW_FETCH_TIMEOUT = 4

CONTRIBUTING_PATHS = [
    "CONTRIBUTING.md",
    "CONTRIBUTING.rst",
    ".github/CONTRIBUTING.md",
    ".github/CONTRIBUTING.rst",
    "docs/CONTRIBUTING.md",
    "docs/CONTRIBUTING.rst",
]
PR_TEMPLATE_PATHS = [
    ".github/pull_request_template.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/pull_request_template.rst",
    "docs/pull_request_template.md",
]
TEST_MARKERS = [
    ("pyproject.toml", "pytest"),
    ("tox.ini", "tox"),
    ("Makefile", "make test"),
    ("Cargo.toml", "cargo test"),
    ("go.mod", "go test ./..."),
]


def _headers() -> dict:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fetch_text(url: str, timeout: int = RAW_FETCH_TIMEOUT) -> str | None:
    try:
        req = urllib.request.Request(url, headers=_headers())
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
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
    # A single metadata call to api.github.com; give it a little more
    # headroom than the bulk raw-file probes below.
    data = _fetch_json(f"{API}/repos/{repo}", timeout=8)
    if isinstance(data, dict) and data.get("default_branch"):
        return str(data["default_branch"])
    return "main"


def _fetch_json(url: str, timeout: int = RAW_FETCH_TIMEOUT) -> dict | list | None:
    text = _fetch_text(url, timeout=timeout)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _fetch_all(repo: str, branch: str, paths: list[str]) -> dict[str, str | None]:
    """Fetch every candidate path concurrently; returns {path: content|None}.

    Fetching candidates in parallel instead of one-after-another keeps the
    total wall time close to a single request's timeout, which is what lets
    this script finish inside the harness's 10s sandbox cap even when
    several candidate paths must be probed.
    """
    with ThreadPoolExecutor(max_workers=max(1, len(paths))) as pool:
        futures = {
            pool.submit(_fetch_text, f"{RAW}/{repo}/{branch}/{p}"): p for p in paths
        }
        return {futures[f]: f.result() for f in futures}


def _first_present(repo: str, branch: str, paths: list[str]) -> tuple[str | None, str | None]:
    results = _fetch_all(repo, branch, paths)
    for path in paths:  # preserve priority order among candidates that exist
        if results.get(path):
            return path, results[path]
    return None, None


def check(repo: str) -> dict:
    repo = _normalize_repo(repo)
    branch = _default_branch(repo)

    contrib_path, contrib_text = _first_present(repo, branch, CONTRIBUTING_PATHS)
    pr_path, pr_text = _first_present(repo, branch, PR_TEMPLATE_PATHS)

    # Test command: probe package.json plus every marker in TEST_MARKERS,
    # all concurrently.
    test_candidates = ["package.json"] + [m for m, _cmd in TEST_MARKERS]
    test_results = _fetch_all(repo, branch, test_candidates)

    test_command = None
    pkg = test_results.get("package.json")
    if pkg:
        try:
            scripts = json.loads(pkg).get("scripts", {})
            if "test" in scripts:
                test_command = f"npm test  ({scripts['test']})"
        except json.JSONDecodeError:
            pass
    if test_command is None:
        for marker, cmd in TEST_MARKERS:
            if test_results.get(marker):
                test_command = cmd
                break

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
        "test_command": test_command,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect a repo for PR expectations.")
    parser.add_argument("--repo", required=True, help="owner/repo or a GitHub URL")
    args = parser.parse_args(argv)
    print(json.dumps(check(args.repo), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
