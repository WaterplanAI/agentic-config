---
name: ac-workflow-spec
description: "Core specification workflow engine. Supports CREATE, GATHER/RESEARCH, CONSOLIDATE, SUCCESS_CRITERIA, CONFIRM_SC, PLAN, IMPLEMENT, REVIEW, FIX, TEST, DOCUMENT, SENTINEL, SELF_VALIDATION, and compatibility stages."
project-agnostic: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
---

# Spec Workflow Engine

/skill:ac-workflow-spec STAGE SPEC: strictly follow bundled stage instructions at `../../assets/agents/spec/{STAGE}.md`.

## Supported public stages

- CREATE
- GATHER (compatibility alias to RESEARCH)
- RESEARCH
- CONSOLIDATE
- SUCCESS_CRITERIA
- CONFIRM_SC
- PLAN
- IMPLEMENT
- REVIEW
- FIX
- TEST
- DOCUMENT
- SENTINEL
- SELF_VALIDATION

Compatibility/internal only: PLAN_REVIEW, VALIDATE, VALIDATE_INLINE, AMEND.

## Repository and commit contract

- default project convention: `.specs/specs/<YYYY>/<MM>/<branch>/<NNN>-<title>.md`
- modify only AI section in spec files
- each stage must commit every changed repo
- if both repos changed, commit root repo first and spec repo second
- include repo-scoped commit evidence in stage outputs: `repo_scope`, `root_commit`, `spec_commit`

## Bundled assets

Use package-bundled assets:
- `../../assets/agents/spec/{STAGE}.md`
- `../../assets/scripts/spec-resolver.sh`
- `../../assets/scripts/external-specs.sh`
- `../../assets/scripts/lib/config-loader.sh`
- `../../assets/scripts/lib/source-helpers.sh`
