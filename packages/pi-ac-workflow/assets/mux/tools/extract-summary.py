#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Bounded summary extraction from mux subagent reports.

Default mode keeps the existing human-readable output:
- file metadata
- markdown table of contents
- executive summary section

Phase 003 adds machine-readable evidence output so verify.py can gate on
structured summary artifacts rather than brittle markdown parsing.

Usage:
    uv run extract-summary.py <file>
    uv run extract-summary.py <file> --max-bytes 2048
    uv run extract-summary.py <file> --evidence
    uv run extract-summary.py <file> --evidence-path <path>
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def extract_headers(content: str) -> list[str]:
    """Extract all markdown headers from content."""
    headers: list[str] = []
    for line in content.split("\n"):
        match = re.match(r"^(#{1,6})\s+(.+)", line)
        if match:
            level = len(match.group(1))
            text = match.group(2).strip()
            indent = "  " * (level - 1)
            headers.append(f"{indent}- {text}")
    return headers


def extract_executive_summary(content: str, max_bytes: int) -> tuple[str, bool]:
    """Extract Executive Summary content, capped at max_bytes."""
    lines = content.split("\n")

    exec_start = -1
    exec_end = len(lines)
    for index, line in enumerate(lines):
        if re.match(r"^##\s+Executive Summary", line):
            exec_start = index + 1
            continue
        if exec_start >= 0 and (line.startswith("## ") or line.strip() == "---"):
            exec_end = index
            break

    if exec_start >= 0:
        section_lines = lines[exec_start:exec_end]
        while section_lines and not section_lines[0].strip():
            section_lines.pop(0)
        while section_lines and not section_lines[-1].strip():
            section_lines.pop()

        summary = "\n".join(section_lines)
        if len(summary) > max_bytes:
            summary = summary[:max_bytes]
        return summary, True

    return "", False


def build_summary_evidence(
    *,
    requested_path: str,
    resolved_path: Path,
    content: str,
    max_bytes: int,
) -> dict[str, Any]:
    """Build machine-readable summary evidence payload."""
    stat = resolved_path.stat()
    modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

    executive_summary, summary_found = extract_executive_summary(content, max_bytes)
    headers = extract_headers(content)

    return {
        "report_path": requested_path,
        "resolved_report_path": str(resolved_path),
        "size_bytes": stat.st_size,
        "word_count": len(content.split()),
        "modified_at": modified_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "headers": headers,
        "executive_summary_found": summary_found,
        "executive_summary": executive_summary,
        "executive_summary_bytes": len(executive_summary.encode("utf-8")),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _atomic_write_text(path: Path, content: str) -> None:
    """Atomically write text payload to path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".{path.name}.tmp.{os.getpid()}"
    tmp_path.write_text(content)
    os.replace(str(tmp_path), str(path))


def render_human_summary(evidence: dict[str, Any]) -> str:
    """Render backwards-compatible human-readable summary output."""
    lines: list[str] = [
        "## File Metadata",
        f"- Path: {evidence['resolved_report_path']}",
        f"- Size: {evidence['size_bytes']} bytes",
        f"- Words: {evidence['word_count']}",
        f"- Modified: {evidence['modified_at']}",
        "",
        "## Table of Contents",
    ]

    headers = evidence.get("headers", [])
    if isinstance(headers, list) and headers:
        lines.extend(headers)
    else:
        lines.append("No markdown headers found")

    lines.extend(["", "## Executive Summary"])
    summary_text = evidence.get("executive_summary", "")
    if evidence.get("executive_summary_found") is True and isinstance(summary_text, str):
        lines.append(summary_text if summary_text else "(section present but empty)")
    else:
        lines.append("No Executive Summary section found")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract bounded summary and machine-readable evidence from mux report"
    )
    parser.add_argument(
        "file",
        help="Path to markdown file with TOC + Executive Summary",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=1024,
        help="Maximum Executive Summary size in bytes (default: 1024)",
    )
    parser.add_argument(
        "--metadata",
        action="store_true",
        help="Retained for backwards compatibility; metadata is included by default",
    )
    parser.add_argument(
        "--evidence",
        action="store_true",
        help="Output machine-readable JSON evidence instead of markdown",
    )
    parser.add_argument(
        "--evidence-path",
        type=str,
        help="Optional file path to write machine-readable JSON evidence artifact",
    )

    args = parser.parse_args()
    file_path = Path(args.file).resolve()

    if not file_path.exists():
        print(f"ERROR: File not found: {file_path}", file=sys.stderr)
        return 1

    content = file_path.read_text()
    evidence = build_summary_evidence(
        requested_path=args.file,
        resolved_path=file_path,
        content=content,
        max_bytes=args.max_bytes,
    )

    if args.evidence_path:
        evidence_path = Path(args.evidence_path)
        _atomic_write_text(evidence_path, json.dumps(evidence, indent=2, sort_keys=True) + "\n")

    if args.evidence:
        print(json.dumps(evidence, indent=2, sort_keys=True))
        return 0

    print(render_human_summary(evidence))
    return 0


if __name__ == "__main__":
    sys.exit(main())
