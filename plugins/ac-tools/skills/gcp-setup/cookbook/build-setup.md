# Build Setup Guide

How to configure the three files that turn your code into a running Cloud Run service.

## What Are These Files?

| File | What it does | Analogy |
|------|-------------|---------|
| `Dockerfile` | Packages your app into a container image | A recipe that describes how to assemble the dish |
| `.dockerignore` | Lists files to exclude from the container | Ingredients you leave out of the recipe |
| `cloudbuild-*.yaml` | Tells Cloud Build how to build, push, and deploy | Kitchen instructions: cook the recipe, plate it, serve it |

**How they connect:**
```
Your code + Dockerfile  -->  Container image  -->  Artifact Registry  -->  Cloud Run
                                      ^                                       ^
                              cloudbuild.yaml orchestrates the whole pipeline
```

## Dockerfile

### What it does

A Dockerfile is a text file with instructions to package your app. Each line creates a "layer" in the image. The gcp-setup skill generates a **multi-stage** Dockerfile — two stages:

1. **Builder stage:** Installs dependencies and compiles your code
2. **Production stage:** Copies only what's needed to run (no dev tools, no source maps)

This keeps the final image small and secure.

### Security requirements

| Requirement | Why | How |
|------------|-----|-----|
| Non-root user | Limits damage if the container is compromised | `USER appuser` in Dockerfile |
| PORT 8080 | Cloud Run injects `PORT=8080` and expects your app to listen there | `ENV PORT=8080` + app listens on `process.env.PORT` |
| No secrets in image | Secrets in image layers are readable by anyone with image access | Use `.dockerignore` + Cloud Run `--set-secrets` |

### Per-runtime templates

The skill auto-detects your runtime and generates the appropriate Dockerfile:

**Node.js** (`assets/dockerfile-node.template`):
- Uses `node:22-alpine` (small, secure)
- `npm ci --ignore-scripts` (reproducible, no post-install scripts)
- Adjust `CMD` to match your entry point (`server.js`, `dist/index.js`, `npm start`)

**Python** (`assets/dockerfile-python.template`):
- Uses `python:3.12-slim`
- Installs deps into a virtual environment (copied to production stage)
- Adjust `CMD` to match your framework (`uvicorn`, `gunicorn`, etc.)

**Go** (`assets/dockerfile-go.template`):
- Builds a static binary with `CGO_ENABLED=0`
- Production stage uses `distroless` (no shell, no package manager)
- Smallest and most secure option

### Customization

**Changing the base image version:**
```dockerfile
# Pin to a specific version for reproducibility
FROM node:22.12-alpine AS builder
```

**Adding build arguments:**
```dockerfile
ARG NODE_ENV=production
ENV NODE_ENV=$NODE_ENV
```

**Custom entry point:**
Change the `CMD` line to match your app:
```dockerfile
# TypeScript compiled to dist/
CMD ["node", "dist/index.js"]

# Next.js
CMD ["npm", "start"]
```

## .dockerignore

### What it does

Lists files and directories that Docker should NOT copy into the container image. This is critical for security — without it, your `.env` files (containing secrets) would be baked into the image.

### What's excluded and why

| Pattern | Why excluded |
|---------|-------------|
| `.env`, `.env.*` | Secret values — NEVER include in images |
| `.git` | Repository history, not needed at runtime |
| `node_modules` | Reinstalled during build for correct platform |
| `__pycache__`, `*.pyc` | Python bytecode, rebuilt at runtime |
| `.venv`, `vendor` | Local dependency caches |
| `tests`, `spec`, `coverage` | Test files, not needed in production |
| `cloudbuild*.yaml` | Build config, not needed at runtime |
| `.gcp-setup.yml` | Infrastructure config, not needed at runtime |

### Adding app-specific exclusions

Append to `.dockerignore`:
```
# Large data files
data/
*.csv

# Local development
docker-compose.yml
.env.local
```

## CloudBuild YAML

### What it does

`cloudbuild-stage.yaml` and `cloudbuild-prod.yaml` tell Google Cloud Build how to:
1. **Build** a Docker image from your code
2. **Push** the image to Artifact Registry
3. **Deploy** the image to Cloud Run

### How to read the template

The template at `assets/cloudbuild-template.yaml` has three steps:

**Step 1: Build Docker image**
```yaml
- name: 'gcr.io/cloud-builders/docker'
  args: ['build', '-t', '<registry>/<image>:$COMMIT_SHA', '.']
```
Runs `docker build` using your Dockerfile. Tags the image with the git commit hash for traceability.

