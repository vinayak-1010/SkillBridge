# SkillBridge SPEC

A reliable local agent harness for small open-weight models (1-4B, run via Ollama).

## Action schema

Every step the model produces exactly one JSON action:

```json
{ "tool": "<tool name or 'finish'>", "args": { } }
```

- `tool` is one of the registered tool names or the literal `"finish"`.
- The `finish` action carries `{"answer": "<str>"}` in `args`.

## Pipeline

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

## Design rules

- Progressive disclosure: start with only skill names and descriptions in context.
- The model never writes free-form tool text; the backend enforces the JSON schema
  (Ollama `format` parameter, or llama.cpp grammar).
- The harness owns safety:
  - path sandbox (reads confined to the active skill folder and workspace),
  - URL allowlist (`api.github.com`, `raw.githubusercontent.com`),
  - scripts run only from the active skill's `scripts/` folder,
  - 10 second subprocess timeout.

## Agent Skills standard

- Folder name equals the `name` field; lowercase letters, digits and hyphens; max 64 chars.
- `SKILL.md` begins with YAML frontmatter: `name` and `description`
  (max 1024 chars; say what it does and when to use it).
  Optional: `license`, `compatibility`, `metadata`, `allowed-tools`.
- Body is Markdown under ~500 lines; long material in `references/`, executables in `scripts/`.

## Defaults

- Model backend: Ollama, default `qwen3:4b`, alternative `phi4-mini`.
- `max_steps = 8`, `token_budget = 6000`, retry `<= 2`, subprocess timeout `10s`.
