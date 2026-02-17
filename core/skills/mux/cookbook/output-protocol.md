# Agent Output Protocol

Mandatory format for ALL swarm agent output files.

## File Structure

```markdown
# {Title}

## Table of Contents
- [Executive Summary](#executive-summary)
- [Section 1](#section-1)
...

## Executive Summary

**Purpose**: {1 sentence}
**Key Findings**: {3-5 bullet points}
**Recommendations/Next Steps**: {2-3 bullet points}

---

## Section 1
...
```

## Signal File Creation

After writing output file, agent MUST create signal:

```bash
uv run .claude/skills/mux/tools/signal.py "{SESSION_DIR}/.signals/{NNN}-{name}.done" \
    --path "{output_path}" \
    --status success
```

## Agent Return Value

Return ONLY: `0`

DO NOT return:
- File paths (already in signal file)
- Content summaries
- Key findings
- Any substantive text
