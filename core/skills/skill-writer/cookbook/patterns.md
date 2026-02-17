# Patterns Cookbook

Common skill patterns with examples.

## Read-Only Analysis

Skills that read and analyze code without modifications.

```yaml
---
name: python-import-analyzer
description: Analyzes Python import statements and detects circular dependencies. Triggers on keywords: python imports, circular dependency, import analysis
project-agnostic: true
allowed-tools:
  - Read
  - Glob
  - Grep
---
```

**Tools rationale:**
- `Read`: Read Python files
- `Glob`: Find Python files by pattern
- `Grep`: Search for import statements

## Code Modification

Skills that edit existing code.

```yaml
---
name: python-type-annotator
description: Adds type annotations to Python functions. Infers types from usage and docstrings. Triggers on keywords: add types, type hints, annotate python
project-agnostic: true
allowed-tools:
  - Read
  - Edit
  - Glob
---
```

**Tools rationale:**
- `Read`: Read Python files to analyze
- `Edit`: Modify files with type hints
- `Glob`: Find Python files

**Why not Write:** Edit is safer for modifications (exact string replacement).

## Documentation Generation

Skills that create new documentation files.

```yaml
---
name: api-doc-generator
description: Generates API documentation from code comments. Creates markdown files with endpoint descriptions. Triggers on keywords: api docs, generate documentation, api reference
project-agnostic: false
allowed-tools:
  - Read
  - Write
  - Glob
---
```

**Tools rationale:**
- `Read`: Read source files
- `Write`: Create new documentation files
- `Glob`: Find source files

**Note:** `project-agnostic: false` because API structure is project-specific.

## Command Execution

Skills that run external commands or scripts.

```yaml
---
name: test-runner
description: Executes project test suite and reports results. Supports pytest, unittest, and nose. Triggers on keywords: run tests, execute tests, test suite
project-agnostic: false
allowed-tools:
  - Bash
  - Read
  - Glob
---
```

**Tools rationale:**
- `Bash`: Execute test commands
- `Read`: Read test configuration
- `Glob`: Find test files

**Note:** `project-agnostic: false` because test setup varies by project.

## Multi-Step Workflow

Skills that orchestrate multiple operations.

```yaml
---
name: changelog-generator
description: Generates changelog from git commits between tags. Groups by type (feat, fix, docs). Triggers on keywords: generate changelog, release notes, commit history
project-agnostic: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Glob
---
```

**Tools rationale:**
- `Bash`: Git commands
- `Read`: Read existing CHANGELOG.md
- `Edit`: Update CHANGELOG.md
- `Glob`: Find changelog file

## Tool Integration

Skills that wrap external tools.

```yaml
---
name: sql-formatter
description: Formats SQL queries using sqlformat. Handles SELECT, INSERT, UPDATE, DELETE with consistent style. Triggers on keywords: format sql, sql formatter, pretty print sql
project-agnostic: true
allowed-tools:
  - Bash
  - Read
  - Edit
---
```

**Tools rationale:**
- `Bash`: Execute sqlformat command
- `Read`: Read SQL files
- `Edit`: Update formatted SQL

## Project-Specific vs Agnostic

### Project-Agnostic (true)

Skills with zero project dependencies:

```yaml
# Language formatting (universal rules)
name: python-formatter
project-agnostic: true

# Standard tool wrappers
name: sql-formatter
project-agnostic: true

# Generic patterns
name: import-analyzer
project-agnostic: true
```

### Project-Specific (false)

Skills tied to project structure:

```yaml
# Custom conventions
name: internal-api-validator
project-agnostic: false

# Project directory structure
name: monorepo-dependency-checker
project-agnostic: false

# Organization-specific workflows
name: company-code-review
project-agnostic: false
```

## Trigger Keyword Patterns

### Good Triggers

```yaml
# Action verbs + domain
description: ... Triggers on keywords: format python, lint code, check style

# Tool names + operation
description: ... Triggers on keywords: black formatter, pylint check, mypy types

# Problem description
description: ... Triggers on keywords: fix imports, organize dependencies, remove unused
```

### Poor Triggers

```yaml
# Too vague
Triggers on keywords: code, files, python

# Too specific (won't match natural language)
Triggers on keywords: execute-black-formatter-with-line-length-88

# Not user vocabulary
Triggers on keywords: ast-transform, lexical-analysis
```

## File Size Management

Keep skills under 500 lines by using supporting files:

```
.claude/skills/my-skill/
  SKILL.md           # Core instructions (under 500 lines)
  cookbook/
    examples.md      # Usage examples
    advanced.md      # Advanced patterns
```

Reference in SKILL.md:
```markdown
See `cookbook/examples.md` for usage patterns.
```
