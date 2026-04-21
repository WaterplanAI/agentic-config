---
name: ac-tools-voice-user
description: Use the say tool for short one-way spoken alerts to the user. Use when you finish a meaningful task, need attention, confirmation, approval, or input, or when the user explicitly asks for voice output. Keep spoken text brief and put the full details in writing.
project-agnostic: true
allowed-tools:
  - say
---

# Voice User

Use the `say` tool for concise one-way spoken communication with the user.

## When to use

- You finished a meaningful task and want to alert the user.
- You need the user's attention, confirmation, approval, choice, or missing input.
- The user explicitly asks for spoken output.
- Only in the top-level agent runtime. Subagents cannot use `say`.

## How to use

- Call the `say` tool with a short spoken message.
- Prefer under 50 words when asking for attention or confirmation.
- Use this shape when possible:
  - `<project> - <what you need>`
- After the spoken alert, give the full explanation in the normal written response.

## Keep spoken output short

Do not speak:

- long explanations
- code
- secrets, tokens, or credentials
- stack traces
- large diffs or long file paths

## Tool shape

```json
{
  "text": "play - say extension updated; please reload.",
  "voice": "Samantha",
  "rate": 190
}
```

Only `text` is required. If `voice` or `rate` is omitted, the extension may use the saved defaults.

## Notes

- The extension may configure automatic voice as `off`, `always`, or `long`.
- Even when automatic voice is off, use the `say` tool when the user explicitly wants spoken output.
- Subagents do not have access to `say`. If a subagent finishes work or needs attention, it should report that in writing and let the parent agent decide whether to speak.
- Long explanations stay in writing; voice is only the concise alert.
