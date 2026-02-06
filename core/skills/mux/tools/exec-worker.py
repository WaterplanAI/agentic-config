#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Executor for MUX worker agents.

Wraps a shell command to strictly enforce the MUX signaling protocol.
Executes the command, captures exit status, and automatically generates
the correct .done/.fail signal file with metadata.

Usage:
    uv run exec-worker.py --command "gemini -p '...'" --signal-path .signals/001.done --output-path outputs/001.md
"""

import argparse
import json
import os
import shlex
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def atomic_write(path: Path, content: str):
    """Atomically write content to file using write-temp-rename pattern."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".{path.name}.tmp.{os.getpid()}"
    tmp_path.write_text(content)
    os.replace(str(tmp_path), str(path))


def publish_event(signal_path: Path, output_path: Path, status: str, error: str | None) -> bool:
    """Publish event to push signal hub if session metadata exists."""
    if signal_path.parent.name != ".signals":
        return False

    session_dir = signal_path.parent.parent
    meta_path = session_dir / ".signal-bus.json"
    if not meta_path.exists():
        return False

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        token = meta["token"]
        socket_path = meta.get("socket_path")
        host = meta.get("host")
        port = meta.get("port")

        event = {
            "type": "signal",
            "session_dir": str(session_dir),
            "signal_path": str(signal_path),
            "output_path": str(output_path),
            "status": status,
            "error": error,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        payload = {"op": "publish", "token": token, "event": event}
        if socket_path:
            conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            conn.settimeout(2.0)
            conn.connect(socket_path)
        elif host and port:
            conn = socket.create_connection((host, int(port)), timeout=2.0)
        else:
            return False
        with conn:
            conn.sendall((json.dumps(payload) + "\n").encode())
            ack = conn.recv(8192).decode().strip()
            return bool(ack and json.loads(ack.splitlines()[0]).get("ok"))
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute worker command and emit MUX signal")
    parser.add_argument("--command", required=True, help="Shell command to execute")
    parser.add_argument("--signal-path", required=True, help="Path to signal file")
    parser.add_argument("--output-path", required=True, help="Path to output file")
    parser.add_argument("--log-path", help="Path to write stdout/stderr")
    
    args = parser.parse_args()
    
    signal_path = Path(args.signal_path)
    output_path = Path(args.output_path)
    
    print(f"[{datetime.now().time()}] Starting: {args.command}")
    
    # Open log file if specified
    log_file = open(args.log_path, "w") if args.log_path else None
    
    start_time = time.time()
    try:
        # Execute command
        result = subprocess.run(
            args.command,
            shell=True,
            stdout=log_file if log_file else None,
            stderr=subprocess.STDOUT if log_file else None,
            text=True
        )
        return_code = result.returncode
    except Exception as e:
        return_code = 1
        if log_file:
            log_file.write(f"\nExecution Error: {str(e)}\n")
        else:
            print(f"Execution Error: {e}", file=sys.stderr)
    finally:
        if log_file:
            log_file.close()

    duration = time.time() - start_time
    status = "success" if return_code == 0 else "fail"
    
    # Determine final signal filename
    if status == "success":
        final_signal_path = signal_path.with_suffix(".done")
    else:
        final_signal_path = signal_path.with_suffix(".fail")
        
    # Generate signal content
    content = [
        f"path: {args.output_path}",
        f"status: {status}",
        f"command: {args.command}",
        f"duration: {duration:.2f}s",
        f"created_at: {datetime.now(timezone.utc).isoformat()}"
    ]
    
    error_msg = None
    if status == "fail":
        error_msg = f"Command failed with exit code {return_code}"
        content.append(f"error: {error_msg}")
        if args.log_path:
            content.append(f"log: {args.log_path}")

    # Write signal
    atomic_write(final_signal_path, "\n".join(content) + "\n")
    
    # Push to bus
    publish_event(final_signal_path, output_path, status, error_msg)
    
    print(f"[{datetime.now().time()}] Finished ({status}). Signal: {final_signal_path}")
    return return_code

if __name__ == "__main__":
    sys.exit(main())
