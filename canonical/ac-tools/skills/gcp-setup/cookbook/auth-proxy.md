# Auth-Proxy Pattern

## Problem

When multiple apps share a GCP project with OAuth, each new app requires manually adding redirect URIs in the GCP Console. Google provides NO API for managing OAuth client redirect URIs -- it is Console-only. This does not scale for growing teams deploying frequent new services.

## Solution: Centralized Auth-Proxy

Deploy a single **auth-proxy** Cloud Run service that handles all Google OAuth interactions. Register its URLs once in the GCP Console. Future apps delegate authentication to the proxy -- no additional Console configuration needed per app.

## Architecture

### Flow

```
User clicks "Login" on any app
  |
  v
App redirects to auth-proxy:
  GET https://auth-proxy-<num>.<region>.run.app/auth/start
      ?return_url=https://my-app-<num>.<region>.run.app/auth/callback
  |
  v
Auth-proxy validates return_url against allowlist
Auth-proxy stores return_url in state parameter
Auth-proxy redirects to Google OAuth
  (redirect_uri = auth-proxy's own callback -- the ONLY one registered in Console)
  |
  v
Google authenticates user, redirects back to auth-proxy:
  GET https://auth-proxy-<num>.<region>.run.app/auth/google/cb?code=...&state=...
  |
  v
Auth-proxy exchanges code for Google tokens
Auth-proxy extracts user info (email, name, domain)
Auth-proxy enforces domain restriction
Auth-proxy signs a short-lived JWT with user info
Auth-proxy redirects to the stored return_url:
  302 https://my-app-<num>.<region>.run.app/auth/callback?token=<SIGNED_JWT>
  |
  v
App receives JWT at /auth/callback
App verifies JWT signature (shared signing secret)
App creates session
```

### Components

| Component | Responsibility |
|-----------|---------------|
| **Auth-proxy** (this app) | Google OAuth flow, domain restriction, JWT signing, return_url validation |
| **Client app** (future apps) | Redirect to proxy, JWT verification, session management |
| **Shared signing secret** | HMAC key used by proxy to sign and clients to verify JWTs |

## Auth-Proxy Setup

When running the `gcp-setup` skill with `oauth.mode: auth-proxy`, the standard OAuth setup (Phase 4) registers the proxy's own Cloud Run URLs with Google. No extra Console steps beyond the normal flow.

### What the Proxy Must Implement

1. **`GET /auth/start`** -- accepts `return_url` query parameter, validates it against an allowlist (see Security section), stores it in an encrypted state parameter or server-side session, redirects to Google OAuth
2. **`GET /auth/google/cb`** (or `/api/auth/callback/google` for Auth.js) -- Google redirects here after authentication. Proxy exchanges the authorization code for tokens, extracts user info, checks domain restriction, signs a JWT with user info, redirects to the stored `return_url` with `?token=<JWT>`
3. **Domain restriction** -- same defense-in-depth as standalone apps (see `cookbook/oauth-setup.md` "Domain Restriction Behavior")
4. **`return_url` validation** -- MUST validate against an allowlist of known app URLs to prevent open redirect attacks (see Security section)

### Proxy Secrets

The proxy uses the same secrets as a standalone OAuth app, plus a JWT signing secret:

| Secret | Env Var | Purpose |
|--------|---------|---------|
| `oauth-client-id` | `GOOGLE_CLIENT_ID` | Google OAuth Client ID |
| `oauth-client-secret` | `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret |
| `session-secret` | `SESSION_SECRET` | Proxy's own session signing (for state management) |
| `auth-proxy-jwt-secret` | `AUTH_PROXY_JWT_SECRET` | Signs tokens sent to client apps |

Add the JWT signing secret to the proxy's `.gcp-setup.yml`:

```yaml
secrets:
  # ... existing OAuth secrets ...
  - name: auth-proxy-jwt-secret
    env_var: AUTH_PROXY_JWT_SECRET
    auto_generate: true
    generator: "openssl rand -hex 32"
    source: "Shared JWT signing key for auth-proxy tokens"
