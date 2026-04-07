# Project Guidelines

## Environment & Tooling
- **Runtime:** ${RUNTIME_DISPLAY}
- **Framework:** ${FRAMEWORK_DISPLAY}
- **Language:** ${LANGUAGE}
- **Package Manager:** ${PACKAGE_MANAGER}
- **Port:** ${PORT}
- **Build:** `${BUILD_CMD}` -- only when explicitly requested
- **Dev:** `${DEV_CMD}` -- runs on http://localhost:${PORT}
- **Lint:** `${LINT_CMD}`

## Style & Conventions
${STYLE_CONVENTIONS}
- After edits: `${TYPECHECK_CMD}` to type-check

## Core Principles
- Verify over assume
- Failures first (lead with errors)
- Always re-raise (never swallow exceptions)
- DO NOT OVERCOMPLICATE
- DO NOT OVERSIMPLIFY

## Critical Rules
- NEVER amend commits unless user says 'amend commit'
- NEVER commit files in gitignored directories unless explicitly requested -- DO NOT use git add -f to bypass .gitignore
- Minimal changes; avoid ambiguity; no placeholders
- EFFICIENCY in application performance and user experience -- REFLECT this in EVERY implementation
- `/<command-or-skill-name>` is an explicit enforcement to INVOKE a skill or command, EVEN if you don't see it in your context.
  - You MUST check if a command or skill with that name exists looking in .claude/skills/ and .claude/commands/ directories.
  - If it exists, you MUST EXPLICITLY INVOKE it using the SKILL tool (e.g.: `Skill(skill="mux", args="...")`)

## Infrastructure
- **GCP Projects:** `${STAGE_PROJECT}` (stage), `${PROD_PROJECT}` (prod)
- **Cloud Run Services:** `${STAGE_SERVICE}`, `${PROD_SERVICE}`
- **Config:** `.gcp-setup.yml` -- source of truth for GCP infrastructure
- **Auth:** ${AUTH_DESCRIPTION}
- **Secrets:** GCP Secret Manager (per-secret IAM, never project-level)
- **Deploy:** Cloud Build triggers -- stage via `/gcbrun` PR comment, prod on push to `main`

## Git Workflow
- Base branch: main (not master)
- Never commit to main directly; never amend unless 'amend commit' explicitly requested
- git status returns CWD-relative paths -- use those exact paths with git add

## Conditional Documentation

- **`docs/managing-secrets-and-envs.md`** -- When adding, updating, or rotating secrets/env vars in GCP Secret Manager or Cloud Build configs
