# Project Guidelines

## Environment & Tooling
- **Package Manager:** uv
- **Type Checking:** uv run pyright
- **Linting:** uv run ruff check [--fix] <path>
- **Build:** Only when explicitly requested

## Style & Conventions
- Type hints for all public functions, descriptive names, small pure functions
- After edits: uv run ruff check --fix <file> && uv run pyright <file>

## PEP 723 Scripts (Inline Dependencies)

For scripts with `# /// script` metadata blocks, standard pyright fails because inline deps aren't in pyproject.toml.

**Type check PEP 723 scripts:**
```bash
# Extract deps and run pyright in isolated env
uvx --from pyright --with <dep1> --with <dep2> pyright <script.py>

# Example for a typer+rich script:
uvx --from pyright --with typer --with rich pyright tools/setup.py
```

**One-liner to auto-extract deps:**
```bash
script="path/to/script.py"
deps=$(python3 -c "
import re, tomllib
with open('$script') as f: c = f.read()
m = re.search(r'# /// script\n(.*?)\n# ///', c, re.DOTALL)
if m:
    t = '\n'.join(l.lstrip('# ') for l in m.group(1).split('\n'))
    print(' '.join('--with ' + re.split(r'[<>=!]', d)[0] for d in tomllib.loads(t).get('dependencies', [])))
")
eval "uvx --from pyright $deps pyright $script"
```

## Core Principles
- Verify over assume
- Failures first (lead with errors)
- Always re-raise (never swallow exceptions)
- DO NOT OVERCOMPLICATE
- DO NOT OVERSIMPLIFY

## Critical Rules
- NEVER amend commits unless user says 'amend commit'
- NEVER commit files in gitignored directories unless explicitly requested - DO NOT use git add -f to bypass .gitignore
- Minimal changes; avoid ambiguity; no placeholders
- Keep prompts concise; log costs
- EFFICIENCY in application performance and user experience - REFLECT this in EVERY implementation

## /spec Workflow
Reference agents/spec/{STAGE}.md for detailed instructions.
- Default path: specs/<YYYY>/<MM>/<branch>/<NNN>-<title>.md
- Modify AI Section only; never touch Human Section
- Commit after each stage: spec(<NNN>): <STAGE> - <title>

## Path Resolution

**Project root** = `$PWD` (where Claude is launched, `.agentic-config.json` stored)
**Global installation** = `$AGENTIC_CONFIG_PATH` or `~/.agents/agentic-config` (where `core/`, `VERSION` exist)

**CRITICAL**: `core/` does NOT exist at project root. Only specific command files are symlinked.

To source global libs (spec-resolver.sh, etc.):
```bash
# Pure bash (no external commands like cat) for restricted shell compatibility
_agp=""
[[ -f ~/.agents/.path ]] && _agp=$(<~/.agents/.path)
AGENTIC_GLOBAL="${AGENTIC_CONFIG_PATH:-${_agp:-$HOME/.agents/agentic-config}}"
unset _agp
source "$AGENTIC_GLOBAL/core/lib/spec-resolver.sh"
```

## User Customizations

User-side behavior customizations for skills/commands live in `$AGENTIC_GLOBAL/customization/`:

```
$AGENTIC_GLOBAL/customization/
  <skill-name>/           # Per-skill customizations
    <tool>.md             # Tool-specific output format
  <command-name>/         # Per-command customizations (future)
```

- **NOT tracked in git** - user-local configuration
- Skills check for customizations before execution
- Example: `customization/gsuite/gcalendar.md` for calendar output format

## Git Workflow
- Base branch: main (not master)
- git status returns CWD-relative paths - use those exact paths with git add
- Never commit to main; never amend unless 'amend commit' explicitly requested
- One stage = one commit: spec(<NNN>): <STAGE> - <title>

## CHANGELOG Guidelines
- CHANGELOG entries are written **only against origin/main**
- Fixes within the same branch/unreleased work are NOT separate entries
- From main's linear history perspective, unreleased changes are ONE logical unit
- Do NOT add "Fixed" entries for implementation iterations before merge to main

## Project-Specific Instructions
READ @PROJECT_AGENTS.md for project-specific instructions - CRITICAL COMPLIANCE

## Conditional Documentation

Read documentation only when relevant to your task:

- **docs/external-specs-storage.md** - When:
  - Working with `/spec`, `/o_spec`, `/po_spec`, or `/branch` commands
  - Configuring external specs repository
  - Modifying spec path resolution or commit routing

<!-- PROJECT_AGENTS.md contains project-specific guidelines that override defaults -->
