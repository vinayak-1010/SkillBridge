#!/usr/bin/env python3
"""Map a GitHub repository to depth 2.

Fetches the repo tree, keeps entries up to depth 2, flags likely entry points,
and reads build/test commands from common config files. Prints a JSON summary.

Standalone: python map_repo.py --repo owner/repo
Also invoked by the repo-onboarding skill via the harness run_script tool.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"
USER_AGENT = "SkillBridge-repo-onboarding/0.1"

ENTRY_HINTS = (
    "main.py",
    "__main__.py",
    "app.py",
    "manage.py",
    "index.js",
    "index.ts",
    "main.go",
    "main.rs",
    "cmd/",
    "src/",
)


def _headers() -> dict:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get(url: str) -> dict | list | None:
    try:
        req = urllib.request.Request(url, headers=_headers())
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _raw(repo: str, branch: str, path: str) -> str | None:
    try:
        req = urllib.request.Request(f"{RAW}/{repo}/{branch}/{path}", headers=_headers())
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            if resp.status != 200:
                return None
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def _normalize_repo(repo: str) -> str:
    repo = repo.strip().rstrip("/")
    for prefix in ("https://github.com/", "http://github.com/", "github.com/"):
        if repo.startswith(prefix):
            repo = repo[len(prefix):]
    return repo


def _depth(path: str) -> int:
    return path.count("/")


def _build_test_commands(repo: str, branch: str) -> dict:
    build = test = None
    pkg = _raw(repo, branch, "package.json")
    if pkg:
        try:
            scripts = json.loads(pkg).get("scripts", {})
            if "build" in scripts:
                build = "npm run build"
            if "test" in scripts:
                test = "npm test"
        except json.JSONDecodeError:
            pass
    for marker, b, t in (
        ("pyproject.toml", "pip install -e .", "pytest"),
        ("setup.py", "pip install -e .", "pytest"),
        ("Makefile", "make", "make test"),
        ("Cargo.toml", "cargo build", "cargo test"),
        ("go.mod", "go build ./...", "go test ./..."),
    ):
        if _raw(repo, branch, marker):
            build = build or b
            test = test or t
    return {"build": build, "test": test}


def map_repo(repo: str) -> dict:
    repo = _normalize_repo(repo)
    meta = _get(f"{API}/repos/{repo}")
    if not isinstance(meta, dict) or "default_branch" not in meta:
        return {"repo": repo, "error": "repository not found or API error"}
    branch = str(meta["default_branch"])

    tree = _get(f"{API}/repos/{repo}/git/trees/{branch}?recursive=1")
    paths: list[str] = []
    if isinstance(tree, dict):
        for node in tree.get("tree", []):
            path = node.get("path", "")
            if path and _depth(path) <= 1:  # depth 2 => at most one slash
                suffix = "/" if node.get("type") == "tree" else ""
                paths.append(path + suffix)

    entry_points = [
        p for p in paths if any(p.rstrip("/").endswith(h.rstrip("/")) or p.startswith(h) for h in ENTRY_HINTS)
    ]

    return {
        "repo": repo,
        "description": meta.get("description"),
        "default_branch": branch,
        "language": meta.get("language"),
        "layout": sorted(paths),
        "entry_points": sorted(set(entry_points)),
        "commands": _build_test_commands(repo, branch),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Map a GitHub repo to depth 2.")
    parser.add_argument("--repo", required=True, help="owner/repo or a GitHub URL")
    args = parser.parse_args(argv)
    print(json.dumps(map_repo(args.repo), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
