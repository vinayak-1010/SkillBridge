# SkillBridge

**A reliable local agent harness for small open-weight models.**

SkillBridge is an open-source Python command-line harness that lets tiny
open-weight models (1-4B parameters, run locally through [Ollama](https://ollama.com))
execute standard [Agent Skills](https://code.claude.com/docs/en/skills) reliably.
It uses constrained decoding, progressive skill loading, and a verify-and-retry
loop. It ships with three Hacktoberfest-focused skills and a benchmark that
compares the same model with and without the harness.

No GPU. No paid API. Runs on a laptop.

---

## Why

Small open-weight models are free to run on a laptop, but they fail at agentic
work: they produce malformed tool calls, pick the wrong tool, and overflow
their small context when given too much text. SkillBridge does not change the
model. The harness around the model takes over reliability.

## 60-second quickstart

```bash
# 1. Install Ollama and pull a small open-weight model
ollama pull qwen3:4b         # Apache-2.0 weights; or: ollama pull phi4-mini

# 2. Install SkillBridge
pip install -e .

# 3. See the skills, then run a task
skillbridge list
skillbridge run "find me beginner issues in Java"
```

Network is needed only for the GitHub API the skills call. No GPU required.

## Architecture

```
task
 -> Catalog   scan skills/, read only frontmatter (~50 tokens/skill)
 -> Router    model picks 1 skill (enum-constrained); BM25 fallback
 -> Activator load chosen SKILL.md body; references/ on demand
 -> Loop      max 8 steps; one schema-constrained JSON action per step
 -> Tools     read_file, list_dir, http_get (allowlist), run_script
 -> Verifier  schema, tool, path and args checks; retry <= 2
 -> Budget    token meter; partial answer if exceeded
 -> Trace     JSONL log per run
```

Every action the model emits is a single JSON object enforced by a schema:

```json
{ "tool": "<tool name or 'finish'>", "args": { } }
```

**Design rules**

- *Progressive disclosure*: start with only skill names and descriptions in context.
- The model never writes free-form tool text; the backend enforces the JSON
  schema (Ollama's `format` parameter, or a llama.cpp grammar).
- The harness owns safety: a path sandbox, a URL allowlist
  (`api.github.com`, `raw.githubusercontent.com`), scripts that run only from
  the active skill's `scripts/` folder, and a 10-second subprocess timeout.

## Commands

| Command | What it does |
| --- | --- |
| `skillbridge list` | Show the available skills. |
| `skillbridge run "<task>"` | Run a task end to end. |
| `skillbridge validate` | Check skills against the Agent Skills standard. |

Useful flags for `run`: `--model phi4-mini`, `--trace run.jsonl`,
`--max-steps 8`, `--budget 6000`.

## The three skills

| Skill | Behavior |
| --- | --- |
| **contrib-scout** | Given languages and interests, returns the top 5 ranked beginner-friendly GitHub issues (`good first issue` / `hacktoberfest`), one reason each. |
| **pr-prep** | Given a repo URL, outputs a PR checklist from the repo's CONTRIBUTING, PR template, commit conventions, and test command. |
| **repo-onboarding** | Given a repo URL, outputs a one-page map: layout to depth 2, entry points, build and test commands. |

Each skill is a standard Agent Skill: a folder with `SKILL.md` (YAML
frontmatter) plus optional `scripts/` and `references/`. They work in any
Agent Skills compatible tool, not just SkillBridge.

## Model and license

- Default model: **qwen3:4b** (Qwen3, Apache-2.0 weights). Alternative:
  **phi4-mini** (MIT). Always check the current license on the model's page.
- SkillBridge itself is **Apache-2.0** (see [LICENSE](LICENSE)).
- The backend sits behind an `LLMBackend` interface, so a llama.cpp server can
  be swapped in. Optional AWS deployment notes live in `docs/aws.md`.

## Benchmark

`bench/` compares a naive baseline against the harness on the same model over
~10 tasks, reporting success rate and average tokens.

```bash
python bench/run_bench.py --model qwen3:4b
```

Results are written to [bench/RESULTS.md](bench/RESULTS.md). We report them
honestly, including when the gain is small.

## Development

```bash
pip install -e ".[dev]"
pytest -q
skillbridge validate
```

CI runs skill validation and the test suite on every push and pull request.

## Project layout

```
skillbridge/
  LICENSE  README.md  pyproject.toml  SPEC.md
  src/skillbridge/
    catalog.py  router.py  backend.py  loop.py
    tools.py    verifier.py budget.py  trace.py  cli.py
  skills/
    contrib-scout/   pr-prep/   repo-onboarding/
  bench/   tasks.jsonl  run_bench.py  RESULTS.md
  tests/
  .github/workflows/ci.yml
```

## Out of scope

Web UI, fine-tuning, multi-agent orchestration, paid APIs, and vector
databases. A VS Code extension or web page could be added later as a bonus.
