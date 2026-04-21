# IAP (Identity-Aware Proxy) Setup Guide

## What is IAP

Google Cloud Identity-Aware Proxy is a managed authentication layer that sits in front of Cloud Run services. It intercepts all requests and requires users to authenticate with Google before reaching your app. No OAuth clients, no redirect URIs, no auth code in your app.

## Prerequisites

- GCP project belongs to a **Google Workspace organization** (required for Internal users)
- `gcloud` CLI with **beta** component: `gcloud components install beta`
- Google Auth Platform configured in the project (one-time, see below)

## One-Time Project Setup

These steps run once per GCP project, not per app.

### 1. Enable required APIs

```bash
gcloud services enable iap.googleapis.com cloudresourcemanager.googleapis.com --project="$PROJECT"
```

The Cloud Resource Manager API is required for IAP IAM policy bindings.

### 2. Configure Google Auth Platform (Console)

1. Go to **Google Auth Platform > Branding** in [GCP Console](https://console.cloud.google.com/)
2. Fill in: App name, User support email, Authorized domain, Developer contact
3. Go to **Audience** and set to **Internal** (restricts to Workspace org)
4. Go to **Data Access** and add scopes: `openid`, `email`, `profile`
5. Save

This is the same Auth Platform setup as standalone OAuth -- the difference is you never create OAuth client IDs manually. IAP auto-creates and manages its own OAuth client when enabled via Console for the first time.

## Per-Service Setup

For each Cloud Run service, four steps:

### 1. Enable IAP on the service

For **existing services** (already deployed):
```bash
gcloud beta run services update "$SERVICE_NAME" \
  --region="$REGION" \
  --iap \
  --project="$PROJECT"
```

For **new deploys** (first deployment):
```bash
gcloud beta run deploy "$SERVICE_NAME" \
  --region="$REGION" \
  --image="$IMAGE" \
  --no-allow-unauthenticated \
  --iap \
  --project="$PROJECT"
```

> **Note:** `gcloud beta run deploy --iap` requires `--image`. For existing services, use `services update --iap` instead.

### 2. Grant IAP service agent invoker permission

IAP needs permission to invoke the Cloud Run service on behalf of authenticated users:

```bash
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
gcloud run services add-iam-policy-binding "$SERVICE_NAME" \
  --region="$REGION" \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com" \
  --role="roles/run.invoker" \
  --project="$PROJECT"
```

### 3. Remove public access

If the service was previously deployed with `--allow-unauthenticated` (public), remove it. Otherwise IAP is bypassed:

```bash
gcloud run services remove-iam-policy-binding "$SERVICE_NAME" \
  --region="$REGION" \
  --member="allUsers" \
  --role="roles/run.invoker" \
  --project="$PROJECT"
```

> **Warning:** If `allUsers` has `roles/run.invoker`, anyone can call the Cloud Run URL directly, completely bypassing IAP. Always verify this binding is removed.

### 4. Grant domain access

```bash
gcloud beta iap web add-iam-policy-binding \
  --resource-type=cloud-run \
  --service="$SERVICE_NAME" \
  --region="$REGION" \
  --member="domain:example.com" \
  --role="roles/iap.httpsResourceAccessor" \
  --project="$PROJECT"
```

To grant individual users instead of a whole domain:

```bash
gcloud beta iap web add-iam-policy-binding \
  --resource-type=cloud-run \
  --service="$SERVICE_NAME" \
  --region="$REGION" \
  --member="user:jane@example.com" \
  --role="roles/iap.httpsResourceAccessor" \
  --project="$PROJECT"
```

## CloudBuild Integration

Add `--iap` and `--no-allow-unauthenticated` to the deploy step in your CloudBuild YAML:

```yaml
# In cloudbuild-stage.yaml, deploy step:
- name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
  entrypoint: gcloud
  args:
    - 'beta'
    - 'run'
    - 'deploy'
    - '${_SERVICE_NAME}'
    - '--image=${_IMAGE}'
    - '--region=${_REGION}'
    - '--no-allow-unauthenticated'
    - '--iap'
    - '--service-account=${_RUNTIME_SA}'
    # ... other flags
```

The IAP agent invoker binding and domain access grant only need to run once (during initial setup), not on every deploy.

## Reading User Identity

IAP injects authenticated user information into request headers.

### Headers

| Header | Value | Example |
|--------|-------|---------|
| `X-Goog-Authenticated-User-Email` | `accounts.google.com:<email>` | `accounts.google.com:jane@example.com` |
| `X-Goog-Authenticated-User-Id` | `accounts.google.com:<id>` | `accounts.google.com:abc123` |
| `X-Goog-IAP-JWT-Assertion` | Signed JWT with full user claims | (JWT string) |

### Reading email (simple)

```javascript
// Express.js example
app.get('/api/me', (req, res) => {
  const rawEmail = req.headers['x-goog-authenticated-user-email'] || '';
  const email = rawEmail.replace('accounts.google.com:', '');
  res.json({ email });
});
```

```python
# FastAPI example
@app.get("/api/me")
def get_me(request: Request):
    raw = request.headers.get("x-goog-authenticated-user-email", "")
    email = raw.removeprefix("accounts.google.com:")
    return {"email": email}
```

## Security: Header Verification

**CRITICAL:** The `X-Goog-Authenticated-User-Email` header can be spoofed if a request bypasses IAP (e.g., direct Cloud Run URL access when `--no-allow-unauthenticated` is accidentally removed). For defense-in-depth:

1. **Always deploy with `--no-allow-unauthenticated`** -- this blocks direct access
2. **Verify the JWT signature** of `X-Goog-IAP-JWT-Assertion` for sensitive operations:

```javascript
// Using google-auth-library
const { OAuth2Client } = require('google-auth-library');
const client = new OAuth2Client();

async function verifyIapJwt(iapJwt, projectNumber, projectId) {
  const ticket = await client.verifySignedJwtWithCertsAsync(
    iapJwt,
    'https://www.gstatic.com/iap/verify/public_key',
    [`/projects/${projectNumber}/global/backendServices/*`,
     `/projects/${projectNumber}/apps/${projectId}`],
    'https://cloud.google.com/iap'
  );
  return ticket.getPayload();
}
```

For most internal tools where `--no-allow-unauthenticated` is enforced, reading the email header directly is sufficient.

## Service-to-Service Authentication

When one IAP-protected service needs to call another IAP-protected service, it must present an OIDC identity token:

```javascript
const { GoogleAuth } = require('google-auth-library');

async function callIapService(url, targetAudience) {
  const auth = new GoogleAuth();
  const client = await auth.getIdTokenClient(targetAudience);
  const response = await client.request({ url });
  return response.data;
}

// targetAudience = the OAuth client ID of the target service's IAP
```

For Cloud Run services calling each other within the same project, use the service's URL as the audience.

## Local Development

IAP does not apply to local development. When running locally:

- The `X-Goog-Authenticated-User-Email` header will not be present
- Your app should handle this gracefully (e.g., use a default dev user)

```javascript
// Development fallback
const email = process.env.NODE_ENV === 'development'
  ? 'dev@example.com'
  : (req.headers['x-goog-authenticated-user-email'] || '').replace('accounts.google.com:', '');
```

Alternatively, set the header manually in your local `.env`:

```bash
# .env.local
DEV_USER_EMAIL=jane@example.com
```

## Secrets

When using IAP mode, OAuth secrets are NOT needed:

| Secret | Needed? | Why |
|--------|---------|-----|
| `oauth-client-id` | No | IAP manages the OAuth client |
| `oauth-client-secret` | No | IAP manages the OAuth client |
| `session-secret` | Only if app has sessions | For signing app-level session cookies |

## Adding a New Service (Checklist)

1. Enable IAP: `gcloud beta run services update <name> --iap` (existing) or `deploy --iap --no-allow-unauthenticated` (new)
2. Grant IAP service agent `roles/run.invoker`
3. Remove `allUsers` from `roles/run.invoker` (if previously public)
4. Grant domain/user access with `roles/iap.httpsResourceAccessor`

No GCP Console changes. No OAuth client configuration. All CLI.

## Limitations

| Limitation | Impact | Workaround |
|------------|--------|------------|
| No custom login UI | Users see Google's IAP interstitial page | None -- use standalone or auth-proxy if custom UI is required |
| Workspace org required | IAP Internal mode needs the GCP project in a Workspace org | Use External mode (less restrictive) or standalone OAuth |
| `gcloud beta` | The `--iap` flag for Cloud Run is in beta | Stable for production use, just requires `gcloud beta` prefix |
| No programmatic OAuth client updates | IAP-created OAuth clients cannot be modified via API | Not needed -- IAP manages its own client automatically |
| Service-to-service auth | Requires OIDC tokens for inter-service calls | See "Service-to-Service Authentication" section above |

## When to Use IAP vs Standalone vs Auth-Proxy

| Scenario | Recommendation |
|----------|---------------|
| Internal tools, Workspace org | **IAP** |
| Custom login page required | Standalone or Auth-proxy |
| Non-Workspace accounts (external users) | Standalone |
| Many apps, growing team, no custom UI needed | **IAP** |
| Many apps, custom UI needed | Auth-proxy |
| Single app | Standalone |
| Service-to-service auth is complex | Standalone (simpler token handling) |
