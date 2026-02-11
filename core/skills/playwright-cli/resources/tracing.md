# Tracing

Capture detailed traces of browser sessions for debugging and analysis.

## Capture Trace

```bash
# Start tracing
playwright-cli tracing-start

# Perform actions...
playwright-cli click "Submit"
playwright-cli snapshot

# Stop and save trace
playwright-cli tracing-stop --output trace.zip
```

## Viewing Traces

Open trace files in the Playwright Trace Viewer:

```bash
npx playwright show-trace trace.zip
```

Traces include screenshots, DOM snapshots, network requests, and console logs at each step.
