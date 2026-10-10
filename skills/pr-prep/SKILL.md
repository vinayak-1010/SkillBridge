---
name: pr-prep
description: Prepare to open a pull request on a GitHub repository. Use when the user gives a repository URL and wants a checklist of what the project expects, drawn from its CONTRIBUTING guide, pull-request template, commit conventions and test command.
license: Apache-2.0
allowed-tools: run_script, http_get, finish
---

# pr-prep

Produce a short, actionable checklist for opening a PR on a given repository.

## When to use

The user supplies a GitHub repository URL (or `owner/repo`) and wants to know
how that project expects contributions to be submitted.

## How to run

1. Call `run_script` with `script: "check_repo.py"` and pass the repository:
   `{"tool": "run_script", "args": {"script": "check_repo.py", "args": ["--repo", "owner/repo"]}}`
2. The script fetches, where present: CONTRIBUTING, the PR template, any commit
   convention hints, and the test command from common config files. It prints a
   JSON object summarising what it found.
3. `finish` with a checklist the user can follow before opening their PR. Only
   include items the repository actually documents; note anything that was not
   found so the user knows what is unspecified.

## Checklist shape

- Read CONTRIBUTING (link it).
- Follow the PR template (summarise the sections).
- Match the commit convention (state it).
- Run the test command (give the exact command).
