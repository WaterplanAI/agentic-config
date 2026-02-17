# A2A Integration

A2A (Agent-to-Agent) protocol enables external orchestration while preserving internal signal architecture.

## Architecture

```
External A2A Clients          Internal Swarm Workflow
        |                              |
        v                              |
+------------------+                   |
|   A2A Server     |<----------------->|
|  (JSON-RPC 2.0)  |                   |
+--------+---------+                   |
         |                             |
         v                             |
+------------------+                   |
|  Task Manager    |                   |
|  (Session Map)   |                   |
+--------+---------+                   |
         |                             v
+------------------+       +------------------+
| Signal Protocol  |<----->|  Swarm Engine    |
|   (Internal)     |       |   (Unchanged)    |
+------------------+       +------------------+
```

**Key Principle**: Internal signal protocol unchanged. A2A is external interface ONLY.

## Starting the Server

```bash
# Generate auth token
uv run .claude/skills/swarm/a2a/auth.py generate

# Start server
uv run .claude/skills/swarm/a2a/server.py
```

## Client Usage

```python
from a2a.client import A2AClient

client = A2AClient("http://localhost:8000", token="your-token")
task = client.send_task("Research AI orchestration patterns")
result = client.wait_for_completion(task["id"])
print(result["artifacts"])
```

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/.well-known/agent.json` | GET | Agent Card discovery |
| `/a2a` | POST | JSON-RPC 2.0 (tasks/send, tasks/get, tasks/cancel) |
