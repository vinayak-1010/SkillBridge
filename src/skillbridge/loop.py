"""The constrained action loop.

Given a task and an activated skill, drive the model through up to
`max_steps` steps. Each step:
  1. ask the backend for one schema-constrained JSON action,
  2. parse and verify it (retry up to twice with a hint on failure),
  3. run the tool inside the sandbox and feed the observation back,
  4. stop on a `finish` action, budget exhaustion, or step cap.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .backend import LLMBackend
from .budget import Budget
from .catalog import Skill, load_body
from .tools import TOOLS, SandboxError, SandboxPolicy, ToolError
from .trace import Trace
from .verifier import action_schema, parse_action, verify

MAX_RETRIES = 2


@dataclass
class RunResult:
    answer: str
    steps: int
    tokens_used: int
    finished: bool
    partial: bool = False
    trace_events: list[dict] = field(default_factory=list)


def _system_prompt(skill: Skill, body: str) -> str:
    tool_names = ", ".join(sorted(TOOLS)) + ", finish"
    return (
        "You are SkillBridge, executing a single Agent Skill to solve a task.\n"
        "Respond with exactly ONE JSON action per turn and nothing else.\n"
        'Format: {"tool": "<name>", "args": {...}}\n'
        f"Available tools: {tool_names}.\n"
        'When done, respond {"tool": "finish", "args": {"answer": "<final answer>"}}.\n\n'
        f"Active skill: {skill.name}\n"
        f"{body}\n"
    )


def run(
    task: str,
    skill: Skill,
    backend: LLMBackend,
    max_steps: int = 8,
    token_budget: int = 6000,
    read_roots: list[Path] | None = None,
    trace: Trace | None = None,
) -> RunResult:
    body = load_body(skill)
    policy = SandboxPolicy(
        read_roots=list(read_roots or [skill.path, Path.cwd()]),
        skill_dir=skill.path,
    )
    budget = Budget(limit=token_budget)
    tr = trace or Trace()
    schema = action_schema()

    messages: list[dict] = [
        {"role": "system", "content": _system_prompt(skill, body)},
        {"role": "user", "content": task},
    ]
    tr.log("start", task=task, skill=skill.name, budget=token_budget, max_steps=max_steps)

    last_answer = ""
    for step in range(1, max_steps + 1):
        if budget.exceeded():
            tr.log("budget_exceeded", step=step, used=budget.used)
            return RunResult(
                answer=last_answer or "Budget exceeded before completion.",
                steps=step - 1,
                tokens_used=budget.used,
                finished=False,
                partial=True,
                trace_events=tr.events,
            )

        action, obs = _one_step(step, messages, backend, schema, budget, policy, tr)
        if action is not None and action.get("tool") == "finish":
            last_answer = str(action.get("args", {}).get("answer", ""))
            tr.log("finish", step=step, answer=last_answer, tokens=budget.used)
            return RunResult(
                answer=last_answer,
                steps=step,
                tokens_used=budget.used,
                finished=True,
                trace_events=tr.events,
            )
        # Feed observation back for the next step.
        if obs is not None:
            messages.append({"role": "user", "content": f"Observation:\n{obs}"})

    tr.log("max_steps", used=budget.used)
    return RunResult(
        answer=last_answer or "Reached step limit without a finish action.",
        steps=max_steps,
        tokens_used=budget.used,
        finished=False,
        partial=True,
        trace_events=tr.events,
    )


def _one_step(
    step: int,
    messages: list[dict],
    backend: LLMBackend,
    schema: dict,
    budget: Budget,
    policy: SandboxPolicy,
    tr: Trace,
) -> tuple[dict | None, str | None]:
    """Run one step with up to MAX_RETRIES correction attempts.

    Returns (action, observation). A finish action is returned with
    observation None; a tool action returns its observation string.
    """
    hint: str | None = None
    for attempt in range(MAX_RETRIES + 1):
        turn_messages = list(messages)
        if hint:
            turn_messages.append({"role": "user", "content": f"Correction: {hint}"})

        text, tokens = backend.generate(turn_messages, schema=schema, max_tokens=512)
        budget.spend(tokens)
        tr.log("model", step=step, attempt=attempt, raw=text, tokens=tokens)

        action, parse_hint = parse_action(text)
        hint = parse_hint
        if action is None:
            continue

        verify_hint = verify(action)
        if verify_hint:
            hint = verify_hint
            tr.log("verify_fail", step=step, attempt=attempt, hint=hint, action=action)
            continue

        tr.log("action", step=step, attempt=attempt, action=action)
        messages.append({"role": "assistant", "content": json.dumps(action)})

        if action["tool"] == "finish":
            return action, None

        # Execute the tool inside the sandbox.
        try:
            observation = TOOLS[action["tool"]](action.get("args", {}), policy)
        except SandboxError as exc:
            observation = f"BLOCKED by sandbox: {exc}"
            tr.log("sandbox_block", step=step, error=str(exc), action=action)
        except ToolError as exc:
            observation = f"Tool error: {exc}"
            tr.log("tool_error", step=step, error=str(exc), action=action)
        else:
            tr.log("observation", step=step, tool=action["tool"], output=observation[:2000])

        # Trim very long observations so they do not blow the context.
        if len(observation) > 4000:
            observation = observation[:4000] + "\n...[truncated]"
        return action, observation

    # All retries exhausted; record and continue the outer loop.
    tr.log("retries_exhausted", step=step, hint=hint)
    messages.append(
        {"role": "assistant", "content": '{"tool": "finish", "args": {"answer": ""}}'}
    )
    return None, f"Could not produce a valid action: {hint}"
