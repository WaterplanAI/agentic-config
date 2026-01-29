# Preferences Cookbook

Proactive preference learning and customization storage for GSuite skill.

## When to Trigger

Detect preference/correction patterns in user follow-up messages after operations.

### Correction Triggers

User correcting assistant behavior - generalizable patterns:

| Pattern | Example |
|---------|---------|
| "No, always ..." | "No, always add Meet links" |
| "No, never ..." | "No, never include me as attendee" |
| "Actually, ..." | "Actually, use my work calendar" |
| "Don't ..." (generalizable) | "Don't add reminders to events" |

### Preference Triggers

User expressing preferences for future behavior:

| Pattern | Example |
|---------|---------|
| "I prefer ..." | "I prefer meetings with Meet links" |
| "I want ..." (generalizable) | "I want 15-minute reminders by default" |
| "Use my ..." | "Use my work calendar for meetings" |
| "My [X] is [Y]" | "My work email is john@corp.com" |
| "From now on ..." | "From now on use primary calendar" |
| "By default ..." | "By default, include agenda in invites" |
| Explicit | "remember this", "save this preference" |

### Exclusions (Do NOT Trigger)

- **One-off specifications**: "Use work calendar for this meeting" (contextual, not general)
- **Factual statements**: "The meeting is at 3pm" (not a preference)
- **Ambiguity resolution**: Already handled by standard AskUserQuestion flow
- **Contextual choices**: "This one" / "That file" (selection, not preference)

## AskUserQuestion Flow

### Step 1: Offer to Save Preference

When pattern detected:

```
AskUserQuestion:
  Question: "Would you like me to remember this preference for future requests?"
  Header: "Preference"
  Options:
    - label: "Yes, remember this"
      description: "Save to customization file for all future gsuite interactions"
    - label: "No, just this once"
      description: "Apply only to current request"
```

### Step 2: Storage Location (if yes)

Determine storage location based on context. Recommend the most appropriate file:

```
AskUserQuestion:
  Question: "Where should I save this preference?"
  Header: "Storage"
  Options:
    - label: "gcalendar.md (Recommended)"  # Context-aware - show relevant tool first
      description: "Calendar-specific preferences"
    - label: "people.md"
      description: "Contact aliases accessible by all tools"
    - label: "gmail.md"
      description: "Email-specific preferences"
```

**Context-aware defaults:**
- Calendar operations -> recommend `gcalendar.md`
- Email operations -> recommend `gmail.md`
- Contact aliases -> recommend `people.md`
- Drive operations -> recommend `drive.md`

### Step 3: Save Preference

```bash
# Ensure directory exists
mkdir -p $AGENTIC_GLOBAL/customization/gsuite

# Append to appropriate file
cat >> $AGENTIC_GLOBAL/customization/gsuite/<tool>.md << 'EOF'
- <preference description>
EOF
```

## Storage Format

### File Structure

```
$AGENTIC_GLOBAL/customization/gsuite/
  index.md       # Entry point with routing
  gcalendar.md   # Calendar preferences
  gmail.md       # Email preferences
  drive.md       # Drive preferences
  people.md      # Contact aliases (global)
```

### gcalendar.md Example

```markdown
# Calendar Preferences

## Event Defaults
- Always add Google Meet link for meetings with attendees
- Set default reminder: 15 minutes before
- Use primary calendar for work meetings

## Display
- Show response status for each event
- Include attendee list in event details
```

### gmail.md Example

```markdown
# Gmail Preferences

## Compose Defaults
- Always include signature
- Default reply-all for team threads

## Display
- Show unread count in summary
```

### drive.md Example

```markdown
# Drive Preferences

## Sharing Defaults
- Default permission: viewer
- Always notify on share

## Organization
- New documents go to "Work" folder
```

### people.md Example

```markdown
# People Aliases

## Contact Aliases
- john = John Smith (john@corp.com)
- jane = Jane Doe (jane@example.com)

## Teams
- engineering = eng-team@corp.com
- marketing = marketing@corp.com
```

## Preference Types

| Type | Storage | Examples |
|------|---------|----------|
| Contact Alias | `people.md` | "john = john@corp.com" |
| Event Default | `gcalendar.md` | "Always add Meet link" |
| Email Default | `gmail.md` | "Always include signature" |
| Drive Default | `drive.md` | "Default share: viewer" |
| Output Format | Tool-specific | "Show events as table" |

## Accessing Preferences

### Convention

**Tool-specific**: `<tool>.py` -> `<tool>.md`

**Cross-cutting files**:

| File | Purpose | Trigger |
|------|---------|---------|
| `index.md` | General patterns, conditional routing | Always (first) |
| `auth.md` | Account labels, default accounts | "work", "personal", account label |
| `people.md` | Contact aliases | Name (not email) mentioned |

### Load Order

1. Always: `index.md` (routing, general patterns)
2. Tool-specific: `<tool>.md`
3. If account reference: `auth.md`
4. If name mentioned: `people.md`
5. Apply preferences -> Execute

### auth.md Example

```markdown
# Account Preferences

## Labels
- personal = user@example.com
- work = user@corporate.com

## Defaults
- Calendar: work
- Gmail: personal
```

### Example Flow

```
User: "Create meeting with John on my work calendar"

1. Load: index.md (general patterns)
2. Operation: gcalendar.py -> Load gcalendar.md (Meet link default)
3. "work" detected -> Load auth.md (work = corporate.com)
4. "John" detected -> Load people.md (john = john@corp.com)
5. Apply: Switch to corporate.com, add Meet, resolve John
6. Execute: gcalendar.py create
```

### Bash Reference

```bash
PREFS="$AGENTIC_GLOBAL/customization/gsuite"

# Always check index first
[[ -f "$PREFS/index.md" ]] && cat "$PREFS/index.md"

# Tool-specific
[[ -f "$PREFS/<tool>.md" ]] && cat "$PREFS/<tool>.md"

# Cross-cutting (conditional)
[[ -f "$PREFS/auth.md" ]] && cat "$PREFS/auth.md"      # if account reference
[[ -f "$PREFS/people.md" ]] && cat "$PREFS/people.md"  # if name mentioned
```

## Examples

### Example 1: Correction Detection

```
User: "Create a meeting with Jane tomorrow at 2pm"
Assistant: [Creates event without Meet link]
User: "No, always add Meet links to meetings"

-> Trigger: "No, always ..." pattern detected
-> AskUserQuestion: "Would you like me to remember this preference?"
-> User: "Yes"
-> AskUserQuestion: "Where should I save?" -> "gcalendar.md (Recommended)"
-> Save: "- Always add Google Meet link for meetings with attendees"
```

### Example 2: Preference Expression

```
User: "What's on my calendar today?"
Assistant: [Shows events from primary calendar]
User: "I prefer my work calendar for meetings"

-> Trigger: "I prefer ..." pattern detected
-> AskUserQuestion: "Would you like me to remember this preference?"
-> User: "Yes"
-> Save to gcalendar.md: "- Use work calendar for meetings"
```

### Example 3: Contact Alias

```
User: "Email the report to boss"
Assistant: [Resolves via People API]
User: "My boss is manager@corp.com, remember that"

-> Trigger: Explicit "remember that"
-> AskUserQuestion: "Where should I save?"
-> Options: "people.md (Recommended)", "gmail.md"
-> Save to people.md: "- boss = Manager (manager@corp.com)"
```

### Example 4: No Trigger (One-off)

```
User: "Create a meeting for this Friday"
Assistant: [Creates on primary calendar]
User: "Use work calendar for this one"

-> No trigger: "for this one" indicates one-off, not preference
-> Apply only to current request
```
