# ac-tools

Productivity utilities -- integrations, dry-run, prototyping, asset management, and more.

## Installation

### From marketplace

```bash
claude plugin marketplace add <owner>/agentic-config
claude plugin install ac-tools@agentic-plugins
```

### Scopes

```bash
claude plugin install ac-tools@agentic-plugins --scope user
claude plugin install ac-tools@agentic-plugins --scope project
claude plugin install ac-tools@agentic-plugins --scope local
```

## Skills

| Skill | Description |
|-------|-------------|
| `ac-issue` | Report issues to agentic-config repository via GitHub CLI |
| `adr` | Document architecture decisions with auto-numbering |
| `agentic-export` | Export project assets to agentic-config repository |
| `agentic-import` | Import external assets into agentic-config repository |
| `agentic-share` | Shared core logic for asset import/export (internal) |
| `cpc` | Clipboard-powered code exchange |
| `dr` | Alias for dry-run |
| `dry-run` | Simulate command execution without file modifications |
| `gsuite` | Google Suite integration (Sheets, Docs, Slides, Drive, Gmail, Calendar, Tasks) |
| `had` | Alias for human-agentic-design |
| `human-agentic-design` | Interactive HTML prototype generator |
| `milestone` | Validate backlog and generate milestone/release notes |
| `improve-agents-md` | Generate and update AGENTS.md (CLAUDE.md) with auto-detected project tooling |
| `setup-voice-mode` | Configure voice mode for conversational interaction |
| `single-file-uv-scripter` | Create self-contained Python scripts with PEP 723 inline deps |
| `video-query` | Query video content using Gemini API |

## Hooks

| Hook | Trigger | Description |
|------|---------|-------------|
| `dry-run-guard` | PreToolUse (Write\|Edit\|NotebookEdit\|Bash) | Blocks file writes when dry-run mode is active |
| `gsuite-public-asset-guard` | PreToolUse (Bash) | Prevents accidental public sharing of Google Suite assets |

## Configuration

### Google Suite

Requires Google Cloud project with OAuth 2.0:

```bash
gsuite auth add
gsuite auth status
```

## Usage Examples

```
# Simulate a command without writing files
/dry-run /spec PLAN path/to/spec.md

# Create a self-contained Python script
# (via single-file-uv-scripter skill)

# Analyze video content
/video-query path/to/video.mp4 "What happens in this demo?"

# Create an ADR
/adr "Use PostgreSQL for primary storage"

# Generate milestone notes
/milestone v0.2.0

# Read a Google Sheet
gsuite sheets read <spreadsheet_id> "Sheet1!A1:D10"

# Report an issue
/ac-issue
```

## License

MIT
