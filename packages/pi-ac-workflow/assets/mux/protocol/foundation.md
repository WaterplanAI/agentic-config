# pi-adapted mux foundation

This document is the shared foundation contract for the pi mux family.

## Locked runtime assumptions
- Session state lives under project-local `tmp/mux/<session>/`.
- Completion signals are explicit files under `.signals/`; they are not implied by worker chat output.
- Report files are the authoritative worker artifact.
- Coordinator depth stays at one worker layer: coordinator -> subagent.
- User approvals happen in the main chat when a real product or scope decision appears.
- Voice alerts use the current runtime `say` tool when a later orchestrator explicitly asks for them.

## Shared helper entry points
- `../../assets/mux/tools/session.py`
- `../../assets/mux/tools/signal.py`
- `../../assets/mux/tools/check-signals.py`
- `../../assets/mux/tools/verify.py`
- `../../assets/mux/tools/extract-summary.py`
- `../../assets/mux/tools/agents.py`
- `../../assets/mux/tools/deactivate.py`

## Boundary for later phases
- This foundation does not claim automatic task-notification support.
- This foundation does not claim nested skill loading inside workers.
- This foundation does not claim generic shared runtime parity beyond the mux-specific file/session protocol described here.
- Phase 008 should consume this asset root and protocol, not recreate local copies of the same helpers.
