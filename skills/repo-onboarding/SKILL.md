---
name: repo-onboarding
description: "Produce a one-page map of an unfamiliar GitHub repository. Use when the user gives a repository URL and wants a quick orientation: the top-level layout, likely entry points, and the build and test commands."
license: Apache-2.0
allowed-tools: run_script, http_get, finish
---

# repo-onboarding

Give a newcomer a one-page orientation to a repository.

## When to use

The user supplies a GitHub repository URL (or `owner/repo`) and wants to
understand its shape fast before diving in.

## How to run

1. Call `run_script` with `script: "map_repo.py"` and pass the repository:
   `{"tool": "run_script", "args": {"script": "map_repo.py", "args": ["--repo", "owner/repo"]}}`
2. The script walks the tree to depth 2, detects likely entry points, and reads
   build/test commands from common config files. It prints a JSON summary.
3. `finish` with a one-page map:
   - top-level folders and what each is for,
   - the entry point(s),
   - the build command and the test command.

Keep it to one screen. Prefer concrete file paths and commands over prose.
Never copy the script's raw `layout` list verbatim into the answer: group
and summarize it (for example "docs/ (40 files)") instead of listing every
entry. If `layout_truncated` is true, say the list was shortened.
