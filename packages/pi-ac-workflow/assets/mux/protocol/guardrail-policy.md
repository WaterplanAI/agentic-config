# mux guardrail policy

This document defines the shipped guardrail split for strict mux sessions.

## Purpose
- keep coordinator enforcement, hook enforcement, and worker-protocol prose clearly separated
- prevent docs from overclaiming runtime behavior that is not currently shipped
- give transcript/checklist consumers one authoritative wording baseline

## Guardrail layer matrix

| Layer | Owner | Activation | Enforces | Does not enforce |
| --- | --- | --- | --- | --- |
| Strict runtime | `extensions/strict-mux-runtime/index.js` | Explicit strict bootstrap via `session.py --strict-runtime --session-key <key>` | Coordinator-side strict orchestration constraints: single `subagent` dispatch shape, declared objective/scope/report/signal contract, `no_nested_subagents=true`, strict mux tool allowlist, bounded coordinator write roots, and fail-closed behavior on invalid strict state | Universal worker runtime behavior, universal hook behavior, or automatic worker-output validation outside declared evidence/gate checks |
| Hook guard | `../../assets/mux/subagent-hooks/mux-subagent-guard.py` | Harnesses that support mux-subagent skill-scoped hooks | Fail-closed hook behavior; currently denies `TaskOutput` for mux-subagent workers | Strict-session activation, coordinator ledger transitions, or full worker protocol enforcement in runtimes without this hook surface |
| Worker protocol prose | `../../assets/mux/protocol/subagent.md` plus mux-subagent skill docs | Always, when coordinators dispatch workers under mux protocol | Data-plane contract: report file + signal artifact, exact success response `0`, no nested `subagent`, no control-plane bridge tools or `report_parent`, Executive Summary + Next Steps report shape | Runtime-level automatic enforcement by itself |

## Non-negotiable combined contract
- Strict coordinator flows remain one worker layer only: coordinator -> subagent.
- Declared dispatch `report_path` and `signal_path` remain project-root-relative artifacts.
- `verify.py --action gate` decides `ADVANCE | BLOCK | RECOVER` from report/signal/summary evidence.
- Missing required evidence produces `BLOCK`; inconsistent/invalid evidence produces `RECOVER`.
- Worker chat text is not a replacement for report/signal artifacts.

## Documentation guardrail
When editing mux docs, transcripts, or checklists:
- do not claim that strict runtime alone enforces every worker rule
- do not claim that hook-denied `TaskOutput` is universal in all runtimes
- do not claim worker-side control-plane advancement
- keep the exact `0` success rule explicit on worker surfaces
