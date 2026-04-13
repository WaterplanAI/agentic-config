# strict regression checklist

Deterministic yes/no checklist for strict mux protocol regression waves.

## Usage
- Evaluate each item as **PASS** or **FAIL**.
- A strict regression wave is complete only when every required item passes.
- Keep evidence paths project-root-relative.

## A) Leaf-worker contract markers
- [ ] **A01** `mux-subagent` canonical/pi/plugin surfaces explicitly state worker is data-plane only.
  - Files: `canonical/ac-workflow/skills/mux-subagent/body.md`, `canonical/ac-workflow/skills/mux-subagent/body.pi.md`, `packages/pi-ac-workflow/skills/ac-workflow-mux-subagent/SKILL.md`, `plugins/ac-workflow/skills/mux-subagent/SKILL.md`
- [ ] **A02** all `mux-subagent` surfaces keep exact success-response rule: final textual response exactly `0`.
- [ ] **A03** all `mux-subagent` surfaces forbid nested `subagent` calls.
- [ ] **A04** pi/package protocol surfaces forbid worker use of control-plane bridge tools or `report_parent`.
- [ ] **A05** required report shape includes `## Executive Summary` and `### Next Steps`.

## B) Artifact-path contract
- [ ] **B01** declared dispatch `report_path` and `signal_path` are documented as project-root-relative.
- [ ] **B02** transcript artifacts use project-root-relative report/signal/summary paths.
- [ ] **B03** gate examples use `extract-summary.py --evidence --evidence-path <path>` and `verify.py --action gate --summary-evidence <path>`.

## C) Guardrail-layer honesty
- [ ] **C01** docs separate strict runtime enforcement from hook enforcement and worker-protocol prose.
- [ ] **C02** strict runtime is documented as explicit/session-scoped (`session.py --strict-runtime --session-key <key>`).
- [ ] **C03** hook guard is documented as harness-scoped `TaskOutput` denial, not universal runtime behavior.
- [ ] **C04** worker protocol prose is documented as contractual guidance, not automatic runtime enforcement.

## D) Transcript artifact presence and required semantics
- [ ] **D01** `protocol/strict-happy-path-transcript.md` exists in canonical/package/plugin copies.
- [ ] **D02** happy-path transcript shows `DECLARE -> DISPATCH -> VERIFY -> ADVANCE` with `gate_status: advance`.
- [ ] **D03** happy-path transcript includes worker signal creation and final `0` response.
- [ ] **D04** `protocol/strict-blocker-path-transcript.md` exists in canonical/package/plugin copies.
- [ ] **D05** blocker-path transcript shows a real `BLOCK` gate result from missing prerequisite/evidence.
- [ ] **D06** blocker-path transcript shows no manual fallback to `ADVANCE` (illegal transition evidence).

## E) Deferment wording cleanup
- [ ] **E01** `assets/mux/protocol/foundation.md` no longer says transcripts/checklists are deferred.
- [ ] **E02** `assets/mux/README.md` no longer says transcripts/checklists are deferred.
- [ ] **E03** `packages/pi-ac-workflow/README.md` no longer says transcript/checklist protocol artifacts remain deferred.

## F) Canonical/package/plugin sync
- [ ] **F01** canonical generation is clean: `uv run python tools/generate_canonical_wrappers.py --check --plugin ac-workflow`.
- [ ] **F02** package protocol files exist: `subagent.md`, `foundation.md`, `guardrail-policy.md`, `strict-happy-path-transcript.md`, `strict-blocker-path-transcript.md`, `strict-regression-checklist.md`.
- [ ] **F03** plugin protocol files exist: `subagent.md`, `foundation.md`, `guardrail-policy.md`, `strict-happy-path-transcript.md`, `strict-blocker-path-transcript.md`, `strict-regression-checklist.md`.

## G) Minimal validation commands
- [ ] **G01** `uv run pytest tests/test_mux_foundation_assets.py tests/test_canonical_generator.py tests/hooks/test_mux_hooks.py`
- [ ] **G02** changed Python files pass lint + typing (`ruff` + `pyright`).

## H) Runtime invariants
- [ ] **H01** Python regression `test_mux_ledger_rejects_illegal_advancement_from_advance_state` proves `ADVANCE -> ADVANCE` is rejected once gate advancement has already succeeded.
- [ ] **H02** Python regression `test_mux_ledger_blocker_path_never_silently_bypasses` proves missing prerequisite/evidence routes to `BLOCK`, not silent `ADVANCE`.
- [ ] **H03** Python regression `test_mux_ledger_recovery_path_never_silent_fallback` proves protocol-invalid evidence routes to `RECOVER`, not silent `ADVANCE`.
- [ ] **H04** JS regression `strict deactivate re-entry is a no-op` proves `deactivate.py` is re-entry safe for the same session key.
- [ ] **H05** JS regression `strict ledger rejects illegal ADVANCE->ADVANCE transition` proves runtime-ledger enforcement rejects repeated advancement after the control state is already `ADVANCE`.

## Prompt Matrix — Explicit Strict Invocation Cases

| Case | Representative explicit strict invocation | Expected ACK / strict surface | Gate behavior | Objective evidence |
|---|---|---|---|---|
| Happy path | `ac-workflow-mux-ospec` strict run with `session.py --strict-runtime --session-key <key>` and a valid declared dispatch | `MUX_OSPEC_ACK`, strict session init, resolved target spec path, and Stage 001 declaration plan | `gate_status: advance`, `control_state: ADVANCE` | `verify.py --action gate --summary-evidence <path>` succeeds after report + signal + summary evidence |
| Blocker path | Same strict coordinator flow, but prerequisite or summary evidence is missing before gate evaluation | strict surface stays fail-closed; no silent bypass to `ADVANCE` | `gate_status: block`, `control_state: BLOCK` | blocker metadata records the missing prerequisite/evidence and gate denies advancement |
| Recovery path | Same strict coordinator flow, but declared dispatch or summary evidence is protocol-invalid / tampered | strict surface stays fail-closed; no silent fallback to `ADVANCE` | `gate_status: recover`, `control_state: RECOVER` | recovery metadata is recorded and gate denies advancement |
| Illegal advancement | After a verified `ADVANCE`, attempt `ledger.py transition --to ADVANCE` again | explicit illegal-transition rejection, not silent acceptance | repeated advancement is denied and control state remains `ADVANCE` | Python + JS illegal-transition regressions assert the rejection |

## Runtime invariant notes
- **R01** `ADVANCE` is reachable only via a passed gate with valid report + signal + summary evidence.
- **R02** `BLOCK` is entered when prerequisites or evidence are missing; it never silently bypasses.
- **R03** `RECOVER` is entered when protocol invariants are violated; it never silently falls back to `ADVANCE`.
- **R04** Illegal state transitions are rejected explicitly; there is no silent fallback to an earlier or later control state.
- **R05** Deactivation is re-entry safe; calling `deactivate.py` twice for the same session key is a no-op.
