# ${PROJECT_NAME}

${PROJECT_DESCRIPTION}

## Environments

| Environment | URL | GCP Project |
|-------------|-----|-------------|
| **Production** | ${PROD_URL} | `${PROD_PROJECT}` |
| **Staging** | ${STAGE_URL} | `${STAGE_PROJECT}` |

## Local Development

```bash
cp .env.example .env.local
# Fill in values (see docs/managing-secrets-and-envs.md)
npm install
npm run dev
```

Open http://localhost:${PORT}

## Deploy

### Staging

Staging deploys are triggered via PR comments and require manual approval.

| Resource | Link |
|----------|------|
| Stage app | ${STAGE_URL} |
| Cloud Build console | ${CB_CONSOLE_STAGE} |

1. **Trigger the build** -- comment `/gcbrun` on the PR
2. **Approve the build** -- open the Cloud Build console, find the pending build, click **Approve**
3. **Wait** -- build takes ~4 min; check the PR Checks tab
4. **Verify** -- open the stage URL and confirm the app loads
5. **Health check**:
   ```bash
   curl ${STAGE_URL}${HEALTH_ENDPOINT}
   # Expected: ${HEALTH_RESPONSE}
   ```

> Repeat steps 1-2 after each push to the PR.

### Production

Production deploys on push to `main` and requires manual approval.

| Resource | Link |
|----------|------|
| Prod app | ${PROD_URL} |
| Cloud Build console | ${CB_CONSOLE_PROD} |

## Docs

- [Managing Secrets & Environment Variables](docs/managing-secrets-and-envs.md) -- how to add, update, or rotate secrets and env vars, and local dev onboarding
