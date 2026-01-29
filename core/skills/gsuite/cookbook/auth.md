# Authentication Cookbook

Authentication setup and multi-account management for GSuite skill.

## Commands

```bash
# Check status
uv run core/skills/gsuite/tools/auth.py status --json

# Add account (opens browser for OAuth)
uv run core/skills/gsuite/tools/auth.py add

# Switch active account
uv run core/skills/gsuite/tools/auth.py switch <email>

# Remove account
uv run core/skills/gsuite/tools/auth.py remove <email>
```

## Interactive OAuth Setup

When authentication is missing or user requests setup, use AskUserQuestion for interactive guidance.

### Step 1: Check Status

```bash
uv run core/skills/gsuite/tools/auth.py status --json
```

### Step 2: If No Credentials

Use AskUserQuestion:
- Question: "Which authentication method do you want to set up?"
- Header: "Auth type"
- Options:
  - "Personal OAuth (Recommended)" - For personal Google accounts, simpler setup
  - "Enterprise Service Account" - For Workspace domain-wide delegation, requires admin access

### Step 3: Personal OAuth Setup

1. **Ask for project URL** via AskUserQuestion:
   - Question: "Paste your Google Cloud Console project URL (from browser address bar after selecting your project)"
   - Header: "Project URL"
   - Example: `https://console.cloud.google.com/welcome?project=my-project-123&authuser=1`

2. **Parse URL parameters**:
   - Extract `project` parameter (e.g., `my-project-123`)
   - Extract `authuser` parameter (e.g., `1`) - defaults to `0` if missing

3. **Generate one-click enable APIs URL** and provide to user:
   ```
   https://console.cloud.google.com/flows/enableapi?project={PROJECT}&authuser={AUTHUSER}&apiid=sheets.googleapis.com,docs.googleapis.com,slides.googleapis.com,drive.googleapis.com,gmail.googleapis.com,calendar-json.googleapis.com,tasks.googleapis.com,people.googleapis.com
   ```

4. **Provide consent screen URL**:
   ```
   https://console.cloud.google.com/apis/credentials/consent?project={PROJECT}&authuser={AUTHUSER}
   ```
   - Select "Internal" for Workspace orgs (no verification needed)
   - Select "External" for personal accounts (add yourself as test user)

5. **Provide credentials URL**:
   ```
   https://console.cloud.google.com/apis/credentials/oauthclient?project={PROJECT}&authuser={AUTHUSER}
   ```
   - Type: Desktop application
   - Download JSON to `~/.agents/gsuite/credentials.json`

6. **Authenticate**: `uv run core/skills/gsuite/tools/auth.py add`

7. **Verify**: `uv run core/skills/gsuite/tools/setup.py check`

### Step 4: Enterprise Service Account Setup

1. Read `assets/enterprise-setup.md` for detailed steps
2. Guide progressively:
   - Create service account in Google Cloud Console
   - Enable domain-wide delegation
   - Download JSON key to `~/.agents/gsuite/service-account.json`
   - Configure Admin Console (admin.google.com) with required scopes
3. After key placed: `uv run core/skills/gsuite/tools/auth.py status`

## Updating Existing Users (New API Added)

When new APIs are added to the skill, existing users must:

1. **Enable the new API** - Use the one-click URL above (already-enabled APIs are skipped)
2. **Re-authenticate** - Delete old token and re-auth:
   ```bash
   uv run core/skills/gsuite/tools/auth.py remove <email>
   uv run core/skills/gsuite/tools/auth.py add
   ```

This is required because OAuth tokens are scoped at authentication time.

## Different Organization Handling

When adding an account from a different organization and OAuth fails, use AskUserQuestion:

- Question: "The new account is from a different organization. How would you like to proceed?"
- Header: "Auth method"
- Options:
  - "Option A: Create separate credentials (Recommended)" - Create OAuth credentials in that organization's GCP project
  - "Option B: Add as test user" - Add the email to your existing OAuth consent screen's test users

### Option A: Separate Credentials (Recommended)

1. Guide user to create GCP project under the new organization
2. Follow oauth-setup.md steps for that project
3. Store credentials with org identifier: `~/.agents/gsuite/credentials-<org-domain>.json`
4. Retry auth add

### Option B: Add as Test User

1. Direct to: https://console.cloud.google.com/apis/credentials/consent
2. Add the email to "Test users" section
3. Retry: `uv run core/skills/gsuite/tools/auth.py add`

**Note**: Option A is recommended because:
- Avoids ongoing test-user limitations
- Respects organization admin policies
- Provides full access within that organization's domain
