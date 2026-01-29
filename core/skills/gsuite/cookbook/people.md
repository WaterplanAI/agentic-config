# People Resolution Cookbook

People resolution flow and preference storage for GSuite skill.

## When to Resolve

**MANDATORY** step when ANY person's name is mentioned in the request.

| Context | Examples | Resolution Required |
|---------|----------|---------------------|
| Email operations | "email John", "draft to Jane" | Always |
| Calendar search | "meeting with Joe", "catchup with Sarah" | Always - need email to filter attendees |
| Calendar create | "invite Mike to meeting" | Always |
| Drive sharing | "share with Alex" | Always |
| Any name mention | "find events with Bob" | Always |

## Resolution Flow

### 1. Check Preferences First

Look up known aliases before calling API:

```bash
# Check for people.md customization (global aliases)
cat $AGENTIC_GLOBAL/customization/gsuite/people.md 2>/dev/null
# Also check tool-specific customizations (e.g., gcalendar.md may have aliases)
cat $AGENTIC_GLOBAL/customization/gsuite/gcalendar.md 2>/dev/null
```

### 2. If Not in Preferences, Use People API

```bash
uv run core/skills/gsuite/tools/people.py search "John Smith"
```

### 3. Handle Results

- **Single match**: Use directly (no confirmation needed for searches)
- **Multiple matches**: Use AskUserQuestion to clarify
- **No match**: Ask for clarification or manual email entry

### 4. Conflict Resolution

Preference aliases take precedence over People API results.

### 5. When in Doubt

Use AskUserQuestion to clarify ambiguous requests (e.g., multiple matching events, unclear which person).

## Examples

**Preferences-first resolution:**
```
User: "Send email to jsmith"

1. Check people.md -> Found: jsmith = john.smith@example.com
2. Proceed with gmail.py send (no confirmation needed for known aliases)
```

**People API fallback:**
```
User: "Send email to Jane Doe"

1. Check people.md -> Not found
2. People API: uv run people.py search "Jane Doe"
3. Results: jane.doe@example.com, jane.d@other.org
4. AskUserQuestion: "Which Jane Doe?"
5. On selection, proceed with gmail.py send
```

**WRONG - Skipping resolution:**
```
User: "Find meeting with John"

# WRONG: Searching without resolving email first
uv run gcalendar.py list-events --days 30 | grep -i john

# WRONG: Assuming email format
uv run gmail.py send "john@company.com" "Subject" "Body"
```

## Commands Reference

```bash
# Search contacts by name
uv run core/skills/gsuite/tools/people.py search "John Smith"

# List recent contacts
uv run core/skills/gsuite/tools/people.py list --limit 20
```

## User Preferences Storage

When user says "remember preference", "remember this", "remember X = Y", or "customize":

### Step 1: Identify Preference Type

| Type | Examples | Storage Location |
|------|----------|------------------|
| Contact Alias | "remember jsmith = john.smith@example.com" | `people.md` (global) OR tool-specific |
| Tool Default | "always add Meet link to events" | Tool-specific (e.g., `gcalendar.md`) |
| Output Format | "show events as table" | Tool-specific |

### Step 2: MANDATORY AskUserQuestion for Storage Location

**For Contact Aliases:**
```
AskUserQuestion:
  Question: "Where should I store this contact alias?"
  Header: "Storage"
  Options:
    - "people.md (Recommended)" - Global access for all GSuite tools (gmail, calendar, drive sharing)
    - "gcalendar.md" - Calendar-only, use if this contact is specific to calendar invites
```

### Step 3: Storage Files

| File | Purpose | When to Use |
|------|---------|-------------|
| `index.md` | Entry point with routing to other files | Always read first |
| `people.md` | Global contact aliases | Names/emails used across multiple tools |
| `gcalendar.md` | Calendar preferences | Event defaults, calendar-specific aliases |
| `gmail.md` | Gmail preferences | Email defaults, signatures |
| `drive.md` | Drive preferences | Sharing defaults, folder preferences |

### Step 4: Create Directory if Needed

```bash
mkdir -p $AGENTIC_GLOBAL/customization/gsuite
```

### Example people.md

```markdown
# People Aliases

## Contact Aliases
- jsmith = John Smith (john.smith@example.com)
- jane = Jane Doe (jane.doe@example.com)
- boss = Manager Name (manager@example.com)

## Teams
- engineering = eng-team@example.com
- marketing = marketing@example.com
```
