# OAuth 2.0 Setup Guide

Setup guide for personal Google account authentication.

## Quick Setup (Recommended)

Use the setup CLI for automated configuration:

```bash
# With gcloud CLI installed (enables APIs automatically)
uv run core/skills/gsuite/tools/setup.py init --project YOUR_PROJECT_ID

# Without gcloud (prints direct console URLs)
uv run core/skills/gsuite/tools/setup.py init
```

## Manual Setup

### Step 1: Enable APIs (one click)

[Enable all GSuite APIs](https://console.cloud.google.com/flows/enableapi?apiid=sheets.googleapis.com,docs.googleapis.com,slides.googleapis.com,drive.googleapis.com,gmail.googleapis.com,calendar-json.googleapis.com,tasks.googleapis.com,people.googleapis.com)

This enables: Sheets, Docs, Slides, Drive, Gmail, Calendar, Tasks, People APIs.

### Step 2: Configure OAuth Consent

[Open OAuth Consent Screen](https://console.cloud.google.com/apis/credentials/consent)

1. Select "External" (or "Internal" for Workspace)
2. App name: GSuite Skill
3. User support email: Your email
4. Developer contact: Your email
5. Add your email as test user (for External apps)

### Step 3: Create Credentials

[Create OAuth Client](https://console.cloud.google.com/apis/credentials/oauthclient)

1. Type: Desktop application
2. Name: GSuite Skill Desktop
3. Click Create
4. Download the JSON file

### Step 4: Install Credentials

```bash
mkdir -p ~/.agents/gsuite
mv ~/Downloads/client_secret_*.json ~/.agents/gsuite/credentials.json
```

### Step 5: Authenticate

```bash
uv run core/skills/gsuite/tools/auth.py add
```

This opens a browser for OAuth consent. After authorization, tokens are stored in:
`~/.agents/gsuite/accounts/<your-email>/token.json`

## Adding More Accounts

Just run `auth.py add` again - it reuses your credentials.json:

```bash
uv run core/skills/gsuite/tools/auth.py add
```

Each account gets its own token in `~/.agents/gsuite/accounts/<email>/token.json`.

## Verify Setup

```bash
# Check setup status
uv run core/skills/gsuite/tools/setup.py check

# Or view account status
uv run core/skills/gsuite/tools/auth.py status
```

## Troubleshooting

- **Error 400: redirect_uri_mismatch**: Ensure Desktop application type selected
- **Access blocked**: Add yourself as test user in OAuth consent screen
- **Token refresh failed**: Re-run `auth.py add` to re-authenticate
