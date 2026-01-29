# Calendar Cookbook

Calendar-specific rules for meeting search, timezone handling, and event creation.

## Event Date Fields

Events have multiple date fields:

| Field | Description | Format |
|-------|-------------|--------|
| `created` | When event was scheduled/created | ISO 8601 (`2025-09-26T18:58:56.000Z`) |
| `updated` | Last modification time | ISO 8601 |
| `start.dateTime` | Event start (timed events) | ISO 8601 with offset (`2026-02-05T16:30:00-03:00`) |
| `start.date` | Event start (all-day events) | Date only (`2026-02-05`) |
| `end.dateTime` / `end.date` | Event end | Same as start |

### Extract Scheduled Date

```bash
# When was event created/scheduled
uv run gcalendar.py list-events --days 30 --json | jq '.events[] | {summary, created, start: .start.dateTime}'

# Find event by name and get creation date
uv run gcalendar.py list-events --days 30 --json | jq '.events[] | select(.summary | test("keyword"; "i")) | {summary, scheduled: .created, occurs: .start.dateTime}'
```

## Relative Date Parsing

Use `gdate.py` to parse natural language dates before creating events:

```bash
# Parse relative date/time
uv run gdate.py parse "mon 3pm" --json
# {"start": "2026-01-26T15:00:00", "end": null, "timezone": "..."}

# With duration
uv run gdate.py parse "mon 3pm" --duration "1h" --json
# {"start": "2026-01-26T15:00:00", "end": "2026-01-26T16:00:00", ...}

# Current time info
uv run gdate.py now --json
```

### Supported Expressions

| Type | Examples |
|------|----------|
| Date | today, tomorrow, mon, tuesday, next monday, next week, in 3 days |
| Time | 3pm, 15:00, 3:30pm, noon, midnight, morning, eod |
| Duration | 1h, 30m, 1.5 hours, 1h 30m, 2 weeks |

### Duration Notes

Durations use dateparser's natural language parsing.

**Supported:** `1h`, `30m`, `1.5 hours`, `1h 30m` (space-separated), `2 weeks`

**NOT supported:** `1h30m` (no space), `1.5 months` (fractional months)

**Fractional month conversions:**
| Instead of | Use |
|------------|-----|
| 1.5 months | 45 days or 6 weeks |
| 2.5 weeks | 17 days |

### Key Rules

1. **Future-biased**: "mon" = next Monday (never past)
2. **Same-day handling**: If today is Monday, "mon" goes to next Monday
3. **Default time**: noon if no time specified

### Integration Pattern

```bash
# Parse then create event
times=$(uv run gdate.py parse "mon 3pm" --duration "1h" --json)
start=$(echo "$times" | jq -r '.start')
end=$(echo "$times" | jq -r '.end')
uv run gcalendar.py create "Meeting" "$start" "$end" --yes
```

## Querying Other Users' Calendars

When user asks for someone else's calendar events (not shared meetings WITH them):

### Requirements
- Target user must have shared their calendar with you (read access)
- Use `--calendar <email>` flag to query their calendar directly

### Correct Usage

```bash
# Query another user's calendar (next 7 days, future only)
uv run gcalendar.py list-events --calendar user@example.com --days 7 --json

# Today's FULL schedule for another user (including past events)
uv run gcalendar.py list-events --calendar user@example.com --start $(date +%Y-%m-%d) --days 1 --limit 50 --json

# Specific date's full schedule
uv run gcalendar.py list-events --calendar user@example.com --start 2026-01-26 --days 1 --limit 50 --json

# With account specification
uv run gcalendar.py list-events --calendar user@example.com --start $(date +%Y-%m-%d) --days 1 --account myaccount@example.com --json
```

### Key Distinction

| User Request | Correct Approach |
|--------------|------------------|
| "What's on John's calendar today?" | `--calendar john@example.com` (query HIS calendar) |
| "My meetings with John" | `--attendee john@example.com` (query YOUR calendar, filter by attendee) |

