---
name: contrib-scout
description: Find beginner-friendly open-source issues to contribute to. Use when the user gives programming languages and interests and wants a short, ranked list of good first issues (good first issue / hacktoberfest labels) from recently active repositories that have a CONTRIBUTING guide.
license: Apache-2.0
allowed-tools: run_script, http_get, finish
---

# contrib-scout

Help a contributor find beginner-friendly issues to work on.

## When to use

The user supplies one or more languages (for example "Python", "Java") and
optional interests (for example "web", "cli", "data"). You return the top 5
ranked issues, each with a one-line reason.

## How to run

1. Call `run_script` with `script: "search_issues.py"` and pass the languages
   and interests as args, for example:
   `{"tool": "run_script", "args": {"script": "search_issues.py", "args": ["--languages", "python", "--interests", "cli"]}}`
2. The script queries the GitHub search API for open issues labelled
   `good first issue` or `hacktoberfest` in recently updated repositories, and
   prints a JSON array of candidates.
3. Rank the candidates using the rules in `references/ranking.md` and select
   the top 5.
4. `finish` with a short list: for each issue give its title, its exact `url`
   copied verbatim from the script output, and a one-line reason it is a good
   match. Never omit the URL and never invent or alter it.

## Required answer format

Each line of the final answer MUST follow this exact shape so the URL is
always present and checkable:

```
1. <title> - <url> - <one-line reason>
2. <title> - <url> - <one-line reason>
...
```

## Notes

- If the GitHub API is rate limited, the script accepts an optional token via
  the `GITHUB_TOKEN` environment variable.
- Keep the final answer compact: 5 issues, one line each, URL included.
