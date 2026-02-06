#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Wait for push events from a MUX signal hub.

Falls back to file counting when no hub metadata exists.
"""

import argparse
import json
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def count_signals(signals_dir: Path) -> tuple[int, int]:
    if not signals_dir.exists():
        return (0, 0)
    return (len(list(signals_dir.glob("*.done"))), len(list(signals_dir.glob("*.fail"))))


def wait_via_files(session_dir: Path, expected: int, timeout: float, interval: float) -> int:
    signals_dir = session_dir / ".signals"
    start = time.time()
    while time.time() - start < timeout:
        complete, failed = count_signals(signals_dir)
        total = complete + failed
        if total >= expected:
            print(json.dumps({
                "source": "files",
                "complete": complete,
                "failed": failed,
                "status": "success" if failed == 0 else "partial",
                "elapsed": round(time.time() - start, 2),
                "detected_at": datetime.now(timezone.utc).isoformat(),
            }))
            return 0
        time.sleep(interval)
    complete, failed = count_signals(signals_dir)
    print(json.dumps({
        "source": "files",
        "complete": complete,
        "failed": failed,
        "status": "timeout",
        "elapsed": round(time.time() - start, 2),
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }))
    return 1


def wait_via_hub(
    session_dir: Path,
    expected: int,
    timeout: float,
    phase: str | None,
    status: str | None,
    event_type: str,
) -> int:
    meta_path = session_dir / ".signal-bus.json"
    if not meta_path.exists():
        return wait_via_files(session_dir, expected=expected, timeout=timeout, interval=2.0)

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    token = meta["token"]
    socket_path = meta.get("socket_path")
    host = meta.get("host")
    port = meta.get("port")

    filters: dict[str, str] = {}
    if phase:
        filters["phase"] = phase
    if status:
        filters["status"] = status
    if event_type:
        filters["type"] = event_type

    start = time.time()
    seen = 0

    if socket_path:
        conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        conn.settimeout(5.0)
        conn.connect(socket_path)
    elif host and port:
        conn = socket.create_connection((host, int(port)), timeout=5.0)
    else:
        raise RuntimeError("No usable hub endpoint in metadata")

    with conn:
        conn.settimeout(0.5)
        subscribe_msg = {"op": "subscribe", "token": token, "filters": filters}
        conn.sendall((json.dumps(subscribe_msg) + "\n").encode())

        # Read subscription ACK
        ack = conn.recv(8192).decode().strip()
        if not ack:
            raise RuntimeError("No ACK from signal hub")
        ack_payload = json.loads(ack.splitlines()[0])
        if not ack_payload.get("ok"):
            raise RuntimeError(f"Hub subscription denied: {ack_payload}")

        while time.time() - start < timeout:
            try:
                raw = conn.recv(65536)
            except socket.timeout:
                continue
            if not raw:
                break
            for line in raw.decode().splitlines():
                if not line.strip():
                    continue
                payload = json.loads(line)
                if payload.get("type") == "event":
                    seen += 1
                    if seen >= expected:
                        print(json.dumps({
                            "source": "hub",
                            "received": seen,
                            "status": "success",
                            "elapsed": round(time.time() - start, 2),
                            "detected_at": datetime.now(timezone.utc).isoformat(),
                        }))
                        return 0

    print(json.dumps({
        "source": "hub",
        "received": seen,
        "status": "timeout",
        "elapsed": round(time.time() - start, 2),
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }))
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Wait for MUX signals via push hub or file fallback")
    parser.add_argument("session_dir", help="Session directory containing .signals/")
    parser.add_argument("--expected", type=int, required=True, help="Number of matching events to wait for")
    parser.add_argument("--timeout", type=float, default=300, help="Max seconds to wait")
    parser.add_argument("--phase", help="Filter by event phase")
    parser.add_argument("--status", choices=["success", "fail"], help="Filter by event status")
    parser.add_argument("--type", dest="event_type", default="signal", help="Filter by event type")
    args = parser.parse_args()

    session_dir = Path(args.session_dir)
    try:
        return wait_via_hub(
            session_dir=session_dir,
            expected=args.expected,
            timeout=args.timeout,
            phase=args.phase,
            status=args.status,
            event_type=args.event_type,
        )
    except Exception as exc:
        print(f"warning: hub wait failed ({exc}), falling back to files", file=sys.stderr)
        return wait_via_files(session_dir, expected=args.expected, timeout=args.timeout, interval=2.0)


if __name__ == "__main__":
    sys.exit(main())
