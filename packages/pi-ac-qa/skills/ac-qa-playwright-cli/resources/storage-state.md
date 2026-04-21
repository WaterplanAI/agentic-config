# Storage State

Save and restore browser state (cookies, localStorage, sessionStorage) across sessions.

## Save State

```bash
# Save all storage state to file
playwright-cli state-save --output state.json
```

## Load State

```bash
# Restore state from file
playwright-cli state-load --input state.json
```

## Cookie Management

```bash
playwright-cli cookie-list              # List all cookies
playwright-cli cookie-get "session_id"  # Get specific cookie
playwright-cli cookie-set "key" "value" # Set cookie
playwright-cli cookie-delete "key"      # Delete cookie
playwright-cli cookie-clear             # Clear all cookies
```

## localStorage

```bash
playwright-cli localstorage-list        # List all items
playwright-cli localstorage-get "key"   # Get item
playwright-cli localstorage-set "key" "value"  # Set item
playwright-cli localstorage-delete "key"       # Delete item
playwright-cli localstorage-clear       # Clear all
```

## Use Cases

- Save authenticated state after login for reuse across test sessions
- Pre-populate localStorage/sessionStorage for specific test scenarios
- Debug cookie-related issues by inspecting cookie state
