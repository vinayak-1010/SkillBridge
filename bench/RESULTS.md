# Benchmark Results

Model: `qwen3:4b` (local, via Ollama). Tasks: 10.

> This file is a placeholder with the expected table shape. Generate real
> numbers on a machine with Ollama running:
>
> ```
> ollama pull qwen3:4b
> python bench/run_bench.py --model qwen3:4b
> ```
>
> `run_bench.py` overwrites this file with measured results.

| Condition | Success rate | Passes | Avg tokens |
| --- | --- | --- | --- |
| Naive baseline | TBD | TBD | TBD |
| SkillBridge harness | TBD | TBD | TBD |

## Why the harness is expected to win

- The naive baseline asks a 1-4B model to answer free-form. Small models
  frequently hallucinate issue URLs or emit malformed output, so the pass/fail
  checks (real GitHub URLs, documented PR steps) fail.
- The harness routes to a skill, runs a real script against the GitHub API, and
  verifies every action against a schema, so the output is grounded in live
  data and structurally valid.

Results are reported honestly, including when the gain is small.
