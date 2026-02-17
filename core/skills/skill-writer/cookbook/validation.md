# Validation Cookbook

Validation rules and checklist for SKILL.md files.

## Validation Checklist

Execute these checks in order. BLOCK if any fail.

### 1. Name Validation

```bash
# Regex: /^[a-z0-9-]+$/
# Max length: 64 characters
# Forbidden: "anthropic", "claude"
```

| Check | Rule | Error |
|-------|------|-------|
| Format | Only lowercase, numbers, hyphens | Invalid characters in name |
| Length | Max 64 characters | Name exceeds 64 characters |
| Reserved | No "anthropic" or "claude" | Reserved word in name |

**Examples:**
- Valid: `python-type-annotator`, `sql-formatter`, `gsuite`
- Invalid: `Python-Annotator`, `my_skill`, `claude-helper`, `anthropic-tools`

### 2. Description Validation

```yaml
# Max length: 1024 characters
# Must be third person
# Must include: "Triggers on keywords:"
```

| Check | Rule | Error |
|-------|------|-------|
| Length | Max 1024 characters | Description exceeds 1024 characters |
| Voice | Third person (no "I" or "you") | Description not in third person |
| Triggers | Contains "Triggers on keywords:" | Missing trigger keywords |
| Keywords | At least 3 trigger keywords | Insufficient trigger keywords |

**Examples:**
- Valid: `Formats SQL queries with consistent style. Triggers on keywords: format sql, sql formatter, pretty print sql`
- Invalid: `I format SQL queries` (first person)
- Invalid: `Formats SQL queries` (no triggers)
- Invalid: `Formats SQL queries. Triggers on keywords: sql` (too few keywords)

### 3. Project-Agnostic Validation

```yaml
# Required field
# Must be explicitly true or false
```

| Check | Rule | Error |
|-------|------|-------|
| Present | Field exists in frontmatter | Missing project-agnostic field |
| Value | Boolean (true or false) | Invalid project-agnostic value |

**Decision guide:**
- `true`: Skill has zero project-specific dependencies
- `false`: Skill references project structure, conventions, or configurations

### 4. Tool Minimalism

```yaml
# Only grant tools necessary for operation
# Read-only skills should not have Write/Edit/Bash
```

| Task Type | Required Tools |
|-----------|----------------|
| Read/analyze | Read, Glob |
| Search content | Read, Glob, Grep |
| Write docs | Read, Write, Glob |
| Edit files | Read, Edit, Glob |
| Run commands | Bash, Read |

**Red flags:**
- Bash granted without clear need
- Write AND Edit both granted
- Analysis skill with Write/Edit/Bash

### 5. Structure Validation

```bash
# Max lines: 500
# No bash execution pattern: !`
# Forward slashes only in paths
# One-level references only
```

| Check | Rule | Error |
|-------|------|-------|
| Lines | Under 500 lines | Skill exceeds 500 lines |
| Execution | No `!` followed by backtick | Unsafe execution pattern |
| Paths | Forward slashes only | Invalid path separators |
| References | One directory level | Nested references |

**Examples:**
- Valid: `cookbook/validation.md`, `templates/skill-template.md`
- Invalid: `cookbook/advanced/validation.md` (two levels)
- Invalid: `templates\skill.md` (backslash)

## Validation Script

Quick validation commands:

```bash
# Name check (max 64, lowercase/numbers/hyphens only)
[[ "$name" =~ ^[a-z0-9-]{1,64}$ ]] && [[ ! "$name" =~ (anthropic|claude) ]]

# Description check (max 1024, has triggers)
[[ ${#description} -le 1024 ]] && [[ "$description" =~ "Triggers on keywords:" ]]

# Line count check
[[ $(wc -l < SKILL.md) -lt 500 ]]

# No execution pattern
! grep -q '!\`' SKILL.md
```

## Common Failures

### Name Violations

```yaml
# BAD: Mixed case
name: mySkill

# BAD: Underscores
name: my_skill

# BAD: Reserved word
name: claude-assistant

# GOOD
name: my-skill
```

### Description Violations

```yaml
# BAD: No triggers
description: Formats Python code

# BAD: First person
description: I format Python code

# BAD: Too long (check character count)
description: This is a very long description that goes on and on...

# GOOD
description: Formats Python code with Black. Triggers on keywords: format python, black formatter, python style
```

### Tool Violations

```yaml
# BAD: Analysis skill with write access
allowed-tools:
  - Read
  - Write
  - Bash

# GOOD: Analysis skill with read-only
allowed-tools:
  - Read
  - Glob
  - Grep
```
