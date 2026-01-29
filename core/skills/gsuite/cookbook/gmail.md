# Gmail Cookbook

Gmail operations and confirmation rules.

## Confirmation Rules

Write operations require user confirmation by default.

| Operation | Confirmation Required | Bypass Flag |
|-----------|----------------------|-------------|
| `send` | Yes | `--yes` |
| `reply` | Yes | `--yes` |
| `draft` | Yes | `--yes` |
| `archive` | Yes | `--yes` |
| `label add` | Yes | `--yes` |
| `label remove` | Yes | `--yes` |
| `delete` | Yes | `--yes` |
| `list` | No | - |
| `read` | No | - |
| `search` | No | - |
| `labels` | No | - |
| `label show` | No | - |

## Commands Reference

```bash
# List messages
uv run core/skills/gsuite/tools/gmail.py list --limit 10

# Read message content
uv run core/skills/gsuite/tools/gmail.py read <message_id>

# Send email (requires confirmation)
uv run core/skills/gsuite/tools/gmail.py send "to@example.com" "Subject" "Body"

# Send email (skip confirmation)
uv run core/skills/gsuite/tools/gmail.py send "to@example.com" "Subject" "Body" --yes

# Create draft (requires confirmation)
uv run core/skills/gsuite/tools/gmail.py draft "to@example.com" "Subject" "Body"

# Search messages
uv run core/skills/gsuite/tools/gmail.py search "from:user@example.com"

# List labels
uv run core/skills/gsuite/tools/gmail.py labels

# Archive message (remove from inbox)
uv run core/skills/gsuite/tools/gmail.py archive <message_id>

# Show labels on a message
uv run core/skills/gsuite/tools/gmail.py label show <message_id>

# Add label to message
uv run core/skills/gsuite/tools/gmail.py label add <message_id> STARRED --yes

# Remove label from message
uv run core/skills/gsuite/tools/gmail.py label remove <message_id> UNREAD --yes
```

## Common Label IDs

System labels (case-sensitive):

| Label ID | Description |
|----------|-------------|
| `INBOX` | Messages in inbox |
| `SPAM` | Spam folder |
| `TRASH` | Trash folder |
| `UNREAD` | Unread messages |
| `STARRED` | Starred messages |
| `IMPORTANT` | Marked important |
| `SENT` | Sent messages |
| `DRAFT` | Draft messages |
| `CATEGORY_PERSONAL` | Personal category |
| `CATEGORY_SOCIAL` | Social category |
| `CATEGORY_PROMOTIONS` | Promotions category |
| `CATEGORY_UPDATES` | Updates category |
| `CATEGORY_FORUMS` | Forums category |

User labels have custom IDs - use `labels` command to list them.

## Recipient Resolution

**ALWAYS resolve recipients before sending**. See cookbook/people.md for resolution flow.

```
User: "Send email to John about the meeting"

1. Resolve "John" -> john.smith@example.com (via people.md or People API)
2. Confirm recipient if multiple matches
3. Execute: uv run gmail.py send "john.smith@example.com" "Subject" "Body"
```
