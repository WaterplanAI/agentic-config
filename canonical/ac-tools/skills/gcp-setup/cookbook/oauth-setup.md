# OAuth 2.0 Setup Guide

## Overview

Google OAuth 2.0 with configurable domain restriction. One OAuth client per environment (local dev, staging, prod). OAuth setup is conditional on `oauth.enabled: true` in `.gcp-setup.yml`.

## Important: gcloud Limitations

The `gcloud` CLI can configure the **Google Auth Platform branding** (brand) but **cannot create regular OAuth 2.0 web clients** -- only IAP-managed clients. Always create OAuth clients via Console UI.

## Step 1: Google Auth Platform Setup (one-time per GCP project)

> **SECURITY WARNING:** If your config specifies `consent_type: Internal`, you MUST set the Audience to **"Internal"**. Do NOT select "External" unless required. Selecting External would allow ANY Google account to reach the OAuth flow, removing the primary authentication boundary. This weakens defense-in-depth and cannot be compensated by app-level checks alone.

### Console UI

**a. Branding**
1. Go to **Google Auth Platform > Branding** in [GCP Console](https://console.cloud.google.com/)
2. Fill in:
   - App name: Your application name
   - User support email: Your admin email
   - Authorized domain: Your configured domain
   - Developer contact: Your admin email
3. Save

**b. Audience**
1. Go to **Google Auth Platform > Audience**
2. Set to configured consent type (default: **Internal**)
3. Save

**c. Data Access**
1. Go to **Google Auth Platform > Data Access**
2. Add scopes: `openid`, `email`, `profile`
3. Save

### gcloud CLI (branding only)
```bash
gcloud auth list                          # verify active account
gcloud config set project <PROJECT_ID>
gcloud services enable iap.googleapis.com
gcloud components install alpha --quiet
gcloud alpha iap oauth-brands list        # check if already exists
gcloud alpha iap oauth-brands create \
  --application_title="<APP_NAME>" \
  --support_email="<ADMIN_EMAIL>"
```
Then proceed to Console UI for Audience, Data Access, and client creation (Step 2).

## Step 2: Compute Cloud Run URLs

Cloud Run URLs are deterministic:
```
https://<service-name>-<project-number>.<region>.run.app
```

Get project numbers:
```bash
CONFIG=".gcp-setup.yml"
STAGE=$(yq -r '.projects.stage.id' "$CONFIG")
PROD=$(yq -r '.projects.prod.id' "$CONFIG")
gcloud projects describe "$STAGE" --format="value(projectNumber)"
gcloud projects describe "$PROD" --format="value(projectNumber)"
```

> **Warning:** Do NOT use `status.url` to get the service URL. It returns a legacy hash-based URL that differs from the deterministic format. Always compute deterministic URLs.

## Step 3: Create OAuth 2.0 Client IDs (Console UI only)

Read the callback path from config: `yq -r '.oauth.callback_path' .gcp-setup.yml`

**Repeat for each environment:**

| Environment | Client Name | JS Origins | Redirect URIs (add BOTH) |
|-------------|-------------|------------|--------------------------|
| Local Dev | `<App> Local Dev` | `http://localhost:<dev-port>` | `http://localhost:<dev-port>/auth/google/cb`, `http://localhost:<dev-port>/api/auth/callback/google` |
| Staging | `<App> Staging` | `https://<stage-url>` | `https://<stage-url>/auth/google/cb`, `https://<stage-url>/api/auth/callback/google` |
| Production | `<App> Production` | `https://<prod-url>` | `https://<prod-url>/auth/google/cb`, `https://<prod-url>/api/auth/callback/google` |

### Common Callback Paths

| Framework | Callback Path |
|-----------|--------------|
| Express + Passport | `/auth/google/cb` |
| Auth.js (NextAuth) | `/api/auth/callback/google` |
| Custom | Check your auth route definition |

Register **both** paths in the OAuth client's redirect URIs. This prevents `redirect_uri_mismatch` errors when switching frameworks or auth libraries, and costs nothing (unused URIs are harmless).

> **Using Auth.js (NextAuth)?** See `cookbook/authjs-setup.md` for Cloud Run-specific configuration including `AUTH_TRUST_HOST`, `AUTH_URL`, and the full secrets setup.

### Local Development Setup

OAuth requires registering `localhost` redirect URIs so you can test authentication locally.

**Common dev ports by framework:**

| Framework | Default Port |
|-----------|-------------|
| Next.js | `3000` |
| Express | `3000` or `8080` |
| FastAPI | `8000` |
| Go (net/http) | `8080` |

**Important:**
- Use `http://` (not `https://`) for localhost — Google OAuth allows `http` only for `localhost`
- Register both callback paths for localhost too (see table above)
- Use the **same OAuth client** as staging — just add the localhost URIs to it, or create a separate `Local Dev` client

**Example redirect URIs for Next.js (port 3000):**
- `http://localhost:3000/api/auth/callback/google`
- `http://localhost:3000/auth/google/cb`

**Example JavaScript origins:**
- `http://localhost:3000`

**Local `.env` file** (never committed — see `cookbook/environments.md`):
```bash
# .env.local (or .env)
GOOGLE_CLIENT_ID=<client-id-from-gcp-console>
GOOGLE_CLIENT_SECRET=<client-secret-from-gcp-console>
SESSION_SECRET=local-dev-secret-change-me
```

For Auth.js-specific local setup, see `cookbook/authjs-setup.md`.

### Steps:
1. Go to **Google Auth Platform > Clients** in GCP Console
2. Click **Create Client** (or edit existing staging client to add localhost URIs)
3. Application type: **Web application**
4. Enter name, origins, and **both** redirect URIs from table above (including localhost)
5. Click **Create**
6. Copy **Client ID** -> populate the configured OAuth client ID secret
7. Copy **Client Secret** -> populate the configured OAuth client secret

## Domain Restriction Behavior

### Google account picker shows all accounts

Google's OAuth account picker always displays ALL accounts logged into the browser. This is expected behavior and cannot be controlled by the app. Domain restriction happens **after** the user selects an account.

### Internal consent type: when it works

Setting consent type to **Internal** in GCP Console > Google Auth Platform > Audience tells Google to only allow accounts from the Google Workspace organization. **However:**

- This only works if the GCP project **belongs to** the Google Workspace organization
- If the GCP project is outside the org (common for shared projects, sandbox accounts, or personal billing), Google treats consent as **External regardless** of the setting
- When External, any Google account can complete the OAuth flow — the only defense is your app-level check

### Defense-in-depth approach

| Layer | What it does | Limitation |
|-------|-------------|------------|
| `hd` authorization param | Hints Google to pre-filter account picker | UI hint only — can be bypassed by modifying the request |
| Internal consent type | Blocks non-org accounts at Google's OAuth server | Only works if GCP project is in the Workspace org |
| App-level domain check | Validates email domain in `signIn` callback | None — fully controlled by your code |

**Always implement app-level domain restriction.** Internal consent and `hd` param are defense-in-depth, not primary defenses.

For Auth.js implementation, see `cookbook/authjs-setup.md` "Domain Restriction" section.

For Express + Passport, validate `profile._json.hd` AND email suffix in the verify callback.

## Multi-App: Shared OAuth Client

When multiple apps share the same GCP project, a single OAuth client can authenticate users for all of them. This is the recommended approach -- it reduces Console configuration and simplifies credential management.

### How It Works

- Google Auth Platform branding and audience are **project-level** (configured once)
- One OAuth 2.0 Client ID can list **multiple redirect URIs**
- Each app adds its own callback URL to the same client

### Adding Redirect URIs for Additional Apps

In GCP Console > Google Auth Platform > Clients, edit the existing OAuth client and add:

| App | Authorized JavaScript Origin | Authorized Redirect URI |
|-----|------------------------------|------------------------|
| Dashboard | `https://dashboard-stage-<num>.<region>.run.app` | `https://dashboard-stage-<num>.<region>.run.app/auth/google/cb` |
| API Gateway | `https://api-gw-stage-<num>.<region>.run.app` | `https://api-gw-stage-<num>.<region>.run.app/auth/google/cb` |

Repeat for prod project's OAuth client.

### Shared vs Separate OAuth Clients

| Approach | Pros | Cons |
|----------|------|------|
| **Shared** (recommended) | Less Console configuration, single set of credentials | Rotating credentials affects all apps |
| **Separate** (per-app) | Independent credential rotation, clearer audit trail | More clients to manage, more secrets to populate |

For most teams, a shared client is simpler. Use separate clients when:
- Apps have different security requirements
- Independent credential rotation is a hard requirement
- Apps are owned by different sub-teams

### Secret Sharing

With a shared OAuth client, apps can either:
- **Reference the same secrets** -- all apps use `oauth-client-id` and `oauth-client-secret` (simpler, but rotating affects all)
- **Copy to per-app secrets** -- each app has `dashboard-oauth-client-id`, `apigw-oauth-client-id` (same values, independent rotation path)

### Alternatives to Per-App OAuth Registration

If your team deploys many apps to the same GCP project, two patterns eliminate per-app Console changes:

**IAP (recommended for internal tools):** Google Cloud Identity-Aware Proxy handles auth at the infrastructure level. Enable per service with `gcloud beta run deploy --iap`. No OAuth clients to manage, no redirect URIs, no extra services. Trade-off: no custom login UI. See `cookbook/iap-setup.md`.

**Auth-proxy:** A single auth-proxy service handles all Google OAuth interactions -- registered once in the Console. Future apps delegate to the proxy. Gives full control over login UI. See `cookbook/auth-proxy.md`.

## Step 4: Populate Secrets

After creating OAuth clients, populate the secrets:
```bash
# Stage
printf '%s' '<CLIENT_ID>' | gcloud secrets versions add <oauth-client-id-secret> --data-file=- --project=<STAGE_PROJECT>
printf '%s' '<CLIENT_SECRET>' | gcloud secrets versions add <oauth-client-secret-secret> --data-file=- --project=<STAGE_PROJECT>

# Prod (different credentials!)
printf '%s' '<CLIENT_ID>' | gcloud secrets versions add <oauth-client-id-secret> --data-file=- --project=<PROD_PROJECT>
printf '%s' '<CLIENT_SECRET>' | gcloud secrets versions add <oauth-client-secret-secret> --data-file=- --project=<PROD_PROJECT>
```

## Step 5: Verify

```bash
# Quick check -- should redirect to Google login (if OAuth enabled)
curl -sI <APP_URL>/auth/google | head -5
# Expected: HTTP/1.1 302 Found with Location: https://accounts.google.com/...
```

## 2nd-gen GitHub Connection (for Cloud Build)

This is separate from OAuth but also requires Console UI. **Connection data MUST be encrypted with a customer-managed key (CMEK).**

### Pre-requisite: CMEK Encryption Key + Cloud Build P4SA Permissions

Before creating the connection, the CMEK infrastructure and IAM permissions must exist. This is automated by `tools/provision.sh --cmek-only`, which:
1. Enables `cloudkms.googleapis.com` and `secretmanager.googleapis.com`
2. Provisions the Secret Manager service agent
3. Creates the configured KMS keyring and key in the same region
4. Grants the Secret Manager service agent `cryptoKeyEncrypterDecrypter` on the key
5. Grants the Cloud Build P4SA `roles/secretmanager.admin` with a **20-minute auto-expiring condition** -- required temporarily for storing the GitHub OAuth token during connection creation.

> Without step 5, connection creation fails with: `Permission error: Cloud Build P4SA needs secretmanager.secrets.create + secretmanager.secrets.setIamPolicy to store the GitHub token`

Verify the key exists:
```bash
KMS_KEYRING=$(yq -r '.kms.keyring' .gcp-setup.yml)
KMS_KEY=$(yq -r '.kms.key' .gcp-setup.yml)
REGION=$(yq -r '.region' .gcp-setup.yml)

gcloud kms keys describe "$KMS_KEY" \
  --keyring="$KMS_KEYRING" \
  --location="$REGION" \
  --project=<PROJECT_ID> \
  --format="value(name)"
```

### Create the Connection

1. Open `https://console.cloud.google.com/cloud-build/repositories/2nd-gen?project=<PROJECT_ID>`
2. Click **Create Host Connection** -> GitHub
3. Configure (fill in this order -- the KMS key picker filters by region, so region must be set first):
   - **Region:** As configured in `.gcp-setup.yml`
   - **Name:** As configured in `github.connection_name`
   - **Encryption:** Select the configured KMS keyring/key
4. Click **Connect** -> Authorize the Cloud Build GitHub App for your organization
5. After connection is created, **Link repository:**
   - Click the connection -> **Link repository**
   - Select the target repository
   - Click **Link**

> **SECURITY WARNING:** Do NOT skip the encryption key. Google-managed encryption is NOT acceptable. The connection stores GitHub OAuth tokens in Secret Manager -- these MUST be encrypted with the customer-managed key for key rotation control and audit compliance.

Repeat for both stage and prod projects.
