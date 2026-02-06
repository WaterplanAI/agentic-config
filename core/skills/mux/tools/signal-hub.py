#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Push signal hub for MUX sessions.

Protocol: newline-delimited JSON over Unix domain socket.

Client messages:
  {"op":"subscribe","token":"...","filters":{"status":"success"}}
  {"op":"publish","token":"...","event":{...}}
  {"op":"ping","token":"..."}
"""

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Subscriber:
    writer: asyncio.StreamWriter
    filters: dict[str, str]


class SignalHub:
    """Session-scoped event fanout service with durable append log."""

    def __init__(self, session_dir: Path, token: str):
        self.session_dir = session_dir
        self.token = token
        self.log_path = session_dir / ".signals" / "events.ndjson"
        self.subscribers: dict[int, Subscriber] = {}
        self._next_sub_id = 1
        self._log_lock = asyncio.Lock()
        self._server: asyncio.AbstractServer | None = None

    async def _send_json(self, writer: asyncio.StreamWriter, payload: dict) -> None:
        writer.write((json.dumps(payload) + "\n").encode())
        await writer.drain()

    def _matches(self, event: dict, filters: dict[str, str]) -> bool:
        for key, expected in filters.items():
            if str(event.get(key, "")) != str(expected):
                return False
        return True

    async def _append_event(self, event: dict) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        async with self._log_lock:
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, ensure_ascii=True) + "\n")

    async def _broadcast(self, event: dict) -> None:
        dead: list[int] = []
        for sub_id, sub in self.subscribers.items():
            if not self._matches(event, sub.filters):
                continue
            try:
                await self._send_json(sub.writer, {"type": "event", "event": event})
            except Exception:
                dead.append(sub_id)
        for sub_id in dead:
            sub = self.subscribers.pop(sub_id, None)
            if sub is not None:
                try:
                    sub.writer.close()
                    await sub.writer.wait_closed()
                except Exception:
                    pass

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        subscriber_id: int | None = None
        try:
            while True:
                raw = await reader.readline()
                if not raw:
                    break
                try:
                    msg = json.loads(raw.decode().strip())
                except json.JSONDecodeError:
                    await self._send_json(writer, {"ok": False, "error": "invalid-json"})
                    continue

                if msg.get("token") != self.token:
                    await self._send_json(writer, {"ok": False, "error": "unauthorized"})
                    continue

                op = msg.get("op")
                if op == "ping":
                    await self._send_json(writer, {"ok": True, "pong": True})
                    continue

                if op == "subscribe":
                    filters = msg.get("filters", {})
                    if not isinstance(filters, dict):
                        await self._send_json(writer, {"ok": False, "error": "filters-must-be-object"})
                        continue
                    subscriber_id = self._next_sub_id
                    self._next_sub_id += 1
                    self.subscribers[subscriber_id] = Subscriber(writer=writer, filters=filters)
                    await self._send_json(writer, {"ok": True, "subscribed": subscriber_id})
                    continue

                if op == "publish":
                    event = msg.get("event")
                    if not isinstance(event, dict):
                        await self._send_json(writer, {"ok": False, "error": "event-must-be-object"})
                        continue
                    event.setdefault("published_at", datetime.now(timezone.utc).isoformat())
                    await self._append_event(event)
                    await self._broadcast(event)
                    await self._send_json(writer, {"ok": True, "published": True})
                    continue

                await self._send_json(writer, {"ok": False, "error": "unknown-op"})
        finally:
            if subscriber_id is not None:
                self.subscribers.pop(subscriber_id, None)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def start_unix(self, socket_path: Path) -> str:
        socket_path.parent.mkdir(parents=True, exist_ok=True)
        if socket_path.exists():
            socket_path.unlink()
        self._server = await asyncio.start_unix_server(
            self._handle_client, path=str(socket_path)
        )
        return str(socket_path)

    async def serve_forever(self) -> None:
        if self._server is None:
            raise RuntimeError("Signal hub server not started")
        async with self._server:
            await self._server.serve_forever()

def main() -> int:
    parser = argparse.ArgumentParser(description="Run push signal hub for a MUX session")
    parser.add_argument("--session-dir", required=True, help="MUX session directory")
    parser.add_argument("--token", required=True, help="Shared auth token")
    parser.add_argument(
        "--socket-path",
        help="Unix socket path (default: <session>/.signals/signal-bus.sock)",
    )
    parser.add_argument("--meta-file", required=True, help="Where to write hub metadata JSON")
    args = parser.parse_args()

    session_dir = Path(args.session_dir)
    meta_file = Path(args.meta_file)
    hub = SignalHub(session_dir=session_dir, token=args.token)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _run() -> int:
        socket_path = Path(args.socket_path) if args.socket_path else session_dir / ".signals" / "signal-bus.sock"
        bound_socket = await hub.start_unix(socket_path)
        meta_file.parent.mkdir(parents=True, exist_ok=True)
        meta = {
            "socket_path": bound_socket,
            "token": args.token,
            "pid": os.getpid(),
            "session_dir": str(session_dir),
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        meta_file.write_text(json.dumps(meta) + "\n", encoding="utf-8")

        await hub.serve_forever()
        return 0

    try:
        return loop.run_until_complete(_run())
    except KeyboardInterrupt:
        return 0
    finally:
        loop.close()


if __name__ == "__main__":
    sys.exit(main())
