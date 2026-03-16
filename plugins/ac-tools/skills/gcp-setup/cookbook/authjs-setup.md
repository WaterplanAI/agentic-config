# Auth.js (NextAuth) on Cloud Run

How to configure Auth.js v5 with Google OAuth on Cloud Run. This covers the gotchas that are specific to container/reverse-proxy deployments.

## Required Environment Variables

Auth.js needs these env vars in addition to the standard OAuth secrets:

| Variable | Value | Why |
|----------|-------|-----|
| `AUTH_TRUST_HOST` | `true` | Cloud Run terminates TLS at the load balancer. Without this, Auth.js rejects the request because the hostname doesn't match what it expects. **Required for all reverse-proxy deployments.** |
| `AUTH_URL` | `https://<cloud-run-url>` | The canonical URL of your app. Auth.js uses this to construct callback URLs and validate redirects. Must match the deterministic Cloud Run URL. |
| `AUTH_SECRET` | `<random-string>` | Signs session tokens. Generate with `openssl rand -hex 32`. Maps to the `session-secret` entry in `.gcp-setup.yml`. |
| `GOOGLE_CLIENT_ID` | `<oauth-client-id>` | From GCP Console > Google Auth Platform > Clients. |
| `GOOGLE_CLIENT_SECRET` | `<oauth-client-secret>` | From GCP Console > Google Auth Platform > Clients. |

## Callback Path

Auth.js uses `/api/auth/callback/google` — NOT the Passport-style `/auth/google/cb`.

Ensure `.gcp-setup.yml` has:
```yaml
oauth:
  callback_path: /api/auth/callback/google
```

And the OAuth client in GCP Console has **both** redirect URIs registered (see `cookbook/oauth-setup.md`):
- `https://<url>/api/auth/callback/google`
- `https://<url>/auth/google/cb`

## Secrets Manifest

Update `.gcp-setup.yml` secrets to include `AUTH_TRUST_HOST` and `AUTH_URL`:

```yaml
secrets:
  - name: oauth-client-id
    env_var: GOOGLE_CLIENT_ID
    source: "GCP OAuth 2.0 Client ID"
  - name: oauth-client-secret
    env_var: GOOGLE_CLIENT_SECRET
    source: "GCP OAuth 2.0 Client Secret"
  - name: session-secret
    env_var: AUTH_SECRET
    auto_generate: true
    generator: "openssl rand -hex 32"
    source: "Auth.js session signing key"
```

`AUTH_TRUST_HOST` and `AUTH_URL` are NOT secrets — set them as plain env vars in the CloudBuild deploy step:

```yaml
# In cloudbuild-stage.yaml, Step 3 (deploy):
- '--update-env-vars=AUTH_TRUST_HOST=true,AUTH_URL=https://<stage-url>'
```

### CloudBuild: env vars vs secrets

`AUTH_URL` and `AUTH_TRUST_HOST` are NOT secrets — they go in `--set-env-vars`, not `--set-secrets`. Add this line to the deploy step in both `cloudbuild-stage.yaml` and `cloudbuild-prod.yaml`:

```yaml
# In the gcloud run deploy step, add after --set-secrets:
- "--set-env-vars=AUTH_URL=https://<deterministic-cloud-run-url>,AUTH_TRUST_HOST=true"
```

The deterministic URL follows the pattern `https://<service-name>-<project-number>.<region>.run.app`. Compute it from config (see `cookbook/environments.md`).

**Stage example:**
```yaml
- "--set-env-vars=AUTH_URL=https://<stage-service>-<stage-project-num>.<region>.run.app,AUTH_TRUST_HOST=true"
```

**Prod example:**
```yaml
- "--set-env-vars=AUTH_URL=https://<prod-service>-<prod-project-num>.<region>.run.app,AUTH_TRUST_HOST=true"
```

