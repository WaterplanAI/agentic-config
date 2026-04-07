# mux foundation assets

This tree is the shared mux runtime substrate for canonical `ac-workflow` mux surfaces.

## Purpose
- keep session/signal/report helpers in one package-owned location
- give pi and Claude mux surfaces one stable asset root
- let later mux orchestrators consume shared protocol docs instead of inventing local copies

## Layout
- `tools/` — session, signal, verification, and bounded-summary helpers
- `subagent-hooks/` — subagent-only hook guards for harnesses that support skill-scoped hooks
- `protocol/` — pi-adapted foundation and worker-protocol reference docs

## Current rendered root
- `${CLAUDE_PLUGIN_ROOT}/mux`

The generator resolves `${CLAUDE_PLUGIN_ROOT}/mux` per harness so wrappers can reference one logical foundation root while the copied assets land in the correct package or plugin path for the current render.
