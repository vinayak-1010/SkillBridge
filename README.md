# SkillBridge

**A reliable local agent harness for small open-weight models.**

SkillBridge is an open-source Python command-line harness that lets tiny
open-weight models (1-4B parameters, run locally through [Ollama](https://ollama.com))
execute standard [Agent Skills](https://code.claude.com/docs/en/skills) reliably.
It uses constrained decoding, progressive skill loading, and a verify-and-retry
loop. It ships with three Hacktoberfest-focused skills and a benchmark that
compares the same model with and without the harness.

No GPU. No paid API. Runs on a laptop.

**Live demo:** https://vinayak-1010.github.io/SkillBridge/
*(static frontend on GitHub Pages, pointed at a SkillBridge API running
locally on the author's laptop next to Ollama via a Cloudflare Tunnel — see
[Web demo](#web-demo) for why, and how to point it at your own machine
instead.)*

**For judges:** open the live demo link above, click **Connect**, wait for
"connected · Ollama reachable", then type a task (for example `find me
beginner issues in Java`) and press **Run task**. You'll see the harness
route to a skill, call a real script against the live GitHub API, and finish
with a grounded answer, streamed step by step in the Live trace panel.

---

## Why

Small open-weight models are free to run on a laptop, but they fail at agentic
work: they produce malformed tool calls, pick the wrong tool, and overflow
their small context when given too much text. SkillBridge does not change the
model. The harness around the model takes over reliability.

## 60-second quickstart

```bash
# 1. Install Ollama: https://ollama.com/download
# 2. Pull a small open-weight model (Apache-2.0 weights)
ollama pull qwen3:1.7b       # recommended default: fast on CPU
# ollama pull qwen3:4b       # larger alternative, needs more CPU/RAM
# ollama pull phi4-mini      # MIT-licensed alternative

# 3. Install SkillBridge
python -m venv .venv && .venv\Scripts\activate   # Windows
# source .venv/bin/activate                      # macOS / Linux
pip install -e .

# 4. See the skills, then run a task live
skillbridge list
skillbridge run "find me beginner issues in Java" --model qwen3:1.7b
```

Network is needed only for the GitHub API the skills call. No GPU required.
On a CPU-only laptop, `qwen3:1.7b` finishes a task in well under a minute;
`qwen3:4b` works too but is noticeably slower per step (see
[Risks and Fallbacks](SPEC.md) for the sizing tradeoff).

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

Useful flags for `run`: `--model qwen3:4b`, `--trace run.jsonl`,
`--max-steps 8`, `--budget 6000`.

> **Verified live** (CPU-only laptop, `qwen3:1.7b`, no GPU): all three skills
> below have been run end to end against the real Ollama server and the real
> GitHub API, producing correct, grounded answers with live issue URLs,
> an accurate repository map, and an honest "not found" when a repo has no
> CONTRIBUTING file. See `bench/RESULTS.md` for the quantitative comparison.

## Web demo

A small browser UI (`web/frontend/`) sits on top of a FastAPI wrapper
(`web/api/`) around the exact same `catalog` / `router` / `loop` code the CLI
uses — the API adds no new agent logic. It lists skills, runs a task, and
streams the live trace (route → action → observation → verify → finish) to
the page as it happens.

**Why the backend isn't "deployed to the cloud":** SkillBridge's entire pitch
is no GPU and no paid API — the model runs on whoever's machine has Ollama.
Hosting the API on a cloud box would mean paying for compute or quietly
reintroducing a hosted model, which contradicts the project. Instead, the
**frontend** is static-hosted (GitHub Pages) and the **API** runs locally,
next to Ollama, on your own machine. This is the same tradeoff llama.cpp /
Ollama's own desktop UIs make.

**Live API during judging:** the hosted frontend's "API base URL" box
defaults to a Cloudflare Tunnel into the author's laptop:
https://manager-altered-couples-model.trycloudflare.com — live only while
that machine is running the demo. If the page shows "cannot reach API", the
demo session has ended; swap the URL for your own API (below) instead.

Run your own API:

```bash
pip install -e ".[web]"
uvicorn web.api.main:app --port 8000
```

Then open the live frontend above, replace the API base URL with
`http://localhost:8000`, and hit Connect. If Ollama and the API are both
running locally, the page will show "connected · Ollama reachable" and you
can run a task straight from the browser.

To expose your own local API to other devices (e.g. for a live demo), run
a tunnel in a second terminal: `cloudflared tunnel --url http://localhost:8000`
([install cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)),
then put the printed `https://*.trycloudflare.com` URL into the API base URL
box. Quick tunnels are free but ephemeral — a new URL is issued every time
`cloudflared` restarts.

To run the frontend locally instead of using the hosted page, just open
`web/frontend/index.html` in a browser, or serve the folder with any static
file server.

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

- Recommended model: **qwen3:1.7b** (Qwen3, Apache-2.0 weights) — fast enough
  for live use on a CPU-only laptop. The larger **qwen3:4b** (same license)
  also works, just slower per step on CPU. Alternative: **phi4-mini** (MIT).
  Always check the current license on the model's page.
- SkillBridge disables the model's hidden "thinking" mode for action steps
  (`think: false` in the Ollama request) so every step produces the
  schema-constrained JSON action directly, instead of spending the token
  budget on an invisible reasoning trace.
- SkillBridge itself is **Apache-2.0** (see [LICENSE](LICENSE)).
- The backend sits behind an `LLMBackend` interface, so a llama.cpp server can
  be swapped in. Optional AWS deployment notes live in `docs/aws.md`.

## Benchmark

`bench/` compares a naive baseline against the harness on the same model over
~10 tasks, reporting success rate and average tokens.

```bash
python bench/run_bench.py --model qwen3:1.7b
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
  web/
    api/        main.py (FastAPI wrapper, no new agent logic)
    frontend/   index.html  styles.css  app.js (static, no build step)
  tests/
  .github/workflows/ci.yml
```

## Out of scope

Fine-tuning, multi-agent orchestration, paid APIs, and vector databases.
A bonus browser UI (`web/`) is included; it is a thin client over the same
CLI logic, not a new product surface.
