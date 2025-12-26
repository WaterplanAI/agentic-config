---
description: Initialize/repair agentic-config symlinks after clone
allowed-tools:
  - Bash
  - Read
  - Glob
---

# Initialize Agentic Config Symlinks

You are being invoked to (re)generate all symlinks for the agentic-config repository.

## Task Overview
Detect the agentic-config repository root and create/repair relative symlinks for all commands, skills, and agents.

## Validation Steps

1. **Verify Repository Identity**
   - Check for VERSION file in current directory
   - Check for core/ directory structure
   - If either missing, report error: "Not in agentic-config repository root"

2. **Detect Symlink Targets**
   Use Bash to discover what needs to be symlinked:
   - Commands: `ls core/commands/claude/*.md`
   - Skills: `ls -d core/skills/*` (directories)
   - Agents: `ls core/agents/*.md`

## Symlink Creation Logic

For each category, use Bash to:

1. **Commands** (.claude/commands/ -> core/commands/claude/)
   ```bash
   cd /absolute/repo/root
   for file in core/commands/claude/*.md; do
     name=$(basename "$file")
     target="../../core/commands/claude/$name"
     ln -sf "$target" ".claude/commands/$name"
   done
   ```

2. **Skills** (.claude/skills/ -> core/skills/)
   ```bash
   cd /absolute/repo/root
   for dir in core/skills/*; do
     name=$(basename "$dir")
     target="../../core/skills/$name"
     ln -sf "$target" ".claude/skills/$name"
   done
   ```

3. **Agents** (.claude/agents/ -> core/agents/)
   ```bash
   cd /absolute/repo/root
   for file in core/agents/*.md; do
     name=$(basename "$file")
     target="../../core/agents/$name"
     ln -sf "$target" ".claude/agents/$name"
   done
   ```

## Pre-Cleanup (Remove Invalid Nested Symlinks)

Before creating symlinks, clean up any invalid nested symlinks that may exist inside source directories:

```bash
cd /absolute/repo/root

# Remove self-referential symlinks inside core/ directories
# Explicit cleanup for known patterns
rm -f core/agents/agents 2>/dev/null
for skill_dir in core/skills/*/; do
  skill_name=$(basename "$skill_dir")
  rm -f "${skill_dir}${skill_name}" 2>/dev/null
done
```

## Execution Steps

1. Get absolute repo root: `pwd`
2. Validate repository (VERSION + core/ exist)
3. **Run pre-cleanup to remove invalid nested symlinks**
4. Create symlinks for all three categories using the logic above
5. Verify symlinks are relative: `readlink .claude/commands/agentic.md` should show `../../core/commands/claude/agentic.md`
6. Count results:
   - Commands created: `ls -1 .claude/commands/*.md | wc -l`
   - Skills created: `ls -1d .claude/skills/* | wc -l`
   - Agents created: `ls -1 .claude/agents/*.md | wc -l`

## Output Format

Report results in markdown:

```markdown
# Agentic Config Initialized

## Repository
- Root: /absolute/path/to/repo

## Local Symlinks
- Commands: N files
- Skills: N directories
- Agents: N files

## Validation
- All symlinks are relative: ✓
- All targets exist: ✓

## Status
Initialization complete. Local symlinks repaired.

Note: For global install, run:
  curl -sL https://raw.githubusercontent.com/USER/agentic-config/main/install.sh | bash
```

## Error Handling

If validation fails:
- Not in agentic-config repo: Report error and exit
- Missing core/ directory: Report error and exit
- Symlink creation fails: Report which category failed and why

## Important Notes

- Use relative paths for symlinks (../../core/...)
- Use `ln -sf` to overwrite existing symlinks
- Work from repository root for all operations
- DO NOT commit changes - just report results
