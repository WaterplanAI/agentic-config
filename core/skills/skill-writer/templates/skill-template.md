# Skill Template

Comprehensive template for creating new Claude Code skills.

## YAML Frontmatter

```yaml
---
name: {skill-name}
description: {Third-person description of what the skill does}. {Additional capability}. Triggers on keywords: {keyword1}, {keyword2}, {keyword3}
project-agnostic: {true|false}
allowed-tools:
  - {Tool1}
  - {Tool2}
---
```

### Field Requirements

| Field | Constraint | Example |
|-------|------------|---------|
| `name` | Max 64 chars, `/^[a-z0-9-]+$/` | `api-documenter` |
| `description` | Max 1024 chars, third person | See below |
| `project-agnostic` | REQUIRED boolean | `true` or `false` |
| `allowed-tools` | Minimal set needed | `[Read, Glob]` |

### Name Rules
- Lowercase letters, numbers, hyphens only
- No "anthropic" or "claude"
- Prefer gerund form: `processing-pdfs`, `analyzing-code`
- Avoid vague names: `helper`, `utils`, `tool`

### Description Formula
```
[Action verb] + [what it does] + [how/with what]. [Additional capability]. Triggers on keywords: [comma-separated keywords]
```

**Good example:**
```yaml
description: Generates API documentation from source code. Extracts function signatures, docstrings, and usage examples. Triggers on keywords: document API, API docs, generate documentation
```

### Project-Agnostic Guidelines

**Set to `true` when:**
- No project-specific paths or structures
- No project-specific configuration
- Can be copied to any project unchanged

**Set to `false` when:**
- Depends on project directory structure
- Requires project-specific tooling
- Uses project-specific conventions

When `false`, document dependencies in SKILL.md body.

## SKILL.md Body Structure

```markdown
# {Skill Name}

Brief description (1-2 sentences).

## Purpose

What this skill does and when to use it.
- Capability 1
- Capability 2
- Capability 3

## Workflow

### 1. {First Step}
Description of first step.

### 2. {Second Step}
Description of second step.

### 3. {Third Step}
Description of third step.

## Anti-Patterns (NEVER DO)

- Never do X
- Never do Y
- Avoid Z

## Output Format

What the skill produces.

## Supporting Files

- `reference.md` - Detailed documentation
- `examples.md` - Usage examples
```

## Pattern Templates

### Pattern 1: Read-Only Analysis

For skills that only read and analyze.

```yaml
---
name: code-reviewer
description: Performs code review on specified files. Analyzes style, patterns, and potential issues. Triggers on keywords: review code, code review, check code quality
project-agnostic: true
allowed-tools:
  - Read
  - Glob
  - Grep
---

# Code Reviewer

Analyzes code for style, patterns, and issues.

## Purpose

- Review code quality
- Identify anti-patterns
- Suggest improvements

## Workflow

1. Identify target files via Glob
2. Read file contents
3. Analyze patterns and issues
4. Report findings

## Output Format

Markdown report with findings grouped by severity.
```

### Pattern 2: Documentation Generator

For skills that read and write documentation.

```yaml
---
name: api-documenter
description: Generates API documentation from source code. Extracts function signatures, docstrings, and usage examples. Triggers on keywords: document API, API docs, generate documentation
project-agnostic: true
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
---

# API Documenter

Generates API documentation from source code.

## Purpose

- Extract function signatures
- Parse docstrings
- Generate markdown documentation

## Workflow

1. Find source files via Glob
2. Extract documentation
3. Generate markdown
4. Write output files

## Output Format

Markdown files with API reference.
```

### Pattern 3: Multi-File Refactoring

For skills that edit multiple files.

```yaml
---
name: import-organizer
description: Organizes and sorts imports across Python files. Groups stdlib, third-party, and local imports. Triggers on keywords: organize imports, sort imports, fix imports
project-agnostic: true
allowed-tools:
  - Read
  - Edit
  - Glob
  - Grep
---

# Import Organizer

Organizes imports in Python files.

## Purpose

- Sort imports alphabetically
- Group by type (stdlib, third-party, local)
- Remove unused imports

## Workflow

1. Find Python files via Glob
2. Read current imports
3. Sort and group imports
4. Edit files with organized imports

## Output Format

Modified Python files with organized imports.
```

### Pattern 4: Workflow with Bash

For skills that run commands.

```yaml
---
name: test-runner
description: Executes test suites and analyzes results. Runs pytest with coverage and reports failures. Triggers on keywords: run tests, execute tests, test suite
project-agnostic: false
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
---

# Test Runner

Executes tests and reports results.

## Purpose

- Run test suites
- Collect coverage data
- Report failures

## Project Dependencies

This skill requires:
- pytest installed
- Project-specific test configuration
- Coverage configuration (optional)

## Workflow

1. Discover test files
2. Execute pytest
3. Parse results
4. Report summary

## Output Format

Test summary with pass/fail counts and failure details.
```

## Validation Checklist

Before finalizing any skill:

- [ ] Name is max 64 chars
- [ ] Name matches `/^[a-z0-9-]+$/`
- [ ] Name has no reserved words (anthropic, claude)
- [ ] Description is max 1024 chars
- [ ] Description is third person (no I/you/we)
- [ ] Description includes "Triggers on keywords:"
- [ ] `project-agnostic` is explicitly set
- [ ] SKILL.md is under 500 lines
- [ ] Only necessary tools granted
- [ ] All file references one level deep
- [ ] All paths use forward slashes
- [ ] No bash execution pattern in content

## Common Mistakes

1. **Vague descriptions** - Always include specific capabilities and triggers
2. **Too many tools** - Start minimal, add only when needed
3. **Missing project-agnostic** - Always set explicitly
4. **Bloated SKILL.md** - Move reference material to supporting files
5. **Deep nesting** - Keep references one level only
6. **Windows paths** - Always use forward slashes
