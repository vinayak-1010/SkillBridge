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
3. `finish` with a checklist the user can follow before opening their PR.

## Grounding rule (critical)

Base every line strictly on the script's JSON output. Never say a guide,
template, or convention exists unless its `found` field is `true` (or its
value is non-null). If `contributing.found` is `false`, do not tell the user
to "read CONTRIBUTING" — instead say the repository has no CONTRIBUTING file
and that unwritten norms (open an issue first, keep PRs small) apply. The
same rule applies to `pr_template.found` and `commit_convention`: report
"not specified" rather than inventing a convention.

## Checklist shape

For each item, follow this pattern:
- If found/present: state it concretely (link the path, name the command).
- If not found/null: say so explicitly, for example "No CONTRIBUTING file
  found; no documented process beyond opening a PR."

Items to cover: CONTRIBUTING guide, PR template, commit convention, test
command.