**NEVER** search for "shared meetings" when user asks for someone's calendar - query their calendar directly.

## Date Range Parameters (--start / --end)

### Critical: Past Events Are Excluded by Default

**`--days N` without `--start` only returns FUTURE events from NOW.**

To get ALL events for a specific day (including past events), you MUST use:
```bash
--start YYYY-MM-DD --days 1
```

### Working Combinations

| Parameters | Result |
|------------|--------|
| `--days N` | Next N days from NOW (excludes past events today) |
| `--start YYYY-MM-DD --days N` | ALL events for N days starting from midnight of date |

### Critical Rules

1. **For a specific date's full schedule**: ALWAYS use `--start YYYY-MM-DD --days 1`
2. **Use dates only** for --start (not datetime with time component)
3. **NEVER use `--days 1` alone** for "today's events" - it misses past events

### Examples

```bash
# CORRECT: Today's FULL schedule (including past events)
uv run gcalendar.py list-events --start $(date +%Y-%m-%d) --days 1 --json

# CORRECT: Someone else's full day
uv run gcalendar.py list-events --calendar user@example.com --start 2026-01-26 --days 1 --json

# WRONG: Misses events that already happened today!
uv run gcalendar.py list-events --days 1 --json

# Next 7 days from now (future only - this is fine for forward-looking queries)
uv run gcalendar.py list-events --days 7 --json

# Historical analysis (90 days from Nov 1)
uv run gcalendar.py list-events --start 2025-11-01 --days 90 --json
```

### Today's Events Pattern

When user asks for "today's events" or "today's schedule":

```bash
# Get ALL events for today (past + future)
today=$(date +%Y-%m-%d)
uv run gcalendar.py list-events --start "$today" --days 1 --limit 50 --json
```

## Meeting Search Semantics

**CRITICAL INTERPRETATION RULES** (apply BEFORE searching):
- "meeting/catchup with X" = X is an **attendee** (use `--attendee <email>`)
- "1:1 with X" = exactly 2 attendees, post-filter for `len(attendees) == 2`
- **NEVER search by event title** when user specifies a person - use `--attendee` filter

### Filtering Out Personal Events

When looking for **meetings** (not personal events), always use `--with-attendees`:
- This filters out solo events like "Exercise", "Lunch", "Focus time"
- Combine filters: `--attendee <email> --with-attendees`

### Search Flow

1. Resolve person's email first (see cookbook/people.md)

2. **Initial search** with meeting filters:
   ```bash
   uv run gcalendar.py list-events --attendee <email> --with-attendees --days 30 --limit 100 --json
   ```

3. **If no results found**, use AskUserQuestion for progressive search:
   ```
   AskUserQuestion:
     Question: "No meetings with <name> found in next 30 days. How to proceed?"
     Header: "Expand"
     Options:
       - "Search further ahead (90 days)" (Recommended)
       - "Search with higher limit (500 events)"
       - "Cancel search"
   ```

4. **When in doubt** (multiple candidate meetings): Use AskUserQuestion to clarify

### Examples

**CORRECT - Calendar search with name:**
```
User: "Find next catchup with Joe"

1. Check people.md / gcalendar.md -> Not found
2. People API: uv run people.py search "Joe"
3. Result: joe.doe@example.com
4. Search: uv run gcalendar.py list-events --attendee joe.doe@example.com --with-attendees --days 30 --json
```

**WRONG - Searching by title instead of attendee:**
```
User: "Find meeting with Joe"

# WRONG: Searching by event title when user said "meeting with Joe"
uv run gcalendar.py list-events --days 30 | grep -i "catchup"

# WRONG: Listing all events (includes personal events like Exercise, Lunch)
uv run gcalendar.py list-events --days 30 --json
```

## Timezone Handling

**Default behavior**: Tool detects local timezone automatically if `--timezone` not specified.

### Parallel/Related Events

