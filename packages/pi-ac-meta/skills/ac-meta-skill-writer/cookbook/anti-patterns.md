# Anti-Patterns Cookbook

What NOT to do when creating skills.

## Naming Anti-Patterns

### Vague Names

```yaml
# BAD: Too generic
name: helper
name: utils
name: tools

# GOOD: Specific purpose
name: python-type-annotator
name: sql-formatter
name: import-organizer
```

### Overly Specific Names

```yaml
# BAD: Too narrow
name: fix-python-import-order-in-django-projects

# GOOD: Appropriate scope
name: python-import-organizer
```

### Mixed Case or Special Characters

```yaml
# BAD: Invalid format
name: mySkill
name: my_skill
name: My-Skill

# GOOD: Lowercase with hyphens
name: my-skill
```

## Description Anti-Patterns

### Missing Triggers

```yaml
# BAD: Not discoverable
description: Formats SQL queries with consistent style

# GOOD: Includes triggers
description: Formats SQL queries with consistent style. Triggers on keywords: format sql, sql formatter, pretty print sql
```

### Wrong Voice

```yaml
# BAD: First person
description: I format Python code with Black

# BAD: Second person
description: You can use this to format Python code

# GOOD: Third person
description: Formats Python code with Black
```

### Too Long

```yaml
# BAD: Exceeds 1024 characters
description: This is a very long description that goes on and on explaining every possible detail about what the skill does, how it works, why it was created, what alternatives were considered, implementation details, performance characteristics, edge cases, limitations, future plans...

# GOOD: Concise and focused
description: Formats Python code with Black. Triggers on keywords: format python, black formatter
```

## Tool Permission Anti-Patterns

### Kitchen Sink Approach

```yaml
# BAD: Grants everything
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep

# GOOD: Minimal necessary
allowed-tools:
  - Read
  - Glob
```

### Write Access for Read-Only Tasks

```yaml
# BAD: Analysis doesn't need write
name: code-analyzer
allowed-tools:
  - Read
  - Write
  - Edit

# GOOD: Read-only tools
allowed-tools:
  - Read
  - Glob
  - Grep
```

### Both Write and Edit

```yaml
# BAD: Rarely need both
allowed-tools:
  - Read
  - Write
  - Edit

# GOOD: Choose one based on task
# Use Edit for modifications
allowed-tools:
  - Read
  - Edit

# Use Write for new files
allowed-tools:
  - Read
  - Write
```

## Structure Anti-Patterns

### Monolithic Skills

```yaml
# BAD: Does everything
name: code-helper
description: Formats, lints, tests, documents, and refactors all code
```

**Why bad:** Unfocused, hard to maintain, triggers on too many keywords.

**Solution:** Split into focused skills (formatter, linter, test-runner).

### Nested References

```markdown
# BAD: Two-level nesting
See `cookbook/advanced/patterns/edge-cases.md`

# GOOD: One-level only
See `cookbook/edge-cases.md`
```

### Execution Patterns

```markdown
# BAD: Unsafe execution pattern
Run this: !`rm -rf /`

# GOOD: Use Bash tool
Use Bash tool to execute commands
```

## Project-Agnostic Anti-Patterns

### Missing Field

```yaml
# BAD: Field not present
name: my-skill
description: Does something
allowed-tools:
  - Read

# GOOD: Explicitly set
name: my-skill
description: Does something
project-agnostic: true
allowed-tools:
  - Read
```

### Wrong Value

```yaml
# BAD: Project-specific marked agnostic
name: internal-api-validator
description: Validates company API conventions
project-agnostic: true  # Wrong - uses company conventions

# GOOD: Correct classification
project-agnostic: false
```

## Content Anti-Patterns

### Excessive Instructions

```markdown
# BAD: Too detailed
1. Read the file
2. Parse the content
3. Analyze each line
4. Check for patterns
5. Build a report
6. Format the output
7. Return results
...
```

**Why bad:** Micromanagement limits Claude's reasoning.

**Solution:** Provide goals and constraints, not step-by-step instructions.

### Placeholder Content

```markdown
# BAD: Incomplete
TODO: Add validation rules
TBD: Define behavior
FIXME: Complete this section
```

**Why bad:** Incomplete skills confuse Claude.

**Solution:** Finish skill before deploying.

### Assumptions About Environment

```markdown
# BAD: Assumes specific paths
Read the config from /home/user/.config/app/settings.json

# GOOD: Use relative paths or environment
Read the config from project root: .app/settings.json
```

## Trigger Keyword Anti-Patterns

### Too Few Keywords

```yaml
# BAD: Not enough matches
Triggers on keywords: format

# GOOD: Multiple alternatives
Triggers on keywords: format python, black formatter, python style, code formatting
```

### Technical Jargon Only

```yaml
# BAD: Users won't say this
Triggers on keywords: ast-transformation, lexical-analysis, syntactic-refactoring

# GOOD: Natural language
Triggers on keywords: fix code structure, analyze syntax, refactor code
```

### Overly Generic

```yaml
# BAD: Too broad
Triggers on keywords: code, file, project, help

# GOOD: Specific to skill
Triggers on keywords: format sql, sql query, pretty print database
```

## Workflow Anti-Patterns

### Implicit Dependencies

```markdown
# BAD: Assumes tools installed
Run sqlformat command

# GOOD: Check and guide
Check if sqlformat is installed. If not, guide user to install.
```

### No Error Handling

```markdown
# BAD: Assumes success
Run the formatter and report results

# GOOD: Handle failures
Run the formatter. If it fails, report the error and suggest fixes.
```

### Silent Failures

```markdown
# BAD: Doesn't report issues
Process all files

# GOOD: Surface errors
Process all files. Report any that fail validation.
```
