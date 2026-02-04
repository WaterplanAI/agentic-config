#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Detect project test framework/stack for adaptive test execution.

Detects: Jest, Vitest, Playwright, Pytest, CDK, Terraform
Returns structured JSON with lint/unit/e2e commands.

Usage:
    uv run detect-repo-type.py [--path <project_path>] [--format json|text]

Examples:
    uv run detect-repo-type.py
    uv run detect-repo-type.py --path /path/to/project
    uv run detect-repo-type.py --format text
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict


class FrameworkResult(TypedDict):
    framework: str
    lint_cmd: str | None
    unit_cmd: str | None
    e2e_cmd: str | None
    detected_at: str


def parse_package_json(pkg_path: Path) -> dict:
    """Parse package.json and return contents."""
    try:
        return json.loads(pkg_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def parse_pyproject_toml(pyproject_path: Path) -> dict:
    """Parse pyproject.toml and check for pytest dependency."""
    try:
        content = pyproject_path.read_text()
        # Simple check for pytest in dependencies
        return {"has_pytest": "pytest" in content.lower()}
    except OSError:
        return {}


def detect_framework(project_path: Path) -> FrameworkResult:
    """Detect project test framework based on config files.

    Priority order (first match wins):
    1. CDK (cdk.json)
    2. Terraform (terraform/ directory)
    3. Vitest (package.json devDeps)
    4. Jest (package.json devDeps)
    5. Playwright (package.json devDeps)
    6. Pytest (pyproject.toml)
    7. Unknown (fallback)

    Args:
        project_path: Root directory of the project

    Returns:
        FrameworkResult with framework name and test commands
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # CDK detection (highest priority for infra projects)
    if (project_path / "cdk.json").exists():
        return {
            "framework": "cdk",
            "lint_cmd": "cdk synth",
            "unit_cmd": "pytest infra/tests/",
            "e2e_cmd": None,
            "detected_at": timestamp,
        }

    # Terraform detection
    if (project_path / "terraform").is_dir() or any(
        project_path.glob("*.tf")
    ):
        return {
            "framework": "terraform",
            "lint_cmd": "terraform validate",
            "unit_cmd": "terraform plan",
            "e2e_cmd": None,
            "detected_at": timestamp,
        }

    # Node.js/TypeScript projects (check package.json)
    pkg_path = project_path / "package.json"
    if pkg_path.exists():
        pkg = parse_package_json(pkg_path)
        deps = pkg.get("devDependencies", {})
        deps.update(pkg.get("dependencies", {}))

        # Vitest detection
        if "vitest" in deps:
            return {
                "framework": "vitest",
                "lint_cmd": "tsc --noEmit",
                "unit_cmd": "npm test",
                "e2e_cmd": "npx playwright test" if "@playwright/test" in deps else None,
                "detected_at": timestamp,
            }

        # Jest detection
        if "jest" in deps:
            return {
                "framework": "jest",
                "lint_cmd": "tsc --noEmit",
                "unit_cmd": "npm test",
                "e2e_cmd": "npx playwright test" if "@playwright/test" in deps else None,
                "detected_at": timestamp,
            }

        # Playwright-only detection (e2e focused project)
        if "@playwright/test" in deps:
            return {
                "framework": "playwright",
                "lint_cmd": "tsc --noEmit",
                "unit_cmd": None,
                "e2e_cmd": "npx playwright test",
                "detected_at": timestamp,
            }

    # Python projects (check pyproject.toml)
    pyproject_path = project_path / "pyproject.toml"
    if pyproject_path.exists():
        pyproject = parse_pyproject_toml(pyproject_path)
        if pyproject.get("has_pytest"):
            return {
                "framework": "pytest",
                "lint_cmd": "ruff check && pyright",
                "unit_cmd": "pytest -m unit",
                "e2e_cmd": "pytest -m e2e",
                "detected_at": timestamp,
            }

    # Fallback for unknown projects
    return {
        "framework": "unknown",
        "lint_cmd": None,
        "unit_cmd": None,
        "e2e_cmd": None,
        "detected_at": timestamp,
    }


def format_text_output(result: FrameworkResult) -> str:
    """Format result as human-readable text."""
    lines = [
        f"framework: {result['framework']}",
        f"lint_cmd: {result['lint_cmd'] or 'N/A'}",
        f"unit_cmd: {result['unit_cmd'] or 'N/A'}",
        f"e2e_cmd: {result['e2e_cmd'] or 'N/A'}",
        f"detected_at: {result['detected_at']}",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect project test framework/stack"
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=Path.cwd(),
        help="Project path to analyze (default: current directory)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json)",
    )

    args = parser.parse_args()
    project_path = args.path.resolve()

    if not project_path.exists():
        print(f"ERROR: Path not found: {project_path}", file=sys.stderr)
        return 1

    if not project_path.is_dir():
        print(f"ERROR: Path is not a directory: {project_path}", file=sys.stderr)
        return 1

    result = detect_framework(project_path)

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(format_text_output(result))

    return 0


if __name__ == "__main__":
    sys.exit(main())