When creating a parallel event based on an existing event's time:

1. **DO NOT copy the `timeZone` field** from original event JSON
2. **Use the UTC offset from `dateTime`** to determine actual timezone:
   - `dateTime: "2026-01-22T18:30:00-03:00"` means event is at 18:30 in UTC-3 zone
   - The stored `timeZone` may be organizer's timezone, NOT the display timezone
3. **Use local timezone** when the dateTime offset matches your local offset
4. **Ask for clarification** if ambiguous

### Examples

**WRONG - Using stored timeZone field:**
```bash
# Original event: dateTime "2026-01-22T18:30:00-03:00", timeZone "America/Los_Angeles"
# WRONG: Using stored timeZone makes 18:30 LA time = 23:30 Buenos Aires!
uv run gcalendar.py create "Parallel" "2026-01-22T18:30" "2026-01-22T19:30" \
  --timezone "America/Los_Angeles" --yes
```

**CORRECT - Using offset to determine timezone:**
```bash
# Original event: dateTime "2026-01-22T18:30:00-03:00", timeZone "America/Los_Angeles"
# The -03:00 offset indicates actual timezone (e.g., America/Argentina/Buenos_Aires)
uv run gcalendar.py create "Parallel" "2026-01-22T18:30" "2026-01-22T19:30" \
  --timezone "America/Argentina/Buenos_Aires" --yes

# Or simply let tool detect local timezone (recommended when local matches offset)
uv run gcalendar.py create "Parallel" "2026-01-22T18:30" "2026-01-22T19:30" --yes
```

## Self-Inclusion

When scheduling events with attendees:

1. **Get active account**: `uv run auth.py status --json | jq -r '.active'`
2. **Include self in attendees** unless user explicitly says "don't include me"
3. **Add self to attendee list**: Include the active account email in `--attendees`

```bash
# Get active account email
active=$(uv run core/skills/gsuite/tools/auth.py status --json | jq -r '.active')

# Include self when creating event with attendees
uv run gcalendar.py create "Team Meeting" "2024-01-15T10:00" "2024-01-15T11:00" \
  --attendees "$active,colleague@example.com" --meet --yes
```

## Commands Reference

Write operations (create, update, delete) require user confirmation by default.

```bash
# List upcoming events
uv run core/skills/gsuite/tools/gcalendar.py list-events --days 7

# Create event (uses local timezone by default)
uv run core/skills/gsuite/tools/gcalendar.py create "Meeting" "2024-01-15T10:00" "2024-01-15T11:00" --yes

# Create event with explicit timezone
uv run core/skills/gsuite/tools/gcalendar.py create "Meeting" "2024-01-15T10:00" "2024-01-15T11:00" \
  --timezone "America/New_York" --yes

# Create event with attendees and Meet link (include self)
uv run core/skills/gsuite/tools/gcalendar.py create "Team Sync" "2024-01-15T10:00" "2024-01-15T11:00" \
  --attendees "self@example.com,colleague@example.com" --meet --yes

# Create private event (hidden from others)
uv run core/skills/gsuite/tools/gcalendar.py create "Personal" "2024-01-15T10:00" "2024-01-15T11:00" \
  --visibility private --yes

# Create event that shows as free (doesn't block calendar)
uv run core/skills/gsuite/tools/gcalendar.py create "Optional" "2024-01-15T10:00" "2024-01-15T11:00" \
  --show-as free --yes

# Update event (preserves original timezone unless --timezone specified)
uv run core/skills/gsuite/tools/gcalendar.py update <event_id> --title "New Title"

# Update event time with explicit timezone
uv run core/skills/gsuite/tools/gcalendar.py update <event_id> --start "2024-01-15T11:00" \
  --timezone "America/New_York" --yes

# Add/remove attendees
uv run core/skills/gsuite/tools/gcalendar.py update <event_id> --add-attendees "new@example.com" --yes
uv run core/skills/gsuite/tools/gcalendar.py update <event_id> --remove-attendees "old@example.com" --yes

# Update visibility and show-as
uv run core/skills/gsuite/tools/gcalendar.py update <event_id> --visibility private --show-as free --yes

# Delete event (requires confirmation)
uv run core/skills/gsuite/tools/gcalendar.py delete <event_id>

# List calendars
uv run core/skills/gsuite/tools/gcalendar.py calendars
```

