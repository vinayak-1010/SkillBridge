"""SkillBridge command-line interface.

Commands:
  skillbridge list                 show available skills
  skillbridge run "<task>"         run a task end to end
  skillbridge validate             check skills against the Agent Skills standard
"""

from __future__ import annotations

from pathlib import Path

import typer

from . import __version__
from .backend import DEFAULT_MODEL, OllamaBackend
from .catalog import load_body, scan, validate_all
from .loop import run as run_loop
from .router import route
from .trace import Trace

app = typer.Typer(add_completion=False, help="A reliable local agent harness for small models.")


def _default_skill_dirs() -> list[Path]:
    """Resolve skill directories: ./skills and a package-bundled fallback."""
    dirs = [Path.cwd() / "skills"]
    return [d for d in dirs if d.exists()] or [Path.cwd() / "skills"]


@app.command("list")
def list_skills(
    skills_dir: Path = typer.Option(None, "--skills-dir", help="Directory of skills."),
) -> None:
    """Show the available skills (name and one-line description)."""
    dirs = [skills_dir] if skills_dir else _default_skill_dirs()
    skills = scan(dirs)
    if not skills:
        typer.echo("No skills found.")
        raise typer.Exit(code=0)
    for s in skills:
        typer.echo(f"{s.name}\n    {s.description}")


@app.command("validate")
def validate(
    skills_dir: Path = typer.Option(None, "--skills-dir", help="Directory of skills."),
) -> None:
    """Validate skills against the Agent Skills standard."""
    dirs = [skills_dir] if skills_dir else _default_skill_dirs()
    results = validate_all(dirs)
    if not results:
        typer.echo("No skills found to validate.")
        raise typer.Exit(code=0)

    failures = 0
    for name, errors in results.items():
        if errors:
            failures += 1
            typer.echo(f"FAIL {name}")
            for e in errors:
                typer.echo(f"    - {e}")
        else:
            typer.echo(f"OK   {name}")
    if failures:
        typer.echo(f"\n{failures} skill(s) failed validation.")
        raise typer.Exit(code=1)
    typer.echo("\nAll skills valid.")


@app.command("run")
def run(
    task: str = typer.Argument(..., help="The task to perform."),
    model: str = typer.Option(DEFAULT_MODEL, "--model", help="Ollama model tag."),
    skills_dir: Path = typer.Option(None, "--skills-dir", help="Directory of skills."),
    max_steps: int = typer.Option(8, "--max-steps"),
    token_budget: int = typer.Option(6000, "--budget"),
    trace_path: Path = typer.Option(None, "--trace", help="Write a JSONL trace here."),
) -> None:
    """Run a task end to end: route to a skill, then execute the loop."""
    dirs = [skills_dir] if skills_dir else _default_skill_dirs()
    skills = scan(dirs)
    if not skills:
        typer.echo("No skills found.")
        raise typer.Exit(code=1)

    backend = OllamaBackend(model=model)
    skill = route(task, skills, backend)
    if skill is None:
        typer.echo("No suitable skill found.")
        raise typer.Exit(code=1)

    typer.echo(f"-> skill: {skill.name}")
    load_body(skill)
    trace = Trace(trace_path) if trace_path else Trace()

    result = run_loop(
        task=task,
        skill=skill,
        backend=backend,
        max_steps=max_steps,
        token_budget=token_budget,
        trace=trace,
    )
    typer.echo("")
    typer.echo(result.answer)
    typer.echo("")
    status = "finished" if result.finished else ("partial" if result.partial else "stopped")
    typer.echo(f"[{status}] steps={result.steps} tokens={result.tokens_used}")


@app.command("version")
def version() -> None:
    """Print the SkillBridge version."""
    typer.echo(__version__)


if __name__ == "__main__":
    app()
