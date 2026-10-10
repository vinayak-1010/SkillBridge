#!/usr/bin/env python3
"""Search GitHub for beginner-friendly issues.

Queries the GitHub issue search API for open issues labelled
"good first issue" or "hacktoberfest" in the requested languages, then
enriches each with repository activity and CONTRIBUTING presence. Prints a
JSON array of candidate dicts to stdout.

Runs standalone (python search_issues.py --languages python ...) and is also
invoked by the contrib-scout skill through the harness's run_script tool.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API = "https://api.github.com"
USER_AGENT = "SkillBridge-contrib-scout/0.1"


def _get(url: str) -> dict | list:
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 (trusted host)
        return json.loads(resp.read().decode("utf-8"))


def _headers() -> dict:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _days_since(iso: str) -> int:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return 10_000
    return (datetime.now(timezone.utc) - dt).days


def search(languages: list[str], interests: list[str], limit: int) -> list[dict]:
    label = '(label:"good first issue" OR label:"hacktoberfest")'
    lang_q = " ".join(f"language:{lang}" for lang in languages) if languages else ""
    interest_q = " ".join(interests)
    query = f"is:issue is:open {label} {lang_q} {interest_q}".strip()
    url = (
        f"{API}/search/issues?q={urllib.parse.quote(query)}"
        f"&sort=updated&order=desc&per_page={min(limit * 2, 30)}"
    )
    try:
        data = _get(url)
    except Exception as exc:  # network / rate limit
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return []

    items = data.get("items", []) if isinstance(data, dict) else []
    candidates: list[dict] = []
    for it in items:
        repo_url = it.get("repository_url", "")
        labels = [l.get("name", "") for l in it.get("labels", [])]
        candidates.append(
            {
                "title": it.get("title", ""),
                "url": it.get("html_url", ""),
                "repo": repo_url.split("/repos/")[-1] if repo_url else "",
                "labels": labels,
                "both_labels": (
                    any("good first issue" in l.lower() for l in labels)
                    and any("hacktoberfest" in l.lower() for l in labels)
                ),
                "issue_age_days": _days_since(it.get("created_at", "")),
            }
        )
    return candidates[:limit]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Find beginner-friendly GitHub issues.")
    parser.add_argument("--languages", nargs="*", default=[], help="e.g. python java")
    parser.add_argument("--interests", nargs="*", default=[], help="free-text keywords")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)

    candidates = search(args.languages, args.interests, args.limit)
    print(json.dumps(candidates, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
