---
description: Update agentic-config to latest version
argument-hint: [path]
project-agnostic: true
---

Update agentic-config installation using the agentic-update agent.

Target directory: ${1:-.}

The agent will:
1. Check current vs latest version
2. Show what changed in CHANGELOG
3. Identify files needing review
4. Show diffs for template changes
5. Offer update options (force/manual/skip)
6. Execute update
7. Validate post-update
8. Offer to commit update changes

Symlinked files (workflows, commands) update automatically.
Copied files (AGENTS.md, config.yml) may need review.
