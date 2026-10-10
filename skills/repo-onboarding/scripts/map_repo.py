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
import urllib.request
from concurrent.futures import ThreadPoolExecutor

API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"
USER_AGENT = "SkillBridge-repo-onboarding/0.1"

# Per-request timeout. Several candidate files are checked for build/test
# markers; they are fetched concurrently (see _build_test_commands) so the
# total wall time stays close to this single-request timeout rather than
# their sum, keeping the script well inside the harness's 10s sandbox cap.
RAW_FETCH_TIMEOUT = 4

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


def _raw(repo: str, branch: str, path: str, timeout: int = RAW_FETCH_TIMEOUT) -> str | None:
    try:
        req = urllib.request.Request(f"{RAW}/{repo}/{branch}/{path}", headers=_headers())
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
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
    """Fetch all candidate marker files concurrently and derive commands.

    Markers are checked in parallel (not one request after another) so this
    function's wall time is bounded by the single slowest fetch, not their
    sum. That keeps the whole script inside the harness's 10s timeout even
    when the network to raw.githubusercontent.com is slow.
    """
    markers = [
        ("package.json", None, None),  # handled specially below
        ("pyproject.toml", "pip install -e .", "pytest"),
        ("setup.py", "pip install -e .", "pytest"),
        ("Makefile", "make", "make test"),
        ("Cargo.toml", "cargo build", "cargo test"),
        ("go.mod", "go build ./...", "go test ./..."),
    ]
    with ThreadPoolExecutor(max_workers=len(markers)) as pool:
        futures = {
            pool.submit(_raw, repo, branch, name): (name, b, t) for name, b, t in markers
        }
        results = {futures[f]: f.result() for f in futures}

    build = test = None
    for (name, b, t), content in results.items():
        if not content:
            continue
        if name == "package.json":
            try:
                scripts = json.loads(content).get("scripts", {})
                if "build" in scripts:
                    build = build or "npm run build"
                if "test" in scripts:
                    test = test or "npm test"
            except json.JSONDecodeError:
                pass
            continue
        build = build or b
        test = test or t
    return {"build": build, "test": test}


def _summarize_layout(paths: list[str]) -> list[str]:
    """Collapse a depth-2 listing into a compact, one-page-sized summary.

    Top-level files are kept as-is. Top-level directories are kept with a
    count of how many depth-2 children they contain, instead of listing
    every child, so the summary stays short regardless of repo size (a
    requirement for progressive disclosure into a small model's context).
    """
    top_level_files: list[str] = []
    dir_child_counts: dict[str, int] = {}
    for p in paths:
        if "/" not in p.rstrip("/"):
            if p.endswith("/"):
                dir_child_counts.setdefault(p, 0)
            else:
                top_level_files.append(p)
        else:
            top_dir = p.split("/", 1)[0] + "/"
            dir_child_counts[top_dir] = dir_child_counts.get(top_dir, 0) + 1

    lines = sorted(top_level_files)
    for d in sorted(dir_child_counts):
        count = dir_child_counts[d]
        lines.append(f"{d} ({count} item{'s' if count != 1 else ''})" if count else d)
    return lines


def map_repo(repo: str, max_layout_entries: int = 40) -> dict:
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

    layout = _summarize_layout(paths)
    truncated = len(layout) > max_layout_entries
    if truncated:
        layout = layout[:max_layout_entries]

    return {
        "repo": repo,
        "description": meta.get("description"),
        "default_branch": branch,
        "language": meta.get("language"),
        "layout": layout,
        "layout_truncated": truncated,
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
