# Request Mocking

Intercept and mock network requests for testing.

## Setting Up Routes

```bash
# Mock an API endpoint with JSON response
playwright-cli route "**\/api\/users" --status 200 --body '{"users": []}'

# Mock with specific content type
playwright-cli route "**\/api\/data" --status 200 --body '{"ok":true}' --content-type "application/json"

# Return error status
playwright-cli route "**\/api\/fail" --status 500 --body '{"error":"server error"}'
```

## Managing Routes

```bash
# List active routes
playwright-cli route-list

# Remove a specific route
playwright-cli unroute "**\/api\/users"
```

## Use Cases

- Test error handling by mocking API failures
- Test loading states by delaying responses
- Test edge cases with specific response data
- Isolate frontend from backend during E2E tests
