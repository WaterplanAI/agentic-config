---
description: Open browser at URL for E2E testing via Playwright MCP
argument-hint: [url]
project-agnostic: true
---

# Browser Command

Open browser for E2E testing using Playwright MCP server.

**Target URL:** $ARGUMENTS

If no URL provided, default to: `http://localhost:${DEFAULT_PORT:-5173}/`

## Pre-Flight Checks

1. **Verify MCP Server Available**
   - Check that Playwright MCP tools are accessible
   - If not available: STOP with error "Playwright MCP server not configured. Run: claude mcp add playwright"

## Execution

1. **Navigate to URL**
   - Use `browser_navigate` tool to open the target URL
   - If URL argument is empty, use `http://localhost:${DEFAULT_PORT:-5173}/`

2. **Verify Page Load**
   - Use `browser_snapshot` to capture current page state
   - Report page title and URL

3. **Report Status**
   - Confirm browser is open and ready
   - Display current page title
   - Display current URL

## Available MCP Browser Tools

After opening browser, these tools are available:
- `browser_navigate` - Navigate to URL
- `browser_snapshot` - Capture accessibility snapshot
- `browser_click` - Click element
- `browser_type` - Type into element
- `browser_screenshot` - Take PNG screenshot
- `browser_close` - Close browser session

## Notes
- Video recording is automatic (configured in .mcp.json if Playwright MCP supports it)
- Videos typically saved to `{PROJECT_ROOT}/videos/` directory
- Port can be configured via DEFAULT_PORT environment variable