Without `AUTH_URL`, Auth.js resolves the callback URL to the internal bind address (`0.0.0.0:8080`) instead of the public Cloud Run URL, causing `redirect_uri_mismatch`.

## Auth.js Configuration

Minimal `src/auth.ts` (or `auth.ts`):

```typescript
import NextAuth from "next-auth"
import Google from "next-auth/providers/google"

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
    }),
  ],
  // AUTH_TRUST_HOST=true handles reverse-proxy trust
  // AUTH_URL is read automatically from the environment
  // AUTH_SECRET is read automatically from the environment
})
```

## Domain Restriction

Google's account picker always shows ALL accounts logged into the browser. This is expected and cannot be controlled by the app. Domain restriction happens **after** the user picks an account.

### Two layers of defense

1. **GCP consent type (Internal):** Filters at Google's level — only allows accounts from the Google Workspace org. **However**, this only works if the GCP project belongs to the same Google Workspace organization. If your GCP project is outside the org (common for shared projects like `internal-tools-stage`), Google treats consent as External regardless of the setting.

2. **App-level domain check (primary defense):** Validates the email domain in Auth.js `signIn` callback. This is the actual security boundary — it works regardless of GCP project org ownership.

### Three layers of domain filtering

| Layer | Mechanism | Where | Enforced? |
|-------|-----------|-------|-----------|
| 1. `hd` authorization param | Hints Google to pre-filter the account picker | Google's UI | No — UI hint only, can be bypassed |
| 2. GCP consent type (Internal) | Only allows Workspace org accounts | Google's OAuth server | Yes, but only if GCP project is in the org |
| 3. `signIn` callback | Validates email domain server-side | Your app | Yes — primary defense |

All three should be configured. Layer 3 is the only one you fully control.

### Auth.js signIn callback

Add domain restriction to your Auth.js config. The `authorization.params.hd` hints the account picker, and the `signIn` callback enforces server-side:

```typescript
import NextAuth from "next-auth"
import Google from "next-auth/providers/google"

const ALLOWED_DOMAIN = process.env.ALLOWED_DOMAIN // e.g., "example.com"

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
      // Layer 1: hint Google to pre-filter the account picker (UI only, not enforced)
      authorization: {
        params: { hd: ALLOWED_DOMAIN, prompt: "select_account" },
      },
    }),
  ],
  callbacks: {
    signIn({ account, profile }) {
      // Layer 3: server-side enforcement (primary defense)
      if (!ALLOWED_DOMAIN) return true // no restriction configured
      if (account?.provider !== "google") return true

      // Primary check: email domain suffix (authoritative)
      const email = profile?.email ?? ""
      if (!email.endsWith(`@${ALLOWED_DOMAIN}`)) return false

      // Secondary check: hosted domain claim (defense-in-depth)
      if (profile?.hd !== ALLOWED_DOMAIN) return false

      return true
    },
  },
})
```

### Setting the domain

Add `ALLOWED_DOMAIN` to your `.gcp-setup.yml` secrets manifest or set it as a plain env var in CloudBuild:

```yaml
# In cloudbuild deploy step:
- "--set-env-vars=AUTH_URL=https://...,AUTH_TRUST_HOST=true,ALLOWED_DOMAIN=example.com"
```

The domain value comes from `.gcp-setup.yml` `oauth.domain_restriction`.

## Common Errors

### UntrustedHost

```
[auth][error] UntrustedHost: Host must be trusted.
```

**Cause:** `AUTH_TRUST_HOST` is not set or not `true`. Cloud Run sits behind a load balancer that terminates TLS — Auth.js sees the request as coming from an untrusted host.

**Fix:** Set `AUTH_TRUST_HOST=true` as an env var in the Cloud Run service:
```bash
SERVICE=$(yq -r '.projects.stage.service_name' .gcp-setup.yml)
REGION=$(yq -r '.region' .gcp-setup.yml)
PROJECT=$(yq -r '.projects.stage.id' .gcp-setup.yml)
gcloud run services update "$SERVICE" \
  --region="$REGION" --project="$PROJECT" \
  --update-env-vars="AUTH_TRUST_HOST=true"
```

