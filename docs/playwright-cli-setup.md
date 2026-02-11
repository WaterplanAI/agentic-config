# Playwright CLI Setup

This guide provides instructions for setting up playwright-cli for E2E testing with agentic-config.

## Prerequisites

- Node.js v18+ (required for npm global install)
- Claude Code or other AI-assisted development tool

## Quick Start

### 1. Install playwright-cli

```bash
npm install -g @playwright/cli@latest
```

### 2. Install Browser

```bash
playwright-cli install-browser
```

### 3. Install Skills (for Claude Code)

If using agentic-config, skills are installed automatically during `/agentic setup`.

For manual installation:
```bash
playwright-cli install --skills
```

This generates `.claude/skills/playwright-cli/` with the skill definition and reference docs.

### 4. Setup Project Directories

```bash
mkdir -p outputs/e2e
```

### 5. Update .gitignore

Add the following entry to your project's `.gitignore` (if not already present):

```
outputs/
```

## Configuration

### Optional: `playwright-cli.json`

Create a `playwright-cli.json` in your project root for custom settings:

```json
{
  "browserName": "chromium",
  "isolated": true,
  "launchOptions": {
    "headless": false
  },
  "contextOptions": {
    "viewport": { "width": 1920, "height": 1080 }
  },
  "saveVideo": {
    "width": 1920,
    "height": 1080
  },
  "outputDir": "./outputs/e2e"
}
```

### Configuration Options

- `browserName`: Browser to use (chromium, firefox, webkit). Default: chromium
- `isolated`: Use isolated browser context. Default: true
- `launchOptions.headless`: Run in headless mode. Default: true
- `contextOptions.viewport`: Browser viewport dimensions
- `saveVideo`: Video recording resolution
- `outputDir`: Output directory for recordings and artifacts

## Usage

### Basic Workflow

```bash
# Open a page
playwright-cli open https://example.com

# Take a snapshot (accessibility tree)
playwright-cli snapshot

# Take a screenshot
playwright-cli screenshot --output ./outputs/e2e/page.png

# Interact with elements
playwright-cli click "Login"
playwright-cli fill "#email" "user@example.com"
playwright-cli fill "#password" "password123"
playwright-cli click "Submit"

# Close session
playwright-cli close
```

### Named Sessions

```bash
playwright-cli -s=mytest open https://example.com
playwright-cli -s=mytest click "Login"
playwright-cli -s=mytest snapshot
```

### Video Recording

```bash
playwright-cli video-start
# ... perform actions ...
playwright-cli video-stop
```

## Migrating from Playwright MCP

If you previously used Playwright MCP (`@playwright/mcp`):

1. Install playwright-cli: `npm install -g @playwright/cli@latest`
2. Install browser: `playwright-cli install-browser`
3. Existing `.mcp.json` playwright config can remain (backward compatible)
4. Optionally remove the MCP config: `jq 'del(.mcpServers.playwright)' .mcp.json > tmp && mv tmp .mcp.json`
5. Video files now come from explicit `video-start`/`video-stop` instead of automatic MCP recording

## Troubleshooting

### Browser Not Found

```bash
playwright-cli install-browser
```

### Command Not Found

Ensure global npm bin is in PATH:
```bash
npm install -g @playwright/cli@latest
which playwright-cli
```

## References

- playwright-cli: https://github.com/microsoft/playwright-cli
- Playwright Documentation: https://playwright.dev
