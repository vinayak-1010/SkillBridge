"""Safe tools the model may invoke, plus the sandbox that constrains them.

Tools: read_file, list_dir, http_get, run_script.

The harness owns safety. Each tool call is validated against a SandboxPolicy:
- file reads and directory listings are confined to allowed roots,
- http_get is restricted to an explicit host allowlist,
- run_script executes only files inside the active skill's scripts/ folder,
- scripts run with a hard timeout.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import httpx

# URL allowlist from the spec.
ALLOWED_HOSTS = {"api.github.com", "raw.githubusercontent.com"}
SCRIPT_TIMEOUT_SECONDS = 10


class SandboxError(Exception):
    """Raised when a tool call violates the sandbox policy."""


class ToolError(Exception):
    """Raised when a tool fails for a non-security reason."""


@dataclass
class SandboxPolicy:
    """Describes what the current run is allowed to touch."""

    # Directories under which file reads / listings are permitted.
    read_roots: list[Path] = field(default_factory=list)
    # The active skill's folder; scripts must live under <skill>/scripts/.
    skill_dir: Path | None = None
    allowed_hosts: set[str] = field(default_factory=lambda: set(ALLOWED_HOSTS))
    script_timeout: int = SCRIPT_TIMEOUT_SECONDS

    def resolve_within(self, target: str) -> Path:
        """Resolve `target` and ensure it stays inside an allowed read root."""
        if not self.read_roots:
            raise SandboxError("no read roots configured")
        p = Path(target).expanduser()
        # Resolve against the first read root when relative.
        if not p.is_absolute():
            p = (self.read_roots[0] / p)
        p = p.resolve()
        for root in self.read_roots:
            root_resolved = root.resolve()
            if p == root_resolved or root_resolved in p.parents:
                return p
        raise SandboxError(f"path escapes sandbox: {target}")

    def resolve_script(self, target: str) -> Path:
        """Resolve a script path and ensure it is inside <skill>/scripts/."""
        if self.skill_dir is None:
            raise SandboxError("no active skill for run_script")
        scripts_root = (self.skill_dir / "scripts").resolve()
        p = Path(target).expanduser()
        if not p.is_absolute():
            p = (scripts_root / p)
        p = p.resolve()
        if p != scripts_root and scripts_root not in p.parents:
            raise SandboxError(f"script escapes skill scripts/ folder: {target}")
        if not p.exists():
            raise ToolError(f"script not found: {target}")
        return p

    def check_url(self, url: str) -> None:
        """Ensure the URL host is on the allowlist."""
        from urllib.parse import urlparse

        host = urlparse(url).hostname or ""
        if host not in self.allowed_hosts:
            raise SandboxError(f"host not allowed: {host!r}")


# --- Tool implementations ------------------------------------------------
# Each tool takes (args: dict, policy: SandboxPolicy) and returns a string.


def read_file(args: dict, policy: SandboxPolicy) -> str:
    path = args.get("path")
    if not path:
        raise ToolError("read_file requires 'path'")
    p = policy.resolve_within(str(path))
    if not p.is_file():
        raise ToolError(f"not a file: {path}")
    return p.read_text(encoding="utf-8", errors="replace")


def list_dir(args: dict, policy: SandboxPolicy) -> str:
    path = args.get("path", ".")
    p = policy.resolve_within(str(path))
    if not p.is_dir():
        raise ToolError(f"not a directory: {path}")
    entries = []
    for child in sorted(p.iterdir()):
        suffix = "/" if child.is_dir() else ""
        entries.append(child.name + suffix)
    return "\n".join(entries)


def http_get(args: dict, policy: SandboxPolicy) -> str:
    url = args.get("url")
    if not url:
        raise ToolError("http_get requires 'url'")
    policy.check_url(str(url))
    headers = {"User-Agent": "SkillBridge/0.1"}
    token = args.get("token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = httpx.get(str(url), headers=headers, timeout=15.0, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


def run_script(args: dict, policy: SandboxPolicy) -> str:
    script = args.get("script")
    if not script:
        raise ToolError("run_script requires 'script'")
    p = policy.resolve_script(str(script))
    argv = [sys.executable, str(p)]
    extra = args.get("args") or []
    if isinstance(extra, (list, tuple)):
        argv.extend(str(a) for a in extra)
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=policy.script_timeout,
            cwd=str(policy.skill_dir),
        )
    except subprocess.TimeoutExpired:
        raise ToolError(f"script timed out after {policy.script_timeout}s")
    if proc.returncode != 0:
        raise ToolError(f"script exited {proc.returncode}: {proc.stderr.strip()[:500]}")
    return proc.stdout


TOOLS: dict[str, Callable[[dict, SandboxPolicy], str]] = {
    "read_file": read_file,
    "list_dir": list_dir,
    "http_get": http_get,
    "run_script": run_script,
}
