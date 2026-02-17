# Preview Loop: Playwright MCP Integration

Iterative visual + accessibility feedback using Playwright MCP tools.

## Available Tools

| Tool | Purpose |
|------|---------|
| `mcp__playwright__browser_navigate` | Open prototype URL |
| `mcp__playwright__browser_take_screenshot` | Capture visual state for human review |
| `mcp__playwright__browser_snapshot` | Capture accessibility tree for agent validation |
| `mcp__playwright__browser_resize` | Test responsive breakpoints |
| `mcp__playwright__browser_click` | Interact with elements for state testing |
| `mcp__playwright__browser_type` | Fill form fields for state testing |

## Tier A Preview Sequence

1. Start HTTP server (background):
   ```bash
   python3 -m http.server 8080 -d /tmp/claude-prototypes/<session-id> &
   SERVER_PID=$!
   ```

2. Navigate:
   ```
   mcp__playwright__browser_navigate(url="http://localhost:8080")
   ```

3. Desktop screenshot:
   ```
   mcp__playwright__browser_take_screenshot(type="png")
   ```

4. Accessibility snapshot:
   ```
   mcp__playwright__browser_snapshot()
   ```
   Verify output contains: `main`, `navigation`, `heading`, `button` landmarks.

5. Mobile responsive test:
   ```
   mcp__playwright__browser_resize(width=375, height=667)
   mcp__playwright__browser_take_screenshot(type="png")
   mcp__playwright__browser_resize(width=1440, height=900)  # Reset to desktop
   ```

6. Stop server when done:
   ```bash
   kill $SERVER_PID 2>/dev/null
   ```

## Tier B Preview Sequence

1. Install and start Vite dev server (background):
   ```bash
   cd /tmp/claude-prototypes/<session-id> && npm install && npm run dev &
   ```
   Wait for "Local: http://localhost:5173" in output.

2. Navigate:
   ```
   mcp__playwright__browser_navigate(url="http://localhost:5173")
   ```

3. Same screenshot + snapshot + resize sequence as Tier A.

## Fallback: No Playwright MCP

If Playwright MCP tools are not available in the current session:

- Do NOT error or warn loudly
- Output file paths and manual instructions:

```
Prototype ready at: /tmp/claude-prototypes/<session-id>/index.html

To preview:
  Option 1 (direct): open /tmp/claude-prototypes/<session-id>/index.html
  Option 2 (server): cd /tmp/claude-prototypes/<session-id> && python3 -m http.server 8080
```

## Accessibility Snapshot Validation

After `browser_snapshot()`, check the output for:
- `main` landmark present
- `navigation` landmark present
- At least one `heading` (level 1)
- `button` elements with accessible names
- `textbox` / `combobox` elements with labels (if form page)

Report missing landmarks as validation failures. Fix generated HTML before delivering.
