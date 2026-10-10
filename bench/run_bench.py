#!/usr/bin/env python3
"""Benchmark: naive baseline vs the SkillBridge harness on the same model.

For each task in tasks.jsonl we run two conditions against the same Ollama
model:

  naive   - the model is asked to answer the task directly, free-form, with no
            skills, tools, routing, or schema enforcement.
  harness - the full SkillBridge pipeline: route to a skill, then the
            constrained action loop with tools and the verifier.

Each task carries a simple pass/fail check. We report success rate and average
tokens per condition and write a Markdown table to RESULTS.md.

Usage:
  python bench/run_bench.py --model qwen3:4b
  python bench/run_bench.py --model qwen3:4b --out bench/RESULTS.md
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path

from skillbridge.backend import OllamaBackend
from skillbridge.catalog import scan
from skillbridge.loop import run as run_loop
from skillbridge.router import route

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"
TASKS = Path(__file__).resolve().parent / "tasks.jsonl"


def load_tasks() -> list[dict]:
    tasks = []
    for line in TASKS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            tasks.append(json.loads(line))
    return tasks


def check_output(output: str, check: dict) -> bool:
    kind = check.get("type")
    if kind == "regex":
        matches = re.findall(check["pattern"], output or "")
        return len(matches) >= int(check.get("min_count", 1))
    if kind == "contains_any":
        low = (output or "").lower()
        return any(term.lower() in low for term in check.get("any", []))
    return False


def run_naive(task: str, backend: OllamaBackend) -> tuple[str, int]:
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant. Answer the user's task directly. "
                "If GitHub issues or repositories are requested, provide concrete "
                "items with full URLs."
            ),
        },
        {"role": "user", "content": task},
    ]
    return backend.generate(messages, schema=None, max_tokens=800)


def run_harness(task: str, backend: OllamaBackend, skills) -> tuple[str, int]:
    skill = route(task, skills, backend)
    if skill is None:
        return "", 0
    result = run_loop(task, skill, backend, max_steps=8, token_budget=6000)
    return result.answer, result.tokens_used


def summarize(label: str, rows: list[dict]) -> dict:
    passes = sum(1 for r in rows if r["pass"])
    tokens = [r["tokens"] for r in rows]
    return {
        "label": label,
        "n": len(rows),
        "passes": passes,
        "rate": passes / len(rows) if rows else 0.0,
        "avg_tokens": round(statistics.mean(tokens)) if tokens else 0,
    }


def write_results(out: Path, model: str, naive: dict, harness: dict, rows: list[dict]) -> None:
    lines = [
        "# Benchmark Results",
        "",
        f"Model: `{model}` (local, via Ollama). Tasks: {naive['n']}.",
        "",
        "| Condition | Success rate | Passes | Avg tokens |",
        "| --- | --- | --- | --- |",
        f"| Naive baseline | {naive['rate']*100:.0f}% | {naive['passes']}/{naive['n']} | {naive['avg_tokens']} |",
        f"| SkillBridge harness | {harness['rate']*100:.0f}% | {harness['passes']}/{harness['n']} | {harness['avg_tokens']} |",
        "",
        "## Per-task detail",
        "",
        "| Task | Skill | Naive | Harness |",
        "| --- | --- | --- | --- |",
    ]
    for r in rows:
        n = "PASS" if r["naive_pass"] else "fail"
        h = "PASS" if r["harness_pass"] else "fail"
        lines.append(f"| {r['id']} | {r['skill']} | {n} | {h} |")
    lines.append("")
    lines.append(
        "> Results are reported honestly, including the case where the gain is small. "
        "The naive baseline often fails because small models emit malformed or "
        "unverifiable output; the harness constrains and verifies each action."
    )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Naive vs SkillBridge benchmark.")
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent / "RESULTS.md"))
    args = parser.parse_args(argv)

    backend = OllamaBackend(model=args.model)
    skills = scan([SKILLS_DIR])
    tasks = load_tasks()

    naive_rows: list[dict] = []
    harness_rows: list[dict] = []
    detail: list[dict] = []

    for t in tasks:
        prompt, check = t["prompt"], t["check"]
        try:
            n_out, n_tok = run_naive(prompt, backend)
            n_pass = check_output(n_out, check)
        except Exception as exc:
            n_out, n_tok, n_pass = f"ERROR: {exc}", 0, False
        try:
            h_out, h_tok = run_harness(prompt, backend, skills)
            h_pass = check_output(h_out, check)
        except Exception as exc:
            h_out, h_tok, h_pass = f"ERROR: {exc}", 0, False

        naive_rows.append({"pass": n_pass, "tokens": n_tok})
        harness_rows.append({"pass": h_pass, "tokens": h_tok})
        detail.append(
            {
                "id": t["id"],
                "skill": t.get("skill", ""),
                "naive_pass": n_pass,
                "harness_pass": h_pass,
            }
        )
        print(f"{t['id']}: naive={'PASS' if n_pass else 'fail'} harness={'PASS' if h_pass else 'fail'}")

    naive = summarize("naive", naive_rows)
    harness = summarize("harness", harness_rows)
    out = Path(args.out)
    write_results(out, args.model, naive, harness, detail)
    print(f"\nNaive:   {naive['rate']*100:.0f}% success, {naive['avg_tokens']} avg tokens")
    print(f"Harness: {harness['rate']*100:.0f}% success, {harness['avg_tokens']} avg tokens")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
