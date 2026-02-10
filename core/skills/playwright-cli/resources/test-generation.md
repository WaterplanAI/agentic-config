# Test Generation

Use playwright-cli sessions to generate test scripts from manual browser interactions.

## Workflow

1. Start a named session with tracing enabled:
   ```bash
   playwright-cli -s=test-gen open https://example.com
   playwright-cli tracing-start
   ```

2. Perform the user flow:
   ```bash
   playwright-cli -s=test-gen click "Login"
   playwright-cli -s=test-gen fill "#email" "user@example.com"
   playwright-cli -s=test-gen click "Submit"
   ```

3. Stop tracing and save:
   ```bash
   playwright-cli tracing-stop --output trace.zip
   ```

4. Review the trace file to extract the test steps.

The trace file contains all actions, network requests, and console output from the session.
