# Extended API Access (--extra)

The `--extra` parameter provides escape hatch access to Google API features not exposed via CLI options.

## Convention

```json
{
  "field": "value",         // Merged into request body (common case)
  "_api": { "param": val }  // Passed to API method directly (rare)
}
```

- Top-level keys (except `_api`) = merged into request body
- `_api` key = API method parameters

## Common Extended Parameters

| Tool | Parameter | Description | Example |
|------|-----------|-------------|---------|
| gcalendar | `recurrence` | Recurring event rules | `'{"recurrence": ["RRULE:FREQ=WEEKLY"]}'` |
| gcalendar | `reminders` | Custom reminders | `'{"reminders": {"useDefault": false, "overrides": [{"method": "popup", "minutes": 10}]}}'` |
| gcalendar | `_api.sendUpdates` | Notify attendees: none/all/externalOnly | `'{"_api": {"sendUpdates": "all"}}'` |
| gmail | `cc` | CC recipients | `'{"cc": ["a@example.com"]}'` |
| gmail | `bcc` | BCC recipients | `'{"bcc": ["b@example.com"]}'` |
| tasks | `parent` | Create subtask | `'{"parent": "task-id"}'` |
| drive | `_api.transferOwnership` | Transfer file ownership | `'{"_api": {"transferOwnership": true}}'` |
| drive | `_api.supportsAllDrives` | Access shared drives | `'{"_api": {"supportsAllDrives": true}}'` |

## Examples

### Recurring Events

```bash
# Weekly recurring event
uv run gcalendar.py create "Weekly Sync" "2024-01-15T10:00" "2024-01-15T11:00" \
  --extra '{"recurrence": ["RRULE:FREQ=WEEKLY"]}' --yes

# Recurring event with attendee notifications
uv run gcalendar.py create "Team Meeting" "2024-01-15T10:00" "2024-01-15T11:00" \
  --attendees "team@example.com" \
  --extra '{"recurrence": ["RRULE:FREQ=WEEKLY"], "_api": {"sendUpdates": "all"}}' --yes
```

### Email with CC/BCC

```bash
uv run gmail.py send "to@example.com" "Subject" "Body" \
  --extra '{"cc": ["cc@example.com"], "bcc": ["bcc@example.com"]}' --yes
```

### Subtasks

```bash
uv run tasks.py create <list-id> "Subtask" \
  --extra '{"parent": "parent-task-id"}' --yes
```

### Drive Ownership Transfer

```bash
uv run drive.py share <file-id> "new-owner@example.com" --role owner \
  --extra '{"_api": {"transferOwnership": true}}' --yes
```

## API Reference

For full parameter documentation, see `assets/api-reference.md`.
