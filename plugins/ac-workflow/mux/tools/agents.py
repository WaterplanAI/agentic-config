#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Agent registry tool for mux orchestrator.

Tracks running agents within a session by storing metadata in .agents/ directory.
Each agent gets a JSON file with its output_file path and metadata.

Usage:
    uv run agents.py register <session_dir> <agent_id> --output <output_file> [--model <model>] [--role <role>]
    uv run agents.py list <session_dir> [--format json|table]
    uv run agents.py get <session_dir> <agent_id>

Examples:
    uv run agents.py register tmp/mux/session researcher-001 --output /tmp/agent-abc.txt --model sonnet --role "Web research"
    uv run agents.py list tmp/mux/session
    uv run agents.py get tmp/mux/session researcher-001
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def register_agent(
    session_dir: Path,
    agent_id: str,
    output_file: str,
    model: str = "sonnet",
    role: str = "",
    task_summary: str = "",
) -> dict:
    """Register an agent in the session registry.

    Args:
        session_dir: Session directory path
        agent_id: Unique agent identifier (e.g., researcher-001)
        output_file: Path to agent's output file (from Task tool)
        model: Model tier (haiku, sonnet, opus)
        role: Agent role description
        task_summary: Brief summary of agent's task

    Returns:
        Agent metadata dict
    """
    agents_dir = session_dir / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "agent_id": agent_id,
        "output_file": output_file,
        "model": model,
        "role": role,
        "task_summary": task_summary,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
    }

    agent_file = agents_dir / f"{agent_id}.json"
    agent_file.write_text(json.dumps(metadata, indent=2) + "\n")

    return metadata


def list_agents(session_dir: Path) -> list[dict]:
    """List all registered agents in session.

    Args:
        session_dir: Session directory path

    Returns:
        List of agent metadata dicts
    """
    agents_dir = session_dir / ".agents"
    if not agents_dir.exists():
        return []

    agents = []
    for agent_file in sorted(agents_dir.glob("*.json")):
        try:
            metadata = json.loads(agent_file.read_text())
            agents.append(metadata)
        except (json.JSONDecodeError, OSError):
            continue

    return agents


def get_agent(session_dir: Path, agent_id: str) -> dict | None:
    """Get specific agent metadata.

    Args:
        session_dir: Session directory path
        agent_id: Agent identifier

    Returns:
        Agent metadata dict or None if not found
    """
    agent_file = session_dir / ".agents" / f"{agent_id}.json"
    if not agent_file.exists():
        return None

    try:
        return json.loads(agent_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manage agent registry for mux sessions"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Register command
    reg_parser = subparsers.add_parser("register", help="Register a new agent")
    reg_parser.add_argument("session_dir", help="Session directory")
    reg_parser.add_argument("agent_id", help="Unique agent identifier")
    reg_parser.add_argument("--output", required=True, help="Agent output file path")
    reg_parser.add_argument("--model", default="sonnet", help="Model tier")
    reg_parser.add_argument("--role", default="", help="Agent role")
    reg_parser.add_argument("--task", default="", help="Task summary")

    # List command
    list_parser = subparsers.add_parser("list", help="List registered agents")
    list_parser.add_argument("session_dir", help="Session directory")
    list_parser.add_argument(
        "--format",
        choices=["json", "table"],
        default="table",
        help="Output format",
    )

    # Get command
    get_parser = subparsers.add_parser("get", help="Get agent metadata")
    get_parser.add_argument("session_dir", help="Session directory")
    get_parser.add_argument("agent_id", help="Agent identifier")

    args = parser.parse_args()
    session_dir = Path(args.session_dir)

    if args.command == "register":
        metadata = register_agent(
            session_dir,
            args.agent_id,
            args.output,
            args.model,
            args.role,
            args.task,
        )
        print(json.dumps(metadata, indent=2))
        return 0

    elif args.command == "list":
        agents = list_agents(session_dir)

        if args.format == "json":
            print(json.dumps(agents, indent=2))
        else:
            # Table format
            if not agents:
                print("No agents registered")
                return 0

            print(f"{'ID':<20} {'Model':<8} {'Role':<30} {'Status':<10}")
            print("-" * 70)
            for agent in agents:
                print(
                    f"{agent['agent_id']:<20} "
                    f"{agent['model']:<8} "
                    f"{agent.get('role', '')[:28]:<30} "
                    f"{agent.get('status', 'unknown'):<10}"
                )
        return 0

    elif args.command == "get":
        agent = get_agent(session_dir, args.agent_id)
        if agent is None:
            print(f"Agent not found: {args.agent_id}", file=sys.stderr)
            return 1
        print(json.dumps(agent, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
