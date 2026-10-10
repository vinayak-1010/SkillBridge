"""SkillBridge web API.

A thin FastAPI wrapper around the existing harness (skillbridge.catalog,
.router, .loop, .backend). It adds no new agent logic: every request routes
through the same scan / route / run_loop / validate functions the CLI uses.

Endpoints:
  GET  /api/health        liveness + whether Ollama is reachable
  GET  /api/skills        list skills (name, description)
  GET  /api/validate      validate skills against the Agent Skills standard
  POST /api/run           run a task; streams progress as Server-Sent Events

This process is meant to run locally, next to Ollama, on the same machine
that has the model pulled -- consistent with SkillBridge's "no GPU, no paid
API, runs on a laptop" design. The static frontend (web/frontend) can be
hosted anywhere (e.g. GitHub Pages) and simply points at this API's URL.

Run:
    pip install -e ".[web]"
    uvicorn web.api.main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import json
import queue
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from skillbridge.backend import DEFAULT_MODEL, OllamaBackend
from skillbridge.catalog import load_body, scan, validate_all
from skillbridge.loop import run as run_loop
from skillbridge.router import route
from skillbridge.trace import Trace

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"

app = FastAPI(title="SkillBridge API", version="0.1.0")

# The frontend is static-hosted (e.g. GitHub Pages) on a different origin
# than this local API, so CORS must allow it. This API is meant to run on
# localhost for a single operator's own use, not as a public multi-tenant
# service -- there is no auth here, by design, matching the CLI's trust
# model. Do not expose this process directly to the public internet.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    task: str
    model: str = DEFAULT_MODEL
    max_steps: int = 8
    token_budget: int = 6000


class SkillOut(BaseModel):
    name: str
    description: str


@app.get("/api/health")
def health() -> dict[str, Any]:
    """Report liveness and whether an Ollama server is reachable."""
    import httpx

    ollama_ok = False
    try:
        resp = httpx.get("http://localhost:11434", timeout=2.0)
        ollama_ok = resp.status_code == 200
    except Exception:
        ollama_ok = False
    return {"status": "ok", "ollama_reachable": ollama_ok}


@app.get("/api/skills", response_model=list[SkillOut])
def list_skills() -> list[SkillOut]:
    skills = scan([SKILLS_DIR])
    return [SkillOut(name=s.name, description=s.description) for s in skills]


@app.get("/api/validate")
def validate() -> dict[str, list[str]]:
    return validate_all([SKILLS_DIR])


def _run_in_thread(req: RunRequest, events: "queue.Queue[dict | None]") -> None:
    """Runs the harness synchronously on a worker thread.

    Each trace event is pushed onto `events` as it happens so the async SSE
    endpoint can forward it to the client immediately. `None` signals the
    run is complete.
    """
    try:
        skills = scan([SKILLS_DIR])
        if not skills:
            events.put({"kind": "error", "message": "No skills found."})
            return

        backend = OllamaBackend(model=req.model)
        events.put({"kind": "routing", "message": f"Routing task to a skill..."})
        skill = route(req.task, skills, backend)
        if skill is None:
            events.put({"kind": "error", "message": "No suitable skill found."})
            return

        events.put({"kind": "routed", "skill": skill.name})
        load_body(skill)

        trace = Trace(on_event=lambda e: events.put(e))
        result = run_loop(
            task=req.task,
            skill=skill,
            backend=backend,
            max_steps=req.max_steps,
            token_budget=req.token_budget,
            trace=trace,
        )
        events.put(
            {
                "kind": "done",
                "answer": result.answer,
                "steps": result.steps,
                "tokens_used": result.tokens_used,
                "finished": result.finished,
                "partial": result.partial,
            }
        )
    except Exception as exc:  # surfaced to the client instead of a bare 500
        events.put({"kind": "error", "message": str(exc)})
    finally:
        events.put(None)


@app.post("/api/run")
async def run_task(req: RunRequest) -> StreamingResponse:
    if not req.task or not req.task.strip():
        raise HTTPException(status_code=400, detail="task must not be empty")

    event_queue: "queue.Queue[dict | None]" = queue.Queue()
    thread = threading.Thread(target=_run_in_thread, args=(req, event_queue), daemon=True)
    thread.start()

    async def event_stream():
        loop = asyncio.get_event_loop()
        while True:
            event = await loop.run_in_executor(None, event_queue.get)
            if event is None:
                break
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
