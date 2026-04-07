---
name: ac-workflow-spec
description: "Core specification workflow engine. Triggers stage agents (CREATE, RESEARCH, PLAN, IMPLEMENT, REVIEW, TEST, etc.) for structured development. Triggers on keywords: spec, specification, plan spec, implement spec, review spec"
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

/skill:ac-workflow-spec STAGE SPEC: STRICTLY FOLLOW the bundled stage instructions in `../../assets/agents/spec/{STAGE}.md` using STAGE AND SPEC as the variables

## Compatibility Note

This pi wrapper preserves the original spec workflow shape while replacing source-plugin-root references with bundled package-local stage-agent and shell-helper assets. In this repository, treat `.specs/specs/` as the canonical destination for committed specs.

## Variables

STAGE=$ARGUMENTS
SPEC=$ARGUMENTS / LAST USED SPEC

## Spec Rules

- Default path in this repository: `.specs/specs/<YYYY>/<MM>/<branch>/<NNN>-<title>.md`
- Modify AI Section only; never touch Human Section
- Commit after each stage: `spec(<NNN>): <STAGE> - <title>`
- One stage = one commit (do NOT bundle multiple stages)

## Bundled Stage Assets

When this workflow refers to stage-agent instructions or helper scripts, use the bundled assets from this pi package:
- `../../assets/agents/spec/{STAGE}.md`
- `../../assets/scripts/spec-resolver.sh`
- `../../assets/scripts/external-specs.sh`
- `../../assets/scripts/lib/config-loader.sh`
- `../../assets/scripts/lib/source-helpers.sh`

## Conditional Documentation

When working with external specs storage, read:
- `../../assets/scripts/spec-resolver.sh`
- `../../assets/scripts/external-specs.sh`
- `../../assets/scripts/lib/config-loader.sh`
