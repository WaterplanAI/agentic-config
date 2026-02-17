# Observability Platform

Production monitoring and alerting for swarm sessions.

## Metrics Collected

| Metric | Type | Description |
|--------|------|-------------|
| `swarm_workers_total` | gauge | Total workers in session |
| `swarm_workers_completed` | gauge | Completed workers |
| `swarm_workers_failed` | gauge | Failed workers |
| `swarm_artifacts_bytes` | gauge | Total artifact size |
| `swarm_duration_seconds` | gauge | Session duration |

## Dashboard

```bash
# Start dashboard server
uv run dashboard/server.py --port 8080 --sessions-dir tmp/swarm

# Access at http://localhost:8080
```

## Prometheus Integration

```bash
# Export metrics in Prometheus format
curl http://localhost:8080/api/prometheus

# Or via CLI
uv run .claude/skills/mux/tools/metrics.py export tmp/swarm --format prometheus
```

## Alerting Thresholds

| Condition | Threshold | Action |
|-----------|-----------|--------|
| Session failure rate | >10% | Warning |
| Worker failure rate | >20% | Alert |
| Session duration | >600s | Warning |
| No completions in | 300s | Alert |

## Tools

| Tool | Purpose |
|------|---------|
| `tools/metrics.py collect` | Collect session metrics |
| `tools/metrics.py export` | Export all metrics |
| `tools/metrics.py summary` | Show summary stats |
| `dashboard/server.py` | Web dashboard server |

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard UI |
| `/api/metrics` | GET | All metrics (JSON) |
| `/api/prometheus` | GET | Prometheus format |
| `/api/health` | GET | Health check |
