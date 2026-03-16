# Security Model

## Defense in Depth

The deployment uses multiple independent security layers. No single layer is the sole defense.

## Layers

### 1. Container Security
- **Non-root execution:** Container should run as non-root user
- **Pinned dependencies:** All packages have exact version pins
- **Multi-stage build:** Source code and dev dependencies excluded from production image
- **.dockerignore:** Excludes `.env`, `.git`, `node_modules`, tests, specs

### 2. Service Account Isolation
- **Runtime SA:** `<sa_prefix.runtime>@<project>.iam.gserviceaccount.com`
  - ONLY permission: per-secret `secretmanager.secretAccessor` (manifest secrets)
  - NO project-level secretAccessor (defensive cleanup removes any)
  - NOT the default compute SA
- **Cloud Build SA:** `<sa_prefix.cloudbuild>@<project>.iam.gserviceaccount.com`
  - `roles/cloudbuild.builds.builder` (build ops)
  - `roles/artifactregistry.writer` (push images)
  - `roles/run.admin` (deploy + set IAM for --allow-unauthenticated)
  - `roles/iam.serviceAccountUser` on runtime SA (impersonation for revisions)

#### Multi-App Isolation in Shared Projects

When multiple apps share the same GCP project, service account isolation is the primary security boundary between apps:

- Each app MUST use a **unique `sa_prefix`** (e.g., `dashboard-rt` / `apigw-rt`). Sharing prefixes across apps means shared SAs, breaking isolation.
- **Per-secret IAM bindings** ensure App A's runtime SA cannot read App B's secrets -- even in the same project.
- Secret names MUST be unique per app (e.g., `dashboard-session-secret` vs `apigw-session-secret`). A collision means both apps' SAs get bound to the same secret.

| Anti-pattern | Risk |
|---|---|
| Same `sa_prefix` across apps | Apps share SAs, breaking least-privilege isolation |
| Generic secret names (e.g., `session-secret`) | Name collision grants cross-app secret access |
| Project-level `secretAccessor` | Any SA can read any secret in the project |

### 3. Secret Management
- **Storage:** GCP Secret Manager only. Never in:
  - Environment variables in cloudbuild YAML
  - Docker image layers
  - Git repository
  - Local .env files in production
- **Access:** Per-secret IAM bindings (not project-level grant)
- **Injection:** `--set-secrets` flag in Cloud Run deploy (mounted as env vars at runtime)
- **Rotation:** New secret version + revision refresh (no redeploy needed)
- **Auto-generated secrets:** Configurable per secret via `auto_generate` + `generator` fields
- **Safe parsing:** `secrets.sh` uses strict .env parsing (validates keys, strips quotes) -- never uses `source` to prevent code injection

### 4. Authentication & Authorization (when OAuth enabled)
- **OAuth 2.0:** Google OAuth with configurable domain restriction
- **App-level domain check (primary defense):** Server-side validation of email domain in the `signIn` callback. This is the only defense you fully control. Checks both email suffix (authoritative) and `hd` claim (defense-in-depth).
- **`hd` authorization param:** Hints Google to pre-filter the account picker to the configured domain. UI improvement only — not a security boundary.
- **Consent screen:** Configurable consent type (default: `Internal`). Only effective if the GCP project belongs to the Google Workspace org. If the project is outside the org, consent is effectively External regardless of the setting.
- **Per-environment OAuth clients:** Separate Client ID/Secret per environment

### 5. Network & CORS
- **Public ingress:** Required for app-level OAuth flow
- **Same-origin CORS:** Production allows only same-origin requests
- **Trust proxy:** Required for Cloud Run TLS termination

### 6. CI/CD Security
- **Approval-gated triggers:** Both stage and prod require manual approval
- **Stage:** Triggered by PR targeting main + approval
- **Prod:** Triggered by push to main + approval
- **User-managed SA:** Cloud Build uses dedicated SA (not default CB SA)
- **Logging:** `CLOUD_LOGGING_ONLY` (no GCS bucket for build logs)

### 7. Encryption (CMEK)
- **Cloud Build GitHub connection:** Encrypted with customer-managed key (Cloud KMS)
  - Keyring and key names configured in `.gcp-setup.yml` (`kms.keyring`, `kms.key`)
  - Secret Manager service agent granted `cryptoKeyEncrypterDecrypter` on the key
  - Cloud Build P4SA granted `roles/secretmanager.admin` **temporarily (20-minute auto-expiring condition)** during connection bootstrap
- **Why mandatory:** GitHub connection stores OAuth tokens in Secret Manager. CMEK provides:
  - Key rotation control (not dependent on Google's schedule)
  - Audit trail via Cloud Audit Logs on KMS operations
  - Ability to revoke access by disabling/destroying the key
  - Compliance with data encryption policies
- **Google-managed encryption is NOT acceptable** for connection data

## What NOT to Do

| Anti-pattern | Why it's dangerous |
|---|---|
| `--update-env-vars=SECRET=value` in cloudbuild | Secrets visible in revision metadata |
| Project-level secretAccessor | Runtime SA can read ALL secrets in project |
| Default compute SA for Cloud Run | Over-privileged, shared across services |
| Same OAuth creds for all envs | Credential rotation affects all environments |
| `roles/run.developer` for CB SA | Cannot set `--allow-unauthenticated` (silent failure) |
| Skip approval on triggers | Untested code auto-deploys to production |
| Skip CMEK on GitHub connection | GitHub OAuth tokens encrypted only by Google-managed keys -- no rotation control, no revocation |
| Using `source` to parse .env files | Arbitrary code execution via crafted .env values |
| Relying solely on Internal consent for domain restriction | Only works if GCP project is in the Workspace org -- bypassed otherwise |
| Checking only `hd` claim without email suffix | `hd` is a hint, not authoritative -- always validate email suffix too |
