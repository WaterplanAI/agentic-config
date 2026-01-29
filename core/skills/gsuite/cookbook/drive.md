# Drive Cookbook

## Finding Recently Shared Files

When user says "X shared a file with me", the sharer may NOT be the owner.

**Wrong approach:** Filter Drive by `--owner <email>` - misses files where sharer has access but isn't owner.

**Correct approach:** Search Gmail for Drive sharing notifications:

```bash
# Find sharing notifications from specific person today
uv run gmail.py search "from:drive-shares-dm-noreply@google.com newer_than:1d" --limit 10 --json

# Filter results by sharer name in subject/snippet
# Subject format: "Spreadsheet shared with you: \"<title>\""
# From format: "\"<Name> (via Google Sheets)\" <drive-shares-dm-noreply@google.com>"
```

**Resolution flow:**
1. Resolve person's name via People API
2. Search Gmail for `from:drive-shares-dm-noreply@google.com newer_than:<days>d`
3. Filter results by sharer name in the "from" field (appears as "Name (via Google ...)")
4. Extract file link from notification or search Drive by exact title

**Date filters:**
- `newer_than:1d` - today
- `newer_than:7d` - last week
- `after:2026/01/20` - after specific date

## Organization-Wide Sharing

```bash
uv run drive.py share <file_id> _ --role reader --no-notify \
  --extra '{"type": "domain", "domain": "example.com", "emailAddress": null}' --yes
```

- `_` placeholder for required email arg (ignored when type=domain)
- `--no-notify` required for domain type
- `emailAddress: null` removes hardcoded user field