Or add it to `cloudbuild-stage.yaml` in the deploy step.

### CallbackRouteError / redirect_uri_mismatch

```
[auth][error] CallbackRouteError
Error 400: redirect_uri_mismatch
```

**Cause:** The redirect URI registered in GCP Console doesn't match Auth.js callback path.

**Fix:** Register `https://<cloud-run-url>/api/auth/callback/google` in GCP Console > Google Auth Platform > Clients. See `cookbook/oauth-setup.md` Step 3.

### AUTH_URL mismatch

```
[auth][error] MissingCSRFToken
```

**Cause:** `AUTH_URL` doesn't match the actual URL the user is accessing. This causes CSRF token validation to fail.

**Fix:** Set `AUTH_URL` to the **deterministic** Cloud Run URL:
```bash
PROJECT=$(yq -r '.projects.stage.id' .gcp-setup.yml)
SERVICE=$(yq -r '.projects.stage.service_name' .gcp-setup.yml)
REGION=$(yq -r '.region' .gcp-setup.yml)
PROJECT_NUM=$(gcloud projects describe "$PROJECT" --format="value(projectNumber)")
echo "AUTH_URL=https://${SERVICE}-${PROJECT_NUM}.${REGION}.run.app"
```

Do NOT use the legacy hash-based URL (`*-uc.a.run.app`).

### Session secret not set

```
[auth][error] MissingSecret: Please define a `secret`
```

**Cause:** `AUTH_SECRET` env var is missing or empty.

**Fix:** Ensure the `session-secret` secret in Secret Manager has a version, and the CloudBuild deploy step maps it via `--set-secrets=AUTH_SECRET=session-secret:latest`.

## Local Development

Auth.js local setup differs from Cloud Run in a few ways.

### `.env.local` file

Create `.env.local` in your project root (never committed):
```bash
# .env.local
GOOGLE_CLIENT_ID=<client-id-from-gcp-console>
GOOGLE_CLIENT_SECRET=<client-secret-from-gcp-console>
AUTH_SECRET=local-dev-secret-any-random-string
AUTH_URL=http://localhost:3000
```

### What's different locally

| Variable | Cloud Run | Local Dev |
|----------|-----------|-----------|
| `AUTH_TRUST_HOST` | `true` (required) | Not needed (localhost is trusted by default) |
| `AUTH_URL` | `https://<cloud-run-url>` | `http://localhost:<port>` (note: `http`, not `https`) |
| `AUTH_SECRET` | From Secret Manager | Any random string |
| OAuth credentials | From Secret Manager | From `.env.local` file |

### GCP Console: register localhost

In the OAuth client, add these redirect URIs (use your dev port -- 3000 for Next.js):
- **JavaScript origin:** `http://localhost:3000`
- **Redirect URI:** `http://localhost:3000/api/auth/callback/google`

Google OAuth allows `http://` only for `localhost` origins. All other origins require `https://`.

### Quick test

```bash
npm run dev
# Open http://localhost:3000
# Click sign in -> should redirect to Google -> should return to localhost
```

If you get `redirect_uri_mismatch`, verify the localhost redirect URI is registered in GCP Console and the port matches.

## Checklist

Before deploying with Auth.js:

- [ ] `.gcp-setup.yml` `oauth.callback_path` set to `/api/auth/callback/google`
- [ ] GCP Console OAuth client has both redirect URIs registered
- [ ] `AUTH_TRUST_HOST=true` set in Cloud Run env vars
- [ ] `AUTH_URL` set to deterministic Cloud Run URL
- [ ] `AUTH_SECRET` mapped from Secret Manager via `--set-secrets`
- [ ] `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` mapped from Secret Manager
- [ ] `src/auth.ts` reads from `process.env` (not hardcoded)
