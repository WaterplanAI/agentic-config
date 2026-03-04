# ADR-002: Accepted Minor Tradeoffs for v0.2.0 Plugin Architecture

## Status

Accepted

## Date

2026-03-04

## Context

During pull-request review of the v0.2.0 migration branch, the architecture was validated as functionally aligned with Claude Code plugin-native distribution:

- 5-plugin marketplace structure (`ac-workflow`, `ac-git`, `ac-qa`, `ac-tools`, `ac-meta`)
- Plugin-root path resolution via `CLAUDE_PLUGIN_ROOT`
- No active runtime dependency on legacy v0.1.x global/core paths
- Passing structural and marketplace validation suites

The review also identified a small set of residual inconsistencies that are low-risk and mostly documentation/ergonomics debt:

1. `plugins/ac-workflow/agents/spec-command.md` still reflects command-era wording and `./agents/...` style references.
2. `plugins/ac-workflow/skills/spec/SKILL.md` argument variable lines are ambiguous (`STAGE=$ARGUMENTS`, `SPEC=$ARGUMENTS / LAST USED SPEC`).
3. A few spec stage docs reference `agents/spec/...` or `@agents/spec/...` without explicit plugin-root semantics.
4. Documentation language still contains minor command-era wording (for example, "Core Commands") while the architecture is skills-first, with `.claude/commands/ac-release.md` kept as a repository-maintainer exception.

## Decision

These findings are accepted as minor tradeoffs for v0.2.0 and will not block this branch.

No immediate remediation is required before merge, provided current validation and architecture guardrails remain in place.

## Rationale

- Findings are non-blocking and do not represent active runtime regression to v0.1.x behavior.
- Core plugin architecture and isolation checks pass.
- Migration risk from additional late-cycle edits is higher than current impact.
- The identified items are localized and can be cleaned incrementally without architectural rework.

## Consequences

### Positive

- Avoids release churn for low-impact editorial cleanup.
- Preserves stability of the validated v0.2.0 migration set.
- Keeps focus on architecture correctness over cosmetic refactors.

### Negative

- Leaves minor documentation/path-style inconsistency in place.
- Slightly increases onboarding ambiguity for maintainers reading those specific files.
- Creates small follow-up debt for next maintenance cycle.

## Guardrails

- Do not reintroduce v0.1.x runtime dependencies (`AGENTIC_GLOBAL`, `_AGENTIC_ROOT`, `core/...` runtime sourcing).
- Maintain plugin-root path semantics for all new/modified runtime references.
- Treat the accepted items above as debt, not precedent.

## Revisit Triggers

Revisit this ADR and perform cleanup when any of the following occurs:

1. A maintenance pass touches `/spec` orchestration or spec-stage agent docs.
2. Documentation IA updates are made for getting-started or command/skill terminology.
3. A v0.2.x hardening iteration is scheduled specifically for docs/protocol consistency.

## Alternatives Considered

1. **Fix all items immediately in this branch**
   - Rejected: low impact, unnecessary late-cycle churn.
2. **Ignore without ADR**
   - Rejected: tradeoffs should be explicit and discoverable.
3. **Block merge until all are fixed**
   - Rejected: disproportionate to risk and validated runtime behavior.
