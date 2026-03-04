#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
"""
Parse agent metadata from YAML frontmatter.

Extracts metadata without loading full agent definition for progressive context management.
Target: 70% startup token reduction (22KB -> 7KB).

Usage:
    uv run parse-agent-metadata.py <agent_file>
    uv run parse-agent-metadata.py --all --agents-dir <path>
    uv run parse-agent-metadata.py --json

Output:
    name: researcher
    role: Web research and synthesis
    tier: medium
    model: sonnet
    triggers: research required, web search needed, external information
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


def parse_frontmatter(file_path: Path) -> dict[str, Any] | None:
    """Extract YAML frontmatter from markdown file.

    Args:
        file_path: Path to agent definition file

    Returns:
        Parsed frontmatter dict or None if no frontmatter
    """
    content = file_path.read_text()

    # Check for frontmatter delimiter
    if not content.startswith("---"):
        return None

    # Find closing delimiter
    lines = content.split("\n")
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return None

    # Parse YAML
    frontmatter_text = "\n".join(lines[1:end_idx])
    try:
        return yaml.safe_load(frontmatter_text)
    except yaml.YAMLError:
        return None


def get_all_agent_metadata(agents_dir: Path) -> dict[str, dict[str, Any]]:
    """Get metadata for all agents in directory.

    Args:
        agents_dir: Directory containing agent .md files

    Returns:
        Dict mapping agent name to metadata
    """
    result = {}
    for agent_file in sorted(agents_dir.glob("*.md")):
        metadata = parse_frontmatter(agent_file)
        if metadata and "name" in metadata:
            result[metadata["name"]] = metadata
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse agent metadata from YAML frontmatter"
    )
    parser.add_argument(
        "agent_file",
        nargs="?",
        type=Path,
        help="Path to agent definition file",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Parse all agents in directory",
    )
    parser.add_argument(
        "--agents-dir",
        type=Path,
        default=Path(__file__).parent.parent / "agents",
        help="Directory containing agent definitions",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    args = parser.parse_args()

    if args.all:
        metadata = get_all_agent_metadata(args.agents_dir)
        if args.json:
            print(json.dumps(metadata, indent=2))
        else:
            for name, data in metadata.items():
                triggers = ", ".join(data.get("triggers", []))
                print(
                    f"{name}: {data.get('role', 'unknown')} ({data.get('tier', 'unknown')}) [{triggers}]"
                )
        return 0

    if not args.agent_file:
        parser.print_help()
        return 1

    metadata = parse_frontmatter(args.agent_file)
    if metadata is None:
        print(f"No frontmatter found in {args.agent_file}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(metadata, indent=2))
    else:
        for key, value in metadata.items():
            if isinstance(value, list):
                value = ", ".join(value)
            print(f"{key}: {value}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
