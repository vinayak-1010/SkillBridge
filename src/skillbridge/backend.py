"""LLM backend abstraction and an Ollama implementation.

The harness talks to the model only through `LLMBackend.generate`. The
default implementation targets a local Ollama server and uses Ollama's
`format` parameter to enforce a JSON schema on the output, so tool calls
are never malformed. A llama.cpp server (grammar-constrained) can be
swapped in behind the same Protocol.
"""

from __future__ import annotations

import json
import os
from typing import Protocol, runtime_checkable

import httpx

DEFAULT_MODEL = "qwen3:4b"
DEFAULT_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")


@runtime_checkable
class LLMBackend(Protocol):
    """A minimal text-generation interface.

    `generate` takes chat messages and an optional JSON schema. When a
    schema is given the backend must constrain the output to match it.
    Returns the generated text and the number of tokens used.
    """

    def generate(
        self,
        messages: list[dict],
        schema: dict | None = None,
        max_tokens: int = 512,
    ) -> tuple[str, int]:  # (text, tokens_used)
        ...


class OllamaBackend:
    """LLMBackend backed by a local Ollama server (/api/chat)."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        host: str = DEFAULT_HOST,
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout

    def generate(
        self,
        messages: list[dict],
        schema: dict | None = None,
        max_tokens: int = 512,
    ) -> tuple[str, int]:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0},
        }
        # Ollama accepts a JSON schema object in `format` for constrained decoding.
        if schema is not None:
            payload["format"] = schema

        url = f"{self.host}/api/chat"
        resp = httpx.post(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        text = data.get("message", {}).get("content", "")
        tokens = int(data.get("eval_count", 0)) + int(data.get("prompt_eval_count", 0))
        if tokens == 0:
            # Fall back to a rough estimate when the server omits counts.
            tokens = _estimate_tokens(messages, text)
        return text, tokens


class EchoBackend:
    """Offline backend for tests and smoke runs.

    It does not call any model. Instead it returns scripted responses from
    a queue, which lets the loop and router be exercised without Ollama.
    """

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = list(responses or [])

    def push(self, text: str) -> None:
        self._responses.append(text)

    def generate(
        self,
        messages: list[dict],
        schema: dict | None = None,
        max_tokens: int = 512,
    ) -> tuple[str, int]:
        if self._responses:
            text = self._responses.pop(0)
        else:
            # Default to a safe finish action so loops terminate.
            text = json.dumps({"tool": "finish", "args": {"answer": ""}})
        return text, _estimate_tokens(messages, text)


def _estimate_tokens(messages: list[dict], text: str) -> int:
    """Rough token estimate (~4 chars/token) when the server gives no count."""
    chars = len(text) + sum(len(str(m.get("content", ""))) for m in messages)
    return max(1, chars // 4)
