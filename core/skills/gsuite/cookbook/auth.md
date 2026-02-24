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

## Multi-Credentials & `--authuser` (Multi-Org Setup)

### When This Applies

Use this pattern when authenticating accounts from **different Google organizations** (e.g., a personal Google account + a Workspace org account). Each org requires its own OAuth credentials from its own GCP project.

### Credentials File Convention

Store one credentials file per organization in `~/.agents/gsuite/`:

```
~/.agents/gsuite/
  credentials.json              ← default (used when --credentials not specified)
  credentials-<org-label>.json  ← per-org credentials (e.g., credentials-work.json)
  accounts/
    <account-A>/token.json      ← token for account A (untouched when re-authing B)
    <account-B>/token.json      ← token for account B
```

Tokens are stored **per-account** — re-authenticating one account never affects another.

### `--authuser` Parameter

`--authuser N` tells Google which account to use in the browser's existing session:
- `0` — first (default) Google account in browser
- `1` — second account
- `2` — third account, etc.

Check your browser's account switcher (top-right avatar) to determine the correct index. Without this flag, Google defaults to `authuser=0`, which may authenticate the wrong account.

### Decision Tree

```
Adding a new account?
│
├─ Same org as default credentials.json?
│    └─ uv run auth.py add <account-email> [--authuser N]
│
└─ Different org (separate GCP project)?
     ├─ 1. Obtain credentials JSON from that org's GCP project
     ├─ 2. Save as: ~/.agents/gsuite/credentials-<org-label>.json
     └─ 3. uv run auth.py add <account-email> \
               --credentials credentials-<org-label>.json \
               --authuser N
```

### Re-authenticating an Expired Token (Multi-Org)

When a token expires for an account that uses non-default credentials:

```bash
# Step 1: remove only the expired account's token
uv run core/skills/gsuite/tools/auth.py remove <expired-account-email>

# Step 2: re-add specifying the correct credentials file and authuser index
uv run core/skills/gsuite/tools/auth.py add <expired-account-email> \
  --credentials credentials-<org-label>.json \
  --authuser N
```

**Do NOT** run `auth.py add` without `--credentials` for an org-account — it will open the wrong GCP project's OAuth consent screen and authenticate the wrong account.

### Agent Guidance: Diagnosing Wrong-Credentials Auth

If auth completes but the wrong account is authenticated (e.g., personal instead of work):

1. Check `ls ~/.agents/gsuite/` — look for `credentials-*.json` files
2. Check `auth.py status --json` to see which accounts already have tokens
3. Identify which credentials file belongs to the target org
4. Run remove + re-add with `--credentials <correct-file>` and `--authuser N`

### Different Organization Handling (OAuth Blocked)

When adding an account from a different organization and OAuth fails, use AskUserQuestion:

- Question: "The new account is from a different organization. How would you like to proceed?"
- Header: "Auth method"
- Options:
  - "Option A: Create separate credentials (Recommended)" - Create OAuth credentials in that organization's GCP project
  - "Option B: Add as test user" - Add the account to your existing OAuth consent screen's test users

#### Option A: Separate Credentials (Recommended)

1. Guide user to create GCP project under the new organization
2. Follow oauth-setup.md steps for that project
3. Store credentials as: `~/.agents/gsuite/credentials-<org-label>.json`
4. Re-add: `uv run auth.py add <account-email> --credentials credentials-<org-label>.json --authuser N`

#### Option B: Add as Test User

1. Direct to: https://console.cloud.google.com/apis/credentials/consent
2. Add the account to "Test users" section
3. Retry: `uv run core/skills/gsuite/tools/auth.py add`

**Note**: Option A is recommended because:
- Avoids ongoing test-user limitations
- Respects organization admin policies
- Provides full access within that organization's domain
