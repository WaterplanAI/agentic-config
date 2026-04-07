# Managing Secrets & Environment Variables

How to add, update, or rotate secrets and environment variables for Cloud Run services, and how to set up a local development environment.

## Architecture

```
+--------------+     +-------------------+     +-----------+
| cloudbuild   |---->| Cloud Run deploy  |---->| Container |
| YAML (git)   |     | --set-secrets     |     | env vars  |
|              |     | --set-env-vars    |     | at runtime|
+--------------+     +-------------------+     +-----------+
                            |
                    +-------+--------+
                    | Secret Manager |  (actual values)
                    +----------------+
```

- **Secrets** -> GCP Secret Manager -> injected via `--set-secrets` in Cloud Build
- **Plain env vars** -> set via `--set-env-vars` in Cloud Build (values in git)
- **Runtime SA** reads secrets at container startup (per-secret IAM, never project-level)

| Environment | GCP Project | Runtime SA | Cloud Build Config |
|-------------|-------------|------------|--------------------|
| Stage | `${STAGE_PROJECT}` | `${RUNTIME_SA_PREFIX}@${STAGE_PROJECT}.iam.gserviceaccount.com` | `cloudbuild-stage.yaml` |
| Production | `${PROD_PROJECT}` | `${RUNTIME_SA_PREFIX}@${PROD_PROJECT}.iam.gserviceaccount.com` | `cloudbuild-prod.yaml` |

## Decision: Secret vs Plain Env Var

| Type | Example | Where it lives | How it's set | Shared via |
|------|---------|---------------|-------------|------------|
| **Secret** | API keys, passwords, OAuth creds | GCP Secret Manager | `--set-secrets` | `gcloud` CLI (never plaintext) |
| **Plain env var** | `NODE_ENV`, feature flags, URLs | cloudbuild YAML (git) | `--set-env-vars` | Git (PR review) |

**Rule of thumb:** if you would not paste it in a group chat, it is a secret.

---

## Local Development Setup (Onboarding)

New team members need a `.env.local` file to run the app locally.

### 1. Copy the template

```bash
cp .env.example .env.local
```

### 2. Get secret values

Secret values are **never** stored in git. Obtain them via:

- **Option A (recommended):** Pull from Secret Manager (requires GCP access)
  ```bash
  PROJECT=${STAGE_PROJECT}  # use stage project for local dev

  # For each secret in the manifest:
  gcloud secrets versions access latest --secret=<secret-name> --project=$PROJECT
  ```

- **Option B:** Ask a teammate to share values via a secure channel (1Password, encrypted DM). **Never** share secrets in Slack channels, email, or git.

### 3. Generate a session secret

```bash
openssl rand -hex 32
```

### 4. Fill in `.env.local` and run

```bash
npm install
npm run dev
```

The `.env.local` file is gitignored -- it will never be committed.

---

## Adding a New Secret

### 1. Create the secret in Secret Manager

```bash
# Replace SECRET_NAME and PROJECT
gcloud secrets create SECRET_NAME --project=PROJECT

# Add a version with the actual value
printf '%s' "secret-value" | gcloud secrets versions add SECRET_NAME --data-file=- --project=PROJECT
```

Do this for **each environment** (stage and prod).

### 2. Grant per-secret IAM to the runtime SA

```bash
RUNTIME_SA="${RUNTIME_SA_PREFIX}@PROJECT.iam.gserviceaccount.com"

gcloud secrets add-iam-policy-binding SECRET_NAME \
  --project=PROJECT \
  --member="serviceAccount:$RUNTIME_SA" \
  --role="roles/secretmanager.secretAccessor"
```

> **Never grant `secretAccessor` at the project level.** Always bind per-secret.

### 3. Update Cloud Build configs to inject the secret

Edit both `cloudbuild-stage.yaml` and `cloudbuild-prod.yaml`. Append to the `--set-secrets` flag:

```yaml
# Before
- '--set-secrets=EXISTING_VAR=existing-secret:latest'

# After
- '--set-secrets=EXISTING_VAR=existing-secret:latest,NEW_ENV_VAR=SECRET_NAME:latest'
```

Format: `ENV_VAR_NAME=secret-name:latest`

### 4. Update the env-example template

Add the new variable to `.env.example` so future devs know it exists.

### 5. Deploy

- **Stage:** push branch, comment `/gcbrun` on PR, approve build
- **Prod:** merge to `main` (auto-deploys via trigger)

### 6. Verify

```bash
# Check the secret is accessible
gcloud secrets versions access latest --secret=SECRET_NAME --project=PROJECT > /dev/null && echo "OK"

# Check Cloud Run revision has the secret
gcloud run services describe ${STAGE_SERVICE} --region=${REGION} --project=${STAGE_PROJECT} \
  --format="yaml(spec.template.spec.containers[0].env)"
```

---

## Updating an Existing Secret Value

```bash
# Add a new version (old versions are preserved)
printf '%s' "new-value" | gcloud secrets versions add SECRET_NAME --data-file=- --project=PROJECT

# Force Cloud Run to pick up the new version (redeploy with no-op change)
gcloud run services update ${STAGE_SERVICE} --region=${REGION} --project=${STAGE_PROJECT} \
  --update-env-vars="SECRETS_REFRESHED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

No Cloud Build YAML changes needed -- `latest` always resolves to the newest version.

---

## Adding a Plain Environment Variable (non-secret)

Edit the cloudbuild YAML. Append to `--set-env-vars`:

```yaml
- '--set-env-vars=EXISTING_VAR=value,MY_NEW_VAR=some-value'
```

Push as a PR -- the value is reviewed in git like any other code change.

---

## Current Inventory

### Secrets (Secret Manager)

${SECRETS_TABLE}

### Plain Env Vars (cloudbuild YAML)

${ENV_VARS_TABLE}

---

## Security Rules

- **Never** store secrets in env vars, images, or git
- **Never** grant `secretAccessor` at project level -- always per-secret
- **Never** echo secret values in scripts or logs
- **Never** share secrets via Slack channels, email, or unencrypted channels
- OAuth credentials **should differ** between stage and prod
- `session-secret` should be auto-generated (not copied from `.env`)