## RSVP

Set your attendance response for events:

```bash
# Accept invitation
uv run gcalendar.py rsvp <event_id> accepted --yes

# Decline invitation
uv run gcalendar.py rsvp <event_id> declined --yes

# Mark as tentative
uv run gcalendar.py rsvp <event_id> tentative --yes

# JSON output
uv run gcalendar.py rsvp <event_id> accepted --json
```

## Extended API Access (--extra)

For Google Calendar API features not exposed via CLI options, use `--extra`:

- Top-level keys = merged into event body
- `_api` key = API method parameters (e.g., sendUpdates)

### Recurring Events

```bash
# Weekly recurring event
uv run gcalendar.py create "Weekly Standup" "2024-01-15T09:00" "2024-01-15T09:30" \
  --extra '{"recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR"]}' --yes

# Biweekly on Tuesdays and Thursdays
uv run gcalendar.py create "Biweekly Sync" "2024-01-16T14:00" "2024-01-16T15:00" \
  --extra '{"recurrence": ["RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=TU,TH"]}' --yes

# Monthly on first Monday
uv run gcalendar.py create "Monthly Review" "2024-01-01T10:00" "2024-01-01T11:00" \
  --extra '{"recurrence": ["RRULE:FREQ=MONTHLY;BYDAY=1MO"]}' --yes

# Daily for 10 occurrences
uv run gcalendar.py create "Daily Check-in" "2024-01-15T08:00" "2024-01-15T08:15" \
  --extra '{"recurrence": ["RRULE:FREQ=DAILY;COUNT=10"]}' --yes
```

### Custom Reminders

```bash
# 10-minute popup reminder only
uv run gcalendar.py create "Quick Sync" "2024-01-15T10:00" "2024-01-15T10:30" \
  --extra '{"reminders": {"useDefault": false, "overrides": [{"method": "popup", "minutes": 10}]}}' --yes

# Multiple reminders: email 1 day before, popup 30 minutes before
uv run gcalendar.py create "Important Meeting" "2024-01-15T10:00" "2024-01-15T11:00" \
  --extra '{"reminders": {"useDefault": false, "overrides": [{"method": "email", "minutes": 1440}, {"method": "popup", "minutes": 30}]}}' --yes
```

### Attendee Notifications

Use `_api.sendUpdates` to control email notifications when creating/updating events with attendees:

```bash
# Notify all attendees
uv run gcalendar.py create "Team Meeting" "2024-01-15T10:00" "2024-01-15T11:00" \
  --attendees "team@example.com" \
  --extra '{"_api": {"sendUpdates": "all"}}' --yes

# Notify only external attendees
uv run gcalendar.py create "External Call" "2024-01-15T14:00" "2024-01-15T15:00" \
  --attendees "partner@external.com,colleague@example.com" \
  --extra '{"_api": {"sendUpdates": "externalOnly"}}' --yes

# No notifications (silent update)
uv run gcalendar.py update <event_id> --title "Renamed Meeting" \
  --extra '{"_api": {"sendUpdates": "none"}}' --yes
```

### Combined Example

```bash
# Recurring weekly meeting with attendees, custom reminders, and notifications
uv run gcalendar.py create "Weekly 1:1" "2024-01-15T11:00" "2024-01-15T11:30" \
  --attendees "manager@example.com" --meet \
  --extra '{
    "recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=MO"],
    "reminders": {"useDefault": false, "overrides": [{"method": "popup", "minutes": 5}]},
    "_api": {"sendUpdates": "all"}
  }' --yes
```
