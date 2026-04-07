# Environment Configuration

## Overview

All environment-specific values are defined in `.gcp-setup.yml`. This file is the single source of truth for project configuration.

### Schema Reference

```yaml
projects:
  stage:
    id: "<stage-project-id>"
    service_name: "<stage-service>"
    build_config: "<path-to-stage-cloudbuild.yaml>"
  prod:
    id: "<prod-project-id>"
    service_name: "<prod-service>"
    build_config: "<path-to-prod-cloudbuild.yaml>"
region: "<gcp-region>"
artifact_registry:
  repo_name: "<repo-name>"
sa_prefix:
  runtime: "<runtime-sa-name>"
  cloudbuild: "<cloudbuild-sa-name>"
```

### Version Control

| File | Commit? | Why |
|------|---------|-----|
| `.gcp-setup.yml` | **Yes** | Infrastructure metadata only — project IDs, SA prefixes, secret names, feature flags. No secret values. |
| `.env`, `.env.*` | **Never** | Contain actual secret values (OAuth credentials, session keys). Must be in `.gitignore`. |
| `.env.example` / `env-example` | **Yes** | Template with empty/placeholder values. Safe to commit. |

The gcp-setup skill automatically adds `.env` and `.env.*` to `.gitignore` during config generation.

### Derived Values

| Property | Formula |
|----------|---------|
| Runtime SA | `<sa_prefix.runtime>@<project-id>.iam.gserviceaccount.com` |
| Cloud Build SA | `<sa_prefix.cloudbuild>@<project-id>.iam.gserviceaccount.com` |
| AR Image | `<region>-docker.pkg.dev/<project-id>/<repo_name>/<image>:<tag>` |
| Stage trigger | `deploy-<stage.service_name>` |
| Prod trigger | `deploy-<prod.service_name>` |

## Cloud Run URLs

URLs are deterministic: `https://<service>-<project-number>.<region>.run.app`

```bash
# Compute deterministic URLs from config
CONFIG=".gcp-setup.yml"
STAGE=$(yq -r '.projects.stage.id' "$CONFIG")
PROD=$(yq -r '.projects.prod.id' "$CONFIG")
STAGE_SVC=$(yq -r '.projects.stage.service_name' "$CONFIG")
PROD_SVC=$(yq -r '.projects.prod.service_name' "$CONFIG")
REGION=$(yq -r '.region' "$CONFIG")

STAGE_NUM=$(gcloud projects describe "$STAGE" --format="value(projectNumber)")
PROD_NUM=$(gcloud projects describe "$PROD" --format="value(projectNumber)")
echo "Stage: https://${STAGE_SVC}-${STAGE_NUM}.${REGION}.run.app"
echo "Prod:  https://${PROD_SVC}-${PROD_NUM}.${REGION}.run.app"
```

> **Warning:** `gcloud run services describe ... --format='value(status.url)'` returns a **legacy hash-based URL** (`*-uc.a.run.app`), NOT the deterministic URL. Both URLs route to the same service, but OAuth clients should be configured with the deterministic format. Always compute URLs with the formula above for OAuth-related work.

## Multi-App Shared Projects

Multiple apps can share the same GCP projects (e.g., a team owns `internal-tools-stage` and `internal-tools-prod` and deploys several unrelated apps into them). Each app lives in its own repo with its own `.gcp-setup.yml`, pointing to the same project IDs.

### What's Shared vs Per-App

| Resource | Scope | Collision risk |
|----------|-------|----------------|
| GCP project | Shared | N/A |
| APIs enabled | Shared | None (idempotent) |
| Artifact Registry repo | Shared | None (idempotent, images tagged per-app) |
| KMS keyring + key | Shared | None (idempotent) |
| Firestore database | Shared | None (one DB per project, collections namespaced by app) |
| GitHub connection | Shared | None (connection is reusable, repos linked additively) |
| Service accounts | **Per-app** | `sa_prefix` MUST be unique per app |
| IAM bindings | **Per-app** | Scoped to per-app SAs |
| Secrets | **Per-app** | Secret `name` MUST be unique per app |
| Cloud Build triggers | **Per-app** | Named `deploy-<service_name>`, unique by default |
| Cloud Run service | **Per-app** | `service_name` MUST be unique per app |
| OAuth client | Shared (recommended) | Add each app's callback URL to redirect URIs |

### Naming Conventions

To avoid collisions, each app MUST use unique values for:

- `sa_prefix.runtime` and `sa_prefix.cloudbuild` -- e.g., `dashboard-rt` / `dashboard-cb`
- `projects.stage.service_name` and `projects.prod.service_name` -- e.g., `dashboard-stage` / `dashboard`
- Secret names -- prefix with app name, e.g., `dashboard-session-secret` instead of `session-secret`

### Example: Two Apps in the Same GCP Projects

**App 1: Dashboard** (repo: `dashboard/`)

```yaml
# dashboard/.gcp-setup.yml
projects:
  stage:
    id: "internal-tools-stage"
    service_name: "dashboard-stage"
  prod:
    id: "internal-tools-prod"
    service_name: "dashboard"
sa_prefix:
  runtime: "dashboard-rt"
  cloudbuild: "dashboard-cb"
secrets:
  - name: dashboard-session-secret
    env_var: SESSION_SECRET
    auto_generate: true
    generator: "openssl rand -hex 32"
```

**App 2: API Gateway** (repo: `api-gateway/`)

```yaml
# api-gateway/.gcp-setup.yml
projects:
  stage:
    id: "internal-tools-stage"
    service_name: "api-gw-stage"
  prod:
    id: "internal-tools-prod"
    service_name: "api-gw"
sa_prefix:
  runtime: "apigw-rt"
  cloudbuild: "apigw-cb"
secrets:
  - name: apigw-session-secret
    env_var: SESSION_SECRET
    auto_generate: true
    generator: "openssl rand -hex 32"
```

Both apps share the same Artifact Registry repo, KMS keyring, and GitHub connection. Each gets independent Cloud Run services, service accounts, secrets, and triggers.

### Provisioning Order

When setting up the first app in a shared project, run all phases normally. For subsequent apps:

1. **Phase 1 (preflight):** Runs normally
2. **Phase 2 (provision):** Shared resources print `=exists` and skip creation. Per-app resources are created fresh.
3. **Phase 3 (secrets):** Creates app-specific secrets only
4. **Phase 4 (OAuth):** Add the new app's callback URL to the existing OAuth client's redirect URIs (see `cookbook/oauth-setup.md`)
5. **Phase 5 (verify):** Validates the new app's resources independently

## Secrets

Secrets are defined in the `secrets` section of `.gcp-setup.yml`:

```yaml
secrets:
  - name: oauth-client-id
    env_var: GOOGLE_CLIENT_ID
    source: "GCP OAuth 2.0 Client ID"
  - name: oauth-client-secret
    env_var: GOOGLE_CLIENT_SECRET
    source: "GCP OAuth 2.0 Client Secret"
  - name: session-secret
    env_var: SESSION_SECRET
    auto_generate: true
    generator: "openssl rand -hex 32"
```

**Each environment has its own set of secrets.** OAuth credentials MUST differ per environment.

## CI/CD Flow

```
PR opened -> Stage trigger -> Manual approval -> Build -> Deploy to stage service
PR merged -> Prod trigger -> Manual approval -> Build -> Deploy to prod service
```

## Image Tags

- Cloud Build: `$COMMIT_SHA` (git commit hash)
- Local deploy: `local-<short-sha>` (avoids collision)
