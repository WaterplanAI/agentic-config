---
description: Execute E2E test from definition file
argument-hint: <test-file-path> [base-url]
project-agnostic: true
---

# E2E Test Runner

Execute E2E test steps from a test definition file.

**Test File:** $1
**Base URL:** $2 (default: `http://localhost:${DEFAULT_PORT:-5173}/`)

## Pre-Flight Checks

1. **Verify Test File Exists**
   - Read test file from `$1`
   - If not found: STOP with "Test file not found: $1"

2. **Verify MCP Server Available**
   - Check Playwright MCP tools are accessible
   - If not: STOP with "Playwright MCP not available"

3. **Parse Test Definition**
   - Extract: Test Name, User Story, Test Steps, Success Criteria
   - If parsing fails: STOP with parse error details

## Execution

1. **Initialize Test Session**
   - Record test start timestamp
   - Create screenshot directory: `{PROJECT_ROOT}/outputs/e2e/<test-name>/`

2. **Navigate to Base URL**
   - Use `browser_navigate` to open base URL
   - Take screenshot: `01_initial.png`

3. **Execute Test Steps**
   - For each step in Test Steps section:
     a. Parse step action (Navigate, Verify, Click, Type, Screenshot)
     b. Execute action using appropriate MCP tool
     c. If step includes "screenshot": capture and save
     d. If step includes "verify": validate condition
     e. On failure: record error and continue to capture state

4. **Validate Success Criteria**
   - Check each criterion from Success Criteria section
   - Mark as passed/failed

5. **Generate Result JSON**
   - Output structured result to stdout

## Output Format

Return JSON result:
```json
{
  "test_name": "<name from test file>",
  "status": "passed|failed",
  "timestamp": "<ISO timestamp>",
  "duration_ms": <number>,
  "steps": [
    {"step": 1, "action": "navigate", "status": "passed"},
    {"step": 2, "action": "verify", "status": "passed"}
  ],
  "screenshots": [
    "{PROJECT_ROOT}/outputs/e2e/<test-name>/01_initial.png"
  ],
  "video": "{PROJECT_ROOT}/videos/<timestamp>-<test-name>.webm",
  "error": null
}
```

## Error Handling

- On step failure: capture screenshot, continue remaining steps
- On critical failure (browser crash): return partial result with error
- Always close browser session on completion

## MCP Tools Used

- `browser_navigate` - Navigate to URLs
- `browser_snapshot` - Get page accessibility tree
- `browser_click` - Click elements (by text/selector)
- `browser_type` - Type into inputs
- `browser_screenshot` - Capture PNG screenshots
- `browser_close` - End session (saves video)
