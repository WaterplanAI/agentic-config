#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["fastapi>=0.100", "uvicorn>=0.23"]
# ///
"""
Observability Dashboard Server.

Serves metrics API and dashboard UI.
Target: Handle 50 concurrent sessions, >99.5% uptime.

Usage:
    uv run dashboard/server.py
    uv run dashboard/server.py --port 8080 --sessions-dir tmp/swarm

Endpoints:
    GET /               - Dashboard UI
    GET /api/metrics    - All session metrics (JSON)
    GET /api/prometheus - Prometheus format metrics
    GET /api/health     - Health check
"""

import argparse
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

# Import metrics module (same directory parent)
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
from metrics import collect_session_metrics, export_prometheus

app = FastAPI(title="Swarm Observability Dashboard", version="1.0.0")

# Configuration - set via CLI args or defaults
SESSIONS_DIR = Path("tmp/swarm")
DASHBOARD_DIR = Path(__file__).parent
MAX_SESSIONS = 50


@app.get("/")
async def dashboard() -> FileResponse:
    """Serve dashboard HTML."""
    return FileResponse(DASHBOARD_DIR / "index.html")


@app.get("/api/metrics")
async def get_metrics() -> JSONResponse:
    """Return all session metrics as JSON."""
    sessions = []
    session_dirs = sorted(
        SESSIONS_DIR.glob("*-*-*"), key=lambda p: p.name, reverse=True
    )

    for session_dir in session_dirs[:MAX_SESSIONS]:
        if session_dir.is_dir():
            sessions.append(collect_session_metrics(session_dir))

    return JSONResponse({"sessions": sessions})


@app.get("/api/prometheus")
async def get_prometheus() -> PlainTextResponse:
    """Return metrics in Prometheus exposition format."""
    sessions = []
    session_dirs = sorted(
        SESSIONS_DIR.glob("*-*-*"), key=lambda p: p.name, reverse=True
    )

    for session_dir in session_dirs[:MAX_SESSIONS]:
        if session_dir.is_dir():
            sessions.append(collect_session_metrics(session_dir))

    return PlainTextResponse(export_prometheus(sessions), media_type="text/plain")


@app.get("/api/health")
async def health() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({"status": "healthy", "sessions_dir": str(SESSIONS_DIR)})


def main() -> int:
    global SESSIONS_DIR, MAX_SESSIONS

    parser = argparse.ArgumentParser(description="Swarm observability dashboard server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8080, help="Bind port")
    parser.add_argument(
        "--sessions-dir",
        type=Path,
        default=Path("tmp/swarm"),
        help="Sessions base directory",
    )
    parser.add_argument(
        "--max-sessions", type=int, default=50, help="Max sessions to display"
    )

    args = parser.parse_args()
    SESSIONS_DIR = args.sessions_dir
    MAX_SESSIONS = args.max_sessions

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
