# Date/Time Parsing Cookbook

Parse natural language date/time expressions to ISO format for calendar operations.

## Basic Usage

```bash
uv run gdate.py parse "mon 3pm" --json                    # Next Monday 3pm
uv run gdate.py parse "tomorrow 2pm" --duration "1h"     # With end time
uv run gdate.py now --json                                # Current time info
```

## Supported Expressions

| Type | Examples |
|------|----------|
| Date | today, tomorrow, mon, tuesday, next monday, next week, in 3 days |
| Time | 3pm, 15:00, 3:30pm, noon, midnight, morning, eod |
| Duration | 1h, 30m, 1.5 hours, 1h 30m, 2 weeks |

## Key Rules

1. **Future-biased**: "mon" = next Monday (never past)
2. **Same-day handling**: If today is Monday, "mon" goes to next Monday
3. **Default time**: noon if no time specified

## Duration Notes

Durations use dateparser's natural language parsing.

**Supported:** `1h`, `30m`, `1.5 hours`, `1h 30m` (space-separated), `2 weeks`

**NOT supported:** `1h30m` (no space), `1.5 months` (fractional months)

**Fractional month conversions:**

| Instead of | Use |
|------------|-----|
| 1.5 months | 45 days or 6 weeks |
| 2.5 weeks | 17 days |

## Integration with Calendar

```bash
# Parse then create event
times=$(uv run gdate.py parse "mon 3pm" --duration "1h" --json)
start=$(echo "$times" | jq -r '.start')
end=$(echo "$times" | jq -r '.end')
uv run gcalendar.py create "Meeting" "$start" "$end" --yes
```

## Output Format

```json
{
  "start": "2026-01-26T15:00:00",
  "end": "2026-01-26T16:00:00",
  "timezone": "America/Argentina/Buenos_Aires"
}
```
