# Benchmark Results

Model: `qwen3:1.7b` (local, via Ollama). Tasks: 10.

| Condition | Success rate | Passes | Avg tokens |
| --- | --- | --- | --- |
| Naive baseline | 70% | 7/10 | 643 |
| SkillBridge harness | 100% | 10/10 | 1605 |

## Per-task detail

| Task | Skill | Naive | Harness |
| --- | --- | --- | --- |
| t01 | contrib-scout | fail | PASS |
| t02 | contrib-scout | PASS | PASS |
| t03 | contrib-scout | PASS | PASS |
| t04 | pr-prep | PASS | PASS |
| t05 | pr-prep | PASS | PASS |
| t06 | pr-prep | PASS | PASS |
| t07 | repo-onboarding | fail | PASS |
| t08 | repo-onboarding | PASS | PASS |
| t09 | repo-onboarding | fail | PASS |
| t10 | contrib-scout | PASS | PASS |

> Results are reported honestly, including the case where the gain is small. The naive baseline often fails because small models emit malformed or unverifiable output; the harness constrains and verifies each action.
