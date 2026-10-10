"""Action verifier.

Checks each parsed action before it runs: schema shape, that the tool is
known, and that required args are present. On failure it returns a short
hint string the loop feeds back to the model for a retry (max 2).

The JSON schema here is also handed to the backend for constrained
decoding, so well-behaved backends emit valid actions by construction.
"""

from __future__ import annotations

import json

from .tools import TOOLS

# Required args per tool (presence check; deeper checks live in the sandbox).
REQUIRED_ARGS: dict[str, list[str]] = {
    "read_file": ["path"],
    "list_dir": [],
    "http_get": ["url"],
    "run_script": ["script"],
    "finish": ["answer"],
}

VALID_TOOLS = set(TOOLS) | {"finish"}


def action_schema() -> dict:
    """JSON schema for a single action, for constrained decoding."""
    return {
        "type": "object",
        "properties": {
            "tool": {"type": "string", "enum": sorted(VALID_TOOLS)},
            "args": {"type": "object"},
        },
        "required": ["tool", "args"],
        "additionalProperties": False,
    }


def parse_action(text: str) -> tuple[dict | None, str | None]:
    """Parse model output into an action dict.

    Returns (action, None) on success or (None, hint) on failure. Tolerates
    surrounding prose by extracting the first balanced JSON object.
    """
    text = text.strip()
    obj = _extract_json(text)
    if obj is None:
        return None, "Output must be a single JSON object like {\"tool\": ..., \"args\": {...}}."
    if not isinstance(obj, dict):
        return None, "Action must be a JSON object."
    return obj, None


def verify(action: dict) -> str | None:
    """Return None if the action is valid, else a short corrective hint."""
    if "tool" not in action:
        return "Missing 'tool'. Use one of: " + ", ".join(sorted(VALID_TOOLS)) + "."
    tool = action.get("tool")
    if tool not in VALID_TOOLS:
        return f"Unknown tool '{tool}'. Use one of: " + ", ".join(sorted(VALID_TOOLS)) + "."
    args = action.get("args")
    if not isinstance(args, dict):
        return "'args' must be a JSON object."
    missing = [a for a in REQUIRED_ARGS.get(tool, []) if a not in args or args[a] in (None, "")]
    if missing:
        return f"Tool '{tool}' requires args: {', '.join(missing)}."
    return None


def _extract_json(text: str) -> object | None:
    """Extract the first top-level JSON object from text."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    return None
    return None
