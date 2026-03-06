# Orchestration Cookbook

Guidelines for running GSuite operations in the v0.2 plugin architecture.

## Architecture

```
User Request -> gsuite SKILL.md -> Task()/subagent worker -> Bash CLI tools (tools/*.py)
```

No legacy orchestrator manager and no spawn-command dependency.
Use platform-native subagent tooling (Task()/subagent) when available.

## Core Rules

1. Prefer delegation to platform-native subagents (Task()/subagent tool).
2. Execute tools with `uv run <tool>.py ...` inside those delegated workers.
3. Keep operations explicit and auditable (show command intent, inputs, outputs).
4. Split complex requests into phases instead of one giant command.
5. Validate prerequisites before writes (auth/account/resource exists).
6. Read the corresponding cookbook file before first use of any tool.

## Phase Pattern (Recommended)

### Phase 1: Collect
- Gather raw data with read/list/search commands.
- Prefer JSON output when available.

### Phase 2: Transform
- Summarize or filter results in-context.
- Prepare write payloads in temp files for large content.

### Phase 3: Apply
- Execute write/update commands.
- Report exactly what changed.

## Examples

### Delegated read workflow

```text
Task()/subagent prompt:
1. Run: uv run tools/gmail.py list --limit 10 --json
2. Run: uv run tools/gcalendar.py list-events --days 7 --json
3. Return consolidated summary + raw JSON snippets
```

### Delegated multi-step workflow

```text
Task()/subagent prompt:
1) Search
   uv run tools/gmail.py search "from:example@example.com" --json --limit 10
2) Read selected message
   uv run tools/gmail.py read <message-id> --json
3) Draft reply from prepared content
   cat /tmp/reply.md | uv run tools/gmail.py draft --to "example@example.com" --subject "Follow-up"
4) Return execution log + outcome
```

### Large content write

```bash
cat /tmp/doc-content.md | uv run tools/docs.py write <doc-id>
```

## Anti-Patterns

- Using deprecated spawn-command instructions
- Skipping available subagent tooling and doing heavy orchestration inline
- Referring to legacy orchestrator-manager patterns
- Executing write operations without auth/account verification
- Skipping cookbook checks for tool-specific flags and limits
