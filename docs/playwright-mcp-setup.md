# Playwright MCP Setup

This guide provides instructions for setting up Playwright MCP (Model Context Protocol) server for E2E testing with agentic-config.

## Prerequisites

- Node.js v18+ (required for npx and Playwright)
- Claude Desktop or other MCP-compatible client
- Optional: GEMINI_API_KEY environment variable (for video query features)

## Quick Start

### 1. Copy MCP Template

Copy the Playwright MCP configuration template to your project's MCP configuration file:

```bash
cp templates/mcp/playwright.json ~/.claude/.mcp.json
```

If you already have an `.mcp.json` file, merge the Playwright server configuration:

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": [
        "@playwright/mcp@latest",
        "--isolated",
        "--save-video=1920x1080",
        "--viewport-size=1920x1080"
      ]
    }
  }
}
```

### 2. Install Playwright Browsers

Install the required browser binaries:

```bash
npx playwright install
```

### 3. Setup Project Directories

Create directories for video recordings and E2E outputs:

```bash
mkdir -p videos outputs/e2e
```

### 4. Update .gitignore

Add the following entries to your project's `.gitignore` (if not already present):

```
videos/
outputs/
*.webm
```

### 5. Restart Claude Desktop

Restart Claude Desktop to load the new MCP server configuration.

## Configuration Options

The Playwright MCP server supports various command-line arguments:

### Default Configuration

- `--isolated`: Use isolated browser context (recommended for test isolation)
- `--save-video=WxH`: Video recording resolution (default: 1920x1080)
- `--viewport-size=WxH`: Browser viewport size (default: 1920x1080)

### Optional Arguments

- `--headless`: Run browsers in headless mode (recommended for CI environments)
- `--browser=chromium|firefox|webkit`: Specify browser type (default: chromium)
- `--video-dir=<path>`: Custom video output directory (default: ./videos)

### CI/CD Configuration Example

For continuous integration environments, use headless mode:

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": [
        "@playwright/mcp@latest",
        "--isolated",
        "--headless",
        "--save-video=1920x1080",
        "--viewport-size=1920x1080"
      ]
    }
  }
}
```

## Advanced Setup

### Local Package Installation

For better performance and version control, install Playwright MCP locally:

```bash
npm install -D @playwright/mcp
# or
pnpm add -D @playwright/mcp
```

Then update your MCP configuration to use the local installation:

```json
{
  "mcpServers": {
    "playwright": {
      "command": "node_modules/.bin/playwright-mcp",
      "args": [
        "--isolated",
        "--save-video=1920x1080",
        "--viewport-size=1920x1080"
      ]
    }
  }
}
```

### Merging with Existing MCP Configuration

If your project already has an `.mcp.json` file:

1. Read the existing configuration
2. Check if `mcpServers.playwright` already exists
3. If not present, add the Playwright server configuration
4. If present, verify settings or skip to avoid overwriting custom configuration

Example merge script (bash):

```bash
#!/bin/bash
MCP_FILE="$HOME/.claude/.mcp.json"

if [ -f "$MCP_FILE" ]; then
  # Check if playwright server exists
  if python3 -c "import json; cfg=json.load(open('$MCP_FILE')); exit(0 if 'playwright' in cfg.get('mcpServers', {}) else 1)"; then
    echo "Playwright MCP already configured"
  else
    echo "Adding Playwright MCP to existing configuration..."
    # Merge logic here
  fi
else
  cp templates/mcp/playwright.json "$MCP_FILE"
fi
```

## Directory Structure

After setup, your project will have:

```
project/
├── videos/              # Video recordings of browser sessions
│   └── *.webm          # Recording files
├── outputs/
│   └── e2e/            # E2E test screenshots and artifacts
├── .mcp.json           # MCP server configuration (in Claude config dir)
└── .gitignore          # Updated with video/output exclusions
```

## Usage

Once configured, you can interact with Playwright through Claude Desktop using natural language commands:

- "Navigate to https://example.com and take a screenshot"
- "Click the login button and fill in the form"
- "Record a video of the user flow from homepage to checkout"

Video recordings are automatically saved to the `videos/` directory with timestamps.

## Troubleshooting

### Browser Not Found

If you see "Browser not found" errors:

```bash
npx playwright install chromium
```

### Permission Issues

Ensure the videos and outputs directories are writable:

```bash
chmod 755 videos outputs
```

### MCP Server Not Loading

1. Verify Node.js version: `node --version` (should be v18+)
2. Check MCP configuration syntax: `python3 -m json.tool ~/.claude/.mcp.json`
3. Restart Claude Desktop
4. Check Claude Desktop logs for MCP server errors

## References

- Playwright MCP: https://github.com/microsoft/playwright-mcp
- Playwright Documentation: https://playwright.dev
- MCP Protocol: https://modelcontextprotocol.io
