#!/usr/bin/env -S uv run
# /// script
# dependencies = ["typer>=0.9.0", "rich>=13.0.0"]
# requires-python = ">=3.12"
# ///
"""Project type detection for agentic-config bootstrap."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

app = typer.Typer(no_args_is_help=True)
console = Console(stderr=True)

SUPPORTED_TYPES = [
    "typescript", "ts-bun", "python-uv", "python-poetry",
    "python-pip", "rust", "generic",
]


def detect_project_type(target: Path) -> str:
    """Detect project type from file indicators.

    Priority: ts-bun > typescript > python-poetry > python-uv > python-pip > rust > generic
    """
    # Bun (check before typescript for specificity)
    if (target / "bun.lockb").exists():
        return "ts-bun"

    # TypeScript/Node.js
    if (target / "package.json").exists():
        try:
            content = (target / "package.json").read_text()
            if "typescript" in content or "@types" in content:
                return "typescript"
        except OSError:
            pass

    # Python Poetry
    if (target / "pyproject.toml").exists():
        try:
            content = (target / "pyproject.toml").read_text()
            if "[tool.poetry]" in content:
                return "python-poetry"
        except OSError:
            pass

    # Python UV
    if (target / "uv.lock").exists():
        return "python-uv"
    if (target / "pyproject.toml").exists():
        try:
            content = (target / "pyproject.toml").read_text()
            if "[tool.uv]" in content:
                return "python-uv"
        except OSError:
            pass

    # Python pip
    if any((target / f).exists() for f in ["requirements.txt", "setup.py", "setup.cfg"]):
        return "python-pip"

    # Rust
    if (target / "Cargo.toml").exists():
        return "rust"

    return "generic"


def detect_python_tooling(target: Path) -> dict[str, str]:
    """Detect Python type checker and linter from project config.

    Returns dict with keys 'type_checker' and 'linter'.
    Defaults: pyright, ruff.
    """
    type_checker = ""
    linter = ""

    # Check pyproject.toml
    pyproject = target / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text()
            if "[tool.pyright]" in content:
                type_checker = "pyright"
            elif "[tool.mypy]" in content:
                type_checker = "mypy"
            if "[tool.ruff]" in content:
                linter = "ruff"
            elif "[tool.pylint]" in content:
                linter = "pylint"
        except OSError:
            pass

    # Check setup.cfg
    if not type_checker or not linter:
        setup_cfg = target / "setup.cfg"
        if setup_cfg.exists():
            try:
                content = setup_cfg.read_text()
                if not type_checker and "[mypy" in content:
                    type_checker = "mypy"
                if not linter and "[pylint" in content:
                    linter = "pylint"
            except OSError:
                pass

    # Defaults
    if not type_checker:
        type_checker = "pyright"
    if not linter:
        linter = "ruff"

    return {"type_checker": type_checker, "linter": linter}


@app.command()
def detect(
    target: Annotated[Path, typer.Argument(help="Project root path")] = Path("."),
    tooling: Annotated[bool, typer.Option("--tooling", help="Also detect Python tooling")] = False,
) -> None:
    """Detect project type and optionally Python tooling."""
    project_type = detect_project_type(target.resolve())
    console.print(f"type={project_type}")
    if tooling and project_type.startswith("python"):
        tools = detect_python_tooling(target.resolve())
        console.print(f"type_checker={tools['type_checker']}")
        console.print(f"linter={tools['linter']}")


if __name__ == "__main__":
    app()
