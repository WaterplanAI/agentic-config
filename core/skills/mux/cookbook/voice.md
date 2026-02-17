# Voice Protocol

Voice updates for MUX orchestration user visibility.

## Voice Command Syntax

```python
mcp__voicemode__converse(
    message="{update}",
    voice="af_heart",
    tts_provider="kokoro",
    speed=1.25,
    wait_for_response=False
)
```

## Voice Settings

Recommended settings for MUX orchestration:

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `voice` | `af_heart` | Primary voice (warm, clear) |
| `tts_provider` | `kokoro` | Fast, high-quality TTS |
| `speed` | `1.25` | Slightly faster than normal |
| `wait_for_response` | `false` | Non-blocking updates |

## When to Use Voice Updates

Update at key milestones:

1. Phase start (confirmation)
2. Workers launched (parallelism)
3. Phase completion
4. Errors or recovery actions
5. Final completion

## Voice Update Examples

### Phase 0: Confirmation
```python
mcp__voicemode__converse(
    message="Starting mux for customer feedback analysis",
    voice="af_heart",
    tts_provider="kokoro",
    speed=1.25,
    wait_for_response=False
)
```

### Phase 2: Workers Launched
```python
mcp__voicemode__converse(
    message=f"{len(subjects)} research workers launched",
    voice="af_heart",
    tts_provider="kokoro",
    speed=1.25,
    wait_for_response=False
)
```

### Phase 4: Consolidation
```python
mcp__voicemode__converse(
    message="Total size 120KB, launching consolidator",
    voice="af_heart",
    tts_provider="kokoro",
    speed=1.25,
    wait_for_response=False
)
```

### Phase 6.5: Completion
```python
mcp__voicemode__converse(
    message="Sentinel review complete, deliverables ready",
    voice="af_heart",
    tts_provider="kokoro",
    speed=1.25,
    wait_for_response=False
)
```

### Error Recovery
```python
mcp__voicemode__converse(
    message="Researcher timed out, relaunching with tighter scope",
    voice="af_heart",
    tts_provider="kokoro",
    speed=1.25,
    wait_for_response=False
)
```

## Voice Helper Function

Shorthand for consistent voice updates:

```python
def voice(message: str):
    mcp__voicemode__converse(
        message=message,
        voice="af_heart",
        tts_provider="kokoro",
        speed=1.25,
        wait_for_response=False
    )
```

Usage:
```python
voice("Starting Phase 2 research fan-out")
```

## Alternative Voices

Kokoro provider alternatives:

| Voice | Characteristics |
|-------|-----------------|
| `af_heart` | Warm, clear (default) |
| `af_sarah` | Neutral, professional |
| `af_bella` | Energetic, friendly |

## Disabling Voice

Set `wait_for_response=False` to make updates non-blocking.

Omit voice calls entirely if user prefers text-only updates.
