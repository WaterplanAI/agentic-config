---
name: spec
description: "Core specification workflow engine. Supports CREATE, GATHER/RESEARCH, CONSOLIDATE, SUCCESS_CRITERIA, CONFIRM_SC, PLAN, IMPLEMENT, REVIEW, FIX, TEST, DOCUMENT, SENTINEL, SELF_VALIDATION, and compatibility stages."
project-agnostic: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
  - Skill
---

/spec STAGE SPEC: STRICTLY FOLLOW `${CLAUDE_PLUGIN_ROOT}/agents/spec/{STAGE}.md` using stage + spec path arguments.

## Supported public stages

Primary stages:
- `CREATE`
- `GATHER` (compatibility alias for `RESEARCH`)
- `RESEARCH`
- `CONSOLIDATE`
- `SUCCESS_CRITERIA`
- `CONFIRM_SC`
- `PLAN`
- `IMPLEMENT`
- `REVIEW`
- `FIX`
- `TEST`
- `DOCUMENT`
- `SENTINEL`
- `SELF_VALIDATION`

Compatibility/internal stages may still exist (`PLAN_REVIEW`, `VALIDATE`, `VALIDATE_INLINE`, `AMEND`), but mux-ospec public flows should use the primary stage names above.

## Spec rules

- canonical external-spec path convention: `.specs/specs/<YYYY>/<MM>/<branch>/<NNN>-<title>.md`
- modify AI Section only; never touch Human Section
- every stage must commit every repo it changed
- when both repos change: commit root first, then spec repo via resolver
- stage closeout must include repo-scoped commit evidence (`repo_scope`, `root_commit`, `spec_commit`)

## External spec routing

When specs are external, use:
- `${CLAUDE_PLUGIN_ROOT}/scripts/spec-resolver.sh`
- `${CLAUDE_PLUGIN_ROOT}/scripts/external-specs.sh`
- `${CLAUDE_PLUGIN_ROOT}/scripts/lib/config-loader.sh`