**Step 2: Push to Artifact Registry**
```yaml
- name: 'gcr.io/cloud-builders/docker'
  args: ['push', '<registry>/<image>:$COMMIT_SHA']
```
Uploads the built image to your private Artifact Registry repo.

**Step 3: Deploy to Cloud Run**
```yaml
- name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
  entrypoint: gcloud
  args: ['run', 'deploy', '<service>', '--image=...', '--set-secrets=...']
```
Deploys the image to Cloud Run with secrets injected from Secret Manager.

### Token reference

These `__TOKEN__` placeholders in the template are replaced with values from `.gcp-setup.yml`. The `__TOKEN__` syntax avoids conflicts with Cloud Build's native `$VARIABLE` substitutions.

| Token | Config path | Example |
|-------|------------|---------|
| `__PROJECT_ID__` | `projects.<env>.id` | `internal-tools-stage` |
| `__SERVICE_NAME__` | `projects.<env>.service_name` | `dashboard-stage` |
| `__REGION__` | `region` | `us-central1` |
| `__REPO_NAME__` | `artifact_registry.repo_name` | `docker-images` |
| `__IMAGE_NAME__` | `projects.<env>.service_name` | `dashboard-stage` |
| `__MAX_INSTANCES__` | `app.max_instances_stage` / `app.max_instances_prod` | `5` / `100` |
| `__RUNTIME_SA__` | `<sa_prefix.runtime>@<project>.iam` | `<sa-prefix>@<project-id>.iam...` |
| `__SECRETS_MAPPING__` | Generated from `secrets[]` | `SESSION_SECRET=dashboard-session-secret:latest` |
| `__APP_DIR__` | `app.dockerfile_path` directory | `.` |

### Stage vs prod differences

| Setting | Stage | Prod |
|---------|-------|------|
| `__MAX_INSTANCES__` | `5` (low cost) | `100` (handle traffic) |
| `__PROJECT_ID__` | Stage project | Prod project |
| `__SERVICE_NAME__` | `*-stage` suffix | Base name |
| `__RUNTIME_SA__` | Stage project SA | Prod project SA |

### Secrets mapping

The `--set-secrets` flag maps Secret Manager secrets to environment variables at deploy time. The mapping is generated from the `secrets` section of `.gcp-setup.yml`:

```yaml
# Config:
secrets:
  - name: dashboard-session-secret
    env_var: SESSION_SECRET

# Generates:
--set-secrets=SESSION_SECRET=dashboard-session-secret:latest
```

Multiple secrets are comma-separated:
```
--set-secrets=SESSION_SECRET=dashboard-session-secret:latest,GOOGLE_CLIENT_ID=oauth-client-id:latest
```

### Environment variables (non-secrets)

The `--set-env-vars` flag sets plain (non-secret) environment variables. Use this for configuration values that are NOT sensitive:

```yaml
--set-env-vars=AUTH_URL=https://<cloud-run-url>,AUTH_TRUST_HOST=true,ALLOWED_DOMAIN=example.com
```

| Flag | Use for | Example |
|------|---------|---------|
| `--set-secrets` | Secret values from Secret Manager | OAuth credentials, session keys |
| `--set-env-vars` | Non-secret configuration | `AUTH_URL`, `AUTH_TRUST_HOST`, `ALLOWED_DOMAIN` |

Never put secret values in `--set-env-vars` — they would be visible in Cloud Run revision metadata.

## Troubleshooting

### Build fails: Dockerfile not found
```
ERROR: could not find Dockerfile
```
Check that `app.dockerfile_path` in `.gcp-setup.yml` points to the correct location, and that the `dir` field in `cloudbuild-*.yaml` matches.

### Build succeeds but container won't start
```
Container failed to start and listen on the port defined by the PORT environment variable.
```
Your app must listen on `process.env.PORT` (or equivalent). Cloud Run injects `PORT=8080`.

### Image is too large
Multi-stage builds should keep images small. If your image exceeds 500MB:
- Check that `.dockerignore` excludes `node_modules`, test files, docs
- Verify the production stage doesn't copy unnecessary files from builder
- Use `alpine` or `slim` base images

### Secrets not available at runtime
Secrets are injected via `--set-secrets` at deploy time, NOT during build. If your app needs secrets during build (e.g., private npm registry), use Cloud Build `secretEnv` instead.
