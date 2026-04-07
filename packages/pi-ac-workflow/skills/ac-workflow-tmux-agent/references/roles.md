# Role Conventions

## Naming

Use stable IDs and role names.

Good examples:

- `chief-of-staff`
- `head-eng`
- `head-research`
- `doer-1`
- `reviewer-1`

Avoid vague names when the hierarchy matters.

## Prompt framing

A spawned agent prompt should usually include:

- role
- mission
- scope limits
- supervisor
- whether it may spawn children
- expected output format

## Suggested defaults

### Chief of Staff

- broader synthesis
- minimal hands-on work
- high compression upward to the human

### Head

- domain ownership
- moderate delegation
- curated summaries upward

### Doer

- narrow scope
- concrete deliverable
- compact reporting
- no broad replanning

## Practical advice

Prefer fewer agents with strong prompts over many agents with weak prompts.
