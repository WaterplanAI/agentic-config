# Tasks Cookbook

Google Tasks operations and confirmation rules.

## Confirmation Rules

Write operations (create, complete, delete) require user confirmation by default.

| Operation | Confirmation Required | Bypass Flag |
|-----------|----------------------|-------------|
| `create` | Yes | `--yes` |
| `complete` | Yes | `--yes` |
| `delete` | Yes | `--yes` |
| `list-lists` | No | - |
| `list-tasks` | No | - |

## Commands Reference

```bash
# List task lists
uv run core/skills/gsuite/tools/tasks.py list-lists

# List tasks in a list
uv run core/skills/gsuite/tools/tasks.py list-tasks <tasklist_id>

# Create task (requires confirmation)
uv run core/skills/gsuite/tools/tasks.py create <tasklist_id> "Task title"

# Create task (skip confirmation)
uv run core/skills/gsuite/tools/tasks.py create <tasklist_id> "Task title" --yes

# Mark task complete (requires confirmation)
uv run core/skills/gsuite/tools/tasks.py complete <tasklist_id> <task_id>

# Delete task (requires confirmation)
uv run core/skills/gsuite/tools/tasks.py delete <tasklist_id> <task_id>
```
