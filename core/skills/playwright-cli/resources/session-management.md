# Session Management

playwright-cli maintains browser state across invocations via named sessions.

## Creating Sessions

```bash
# Default session (unnamed)
playwright-cli open https://example.com

# Named session
playwright-cli -s=login-flow open https://example.com

# Via environment variable
PLAYWRIGHT_CLI_SESSION=login-flow playwright-cli open https://example.com
```

## Using Existing Sessions

```bash
# All subsequent commands use the same session
playwright-cli -s=login-flow fill "#email" "user@example.com"
playwright-cli -s=login-flow fill "#password" "pass123"
playwright-cli -s=login-flow click "Sign In"
playwright-cli -s=login-flow snapshot
```

## Managing Sessions

```bash
playwright-cli list           # List all active sessions
playwright-cli close          # Close current/default session
playwright-cli -s=name close  # Close specific session
playwright-cli close-all      # Close all sessions
playwright-cli kill-all       # Force-kill all sessions
playwright-cli delete-data    # Delete all session data
```

## Best Practices

- Use named sessions for multi-step workflows (login, checkout, etc.)
- One session per test scenario to avoid state leakage
- Close sessions explicitly after workflows complete
- Use `PLAYWRIGHT_CLI_SESSION` env var for scripts that invoke multiple commands
