# Orchestration Cookbook

Guidelines for delegating GSuite operations via `/spawn` command.

## Architecture

```
User Request -> SKILL.md -> agent-orchestrator-manager -> /spawn agents -> Bash CLI tools
```

NEVER execute tools directly. ALWAYS delegate via `/spawn` command.

## Orchestration Rules

The orchestrator (SKILL.md) MUST NOT consume tokens for data processing. Its role is:
1. Parse user request
2. Delegate execution to subagents
3. Review subagent outputs (max 3 correction loops)
4. Return final answer

## Model Selection

| Complexity | Model Tier | Use For |
|------------|------------|---------|
| Simple reads | Low-tier (haiku/flash-lite) | `auth.py status`, `gmail.py list`, single API calls |
| Moderate | Medium-tier (sonnet/flash) | Multi-step operations, data processing, searches, summarization |
| Complex | High-tier (opus/pro) | Cross-service operations, analysis requiring judgment |

## Delegation Pattern

**Phase 1: Data Collection** - Spawn low/medium-tier model to execute CLI tools and collect raw data
**Phase 2: Processing** - Spawn low/medium-tier model to summarize, analyze, or transform data
**Phase 3: Final Answer** - Spawn low/medium-tier model to format the final response
**Orchestrator Role** - Review outputs, ensure requirements met, iterate if needed (max 3 loops)

## Examples

### WRONG - Direct execution (orchestrator consuming tokens)

```bash
Bash(uv run gmail.py list --limit 10)
Bash(uv run gcalendar.py list-events --days 7)
# Then processing data directly in orchestrator context
```

### CORRECT - Delegated execution

```bash
/spawn low-tier "Run: uv run core/skills/gsuite/tools/gmail.py list --limit 10"
/spawn low-tier "Run: uv run core/skills/gsuite/tools/gcalendar.py list-events --days 7 --json"
```

### CORRECT - Full delegation with processing

```bash
/spawn medium-tier "Execute:
1. Run: uv run core/skills/gsuite/tools/gmail.py search 'from:user@example.com' --json --limit 10
2. For each message ID, run: uv run gmail.py read <id>
3. Summarize key themes
4. Propose next steps for each
Report: Formatted summary with next steps"
```