```

## Security: return_url Allowlist

The proxy MUST validate `return_url` against an allowlist of known app URLs. Without this, the proxy becomes an open redirector -- an attacker could craft a URL that redirects authenticated users to a malicious site with a valid JWT.

### Configuration

Store the allowlist as a comma-separated env var in the CloudBuild deploy step:

```bash
# In cloudbuild deploy step:
- "--set-env-vars=ALLOWED_RETURN_URLS=https://app1-<num>.<region>.run.app,https://app2-<num>.<region>.run.app"
```

### Validation Rules

- Match scheme (`https://` only, except `http://localhost` for local dev)
- Match full origin (scheme + host + port) against the allowlist
- Reject any `return_url` not in the allowlist with HTTP 400
- Do NOT use substring matching -- use exact origin comparison

### Updating the Allowlist

When adding a new client app:

1. Compute the new app's deterministic Cloud Run URL
2. Add it to `ALLOWED_RETURN_URLS` in the proxy's CloudBuild deploy step
3. Redeploy the proxy (or use a dynamic allowlist in Firestore for zero-downtime updates)

## Client App Integration

Future apps that use the auth-proxy do NOT need `oauth.enabled: true` in their `.gcp-setup.yml`. They do not interact with Google OAuth directly.

### Client App Config

```yaml
# client-app/.gcp-setup.yml
oauth:
  enabled: false    # no direct Google OAuth needed
```

The client app needs one env var pointing to the proxy:

```bash
# In cloudbuild deploy step:
- "--set-env-vars=AUTH_PROXY_URL=https://<auth-proxy-service>-<project-num>.<region>.run.app"
```

### Client App Secrets

```yaml
# client-app/.gcp-setup.yml
secrets:
  - name: auth-proxy-jwt-secret
    env_var: AUTH_PROXY_JWT_SECRET
    source: "Shared JWT signing key (same as auth-proxy)"
  - name: session-secret
    env_var: SESSION_SECRET
    auto_generate: true
    generator: "openssl rand -hex 32"
    source: "App session signing key"
```

No `oauth-client-id` or `oauth-client-secret` needed -- the client app never talks to Google.

### Client App Flow

1. **Login route** (`/login` or similar) -- redirects to:
   ```
   ${AUTH_PROXY_URL}/auth/start?return_url=https://<this-app-url>/auth/callback
   ```
2. **Callback route** (`/auth/callback`) -- receives `?token=<JWT>`:
   - Verify JWT signature using the shared `AUTH_PROXY_JWT_SECRET`
   - Check `exp` claim (reject expired tokens)
   - Extract user info (email, name) from claims
   - Create app session
   - Redirect to app home page

### Local Development

For local development with the auth-proxy:

- The proxy must include `http://localhost:<port>` in its `ALLOWED_RETURN_URLS`
- Set `AUTH_PROXY_URL` in the client app's `.env.local` to the deployed proxy URL (stage environment)
- Or run the proxy locally and point to `http://localhost:<proxy-port>`

## JWT Token Format

Recommended claims for the token the proxy sends to client apps:

| Claim | Value | Purpose |
|-------|-------|---------|
| `sub` | Google user ID | Stable user identifier |
| `email` | User email | Display and authorization |
| `name` | User display name | Display |
| `hd` | Hosted domain | Domain verification (defense-in-depth) |
| `iat` | Issued-at timestamp | Token freshness |
| `exp` | Expiration (30-60 seconds from `iat`) | Prevent replay |

The token is intentionally **short-lived** (30-60 seconds) because it is only used during the redirect hop from proxy to client app. The client app exchanges it for a long-lived session immediately upon receipt.

## When to Use Auth-Proxy vs Standalone

| Scenario | Recommendation |
|----------|---------------|
| Single app | Standalone |
| 2-3 apps, infrequent changes | Standalone (shared OAuth client, add URIs manually) |
| 5+ apps, growing team | Auth-proxy |
| Apps across different GCP projects | Auth-proxy (proxy in one project, clients anywhere) |
| Strict per-app OAuth isolation needed | Standalone (separate clients per app) |

## Adding a New Client App (Checklist)

1. Add the new app's Cloud Run URL to the proxy's `ALLOWED_RETURN_URLS` env var
2. Redeploy the proxy (or update dynamic allowlist)
3. In the new app: set `AUTH_PROXY_URL` env var pointing to the proxy
4. In the new app: add `auth-proxy-jwt-secret` to secrets manifest (reference the proxy's secret)
5. Implement login redirect and `/auth/callback` route in the new app
6. No GCP Console changes needed
