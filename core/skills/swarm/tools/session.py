#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Session directory creation tool for swarm orchestrator.

Creates the standard session directory structure with all required subdirectories.

Usage:
    uv run session.py <topic_slug>
    uv run session.py <topic_slug> --base tmp/swarm

Output (stdout):
    SESSION_DIR=tmp/swarm/20260129-1500-topic
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create swarm session directory structure"
    )
    parser.add_argument(
        "topic_slug",
        help="Topic slug for session ID (e.g., 'auth-research')",
    )
    parser.add_argument(
        "--base",
        default="tmp/swarm",
        help="Base directory for swarm sessions (default: tmp/swarm)",
    )

    args = parser.parse_args()

    # Generate session ID: YYYYMMDD-HHMM-topic
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    session_id = f"{timestamp}-{args.topic_slug}"
    session_dir = Path(args.base) / session_id

    # Create directory structure
    subdirs = ["research", "audits", "consolidated", ".signals"]
    for subdir in subdirs:
        (session_dir / subdir).mkdir(parents=True, exist_ok=True)

    # Output for shell consumption
    print(f"SESSION_DIR={session_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
