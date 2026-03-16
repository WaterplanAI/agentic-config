# Troubleshooting

## Connection Creation

### Cloud Build P4SA permission error
```
Permission error: Cloud Build P4SA needs secretmanager.secrets.create + secretmanager.secrets.setIamPolicy to store the GitHub token
```
**Cause:** The Cloud Build per-project service agent (P4SA) lacks `roles/secretmanager.admin`. It needs this temporarily to create secrets and set IAM policies when storing the GitHub OAuth token during 2nd-gen connection creation.

**Fix:** Re-run provisioning with `--cmek-only` to grant a 20-minute auto-expiring `secretmanager.admin` binding, then create the connection within that window.
```bash
bash tools/provision.sh --config .gcp-setup.yml --cmek-only --env all
```

## Build Failures

### Dockerfile not found
```
ERROR: could not find Dockerfile
```
**Fix:** Verify `dir` field in cloudbuild YAML points to the directory containing the Dockerfile. Check `app.dockerfile_path` in `.gcp-setup.yml`.

## Container Startup

### Container fails to start (PORT)
```
Container failed to start. Failed to start and then listen on the port defined by the PORT environment variable.
```
**Fix:** Ensure `ENV PORT=8080` in Dockerfile and the application listens on `process.env.PORT || 8080` (or equivalent for your runtime).

### Container starts but crashes
**Fix:** Check Cloud Run logs:
```bash
SERVICE=$(yq -r '.projects.stage.service_name' .gcp-setup.yml)
REGION=$(yq -r '.region' .gcp-setup.yml)
PROJECT=$(yq -r '.projects.stage.id' .gcp-setup.yml)
gcloud run services logs read "$SERVICE" --region="$REGION" --project="$PROJECT" --limit=50
```

## Authentication

### 403 Forbidden (Cloud Run level)
User sees 403 before reaching the app at all.

**Cause:** Missing `allUsers` invoker binding. Cloud Build SA needs `roles/run.admin` (not `roles/run.developer`) to set `--allow-unauthenticated`.

**Fix:**
```bash
PROJECT=$(yq -r '.projects.stage.id' .gcp-setup.yml)
SERVICE=$(yq -r '.projects.stage.service_name' .gcp-setup.yml)
REGION=$(yq -r '.region' .gcp-setup.yml)
CB_SA_PREFIX=$(yq -r '.sa_prefix.cloudbuild' .gcp-setup.yml)

# Check CB SA role
gcloud projects get-iam-policy "$PROJECT" --format=json | grep -A5 "run.admin"

# Manually add invoker binding:
gcloud run services add-iam-policy-binding "$SERVICE" \
  --member="allUsers" \
  --role="roles/run.invoker" \
  --region="$REGION" --project="$PROJECT"
```

### 403 at /auth/denied (app level)
User authenticates with Google but gets denied by the app.

**Cause:** User's Google account does not match the configured domain restriction.

**Fix:** This is working as intended. Only accounts matching the configured domain are allowed.

### redirect_uri_mismatch
```
Error 400: redirect_uri_mismatch
```
**Cause:** The OAuth callback URL in the request doesn't match what's registered in GCP Console.

**Fix:**
1. Get the **deterministic** Cloud Run URL (not `status.url`, which returns the legacy hash-based URL):
   ```bash
   PROJECT=$(yq -r '.projects.stage.id' .gcp-setup.yml)
   SERVICE=$(yq -r '.projects.stage.service_name' .gcp-setup.yml)
   REGION=$(yq -r '.region' .gcp-setup.yml)
   CALLBACK=$(yq -r '.oauth.callback_path' .gcp-setup.yml)
   PROJECT_NUM=$(gcloud projects describe "$PROJECT" --format="value(projectNumber)")
   echo "https://${SERVICE}-${PROJECT_NUM}.${REGION}.run.app"
   ```
   > **Warning:** `status.url` returns a legacy hash-based URL (`*-uc.a.run.app`) that does NOT match the deterministic URL registered in OAuth. Always use the deterministic format for OAuth configuration.
2. Register `<deterministic-url><callback_path>` as authorized redirect URI in GCP Console > Google Auth Platform > Clients
3. Also add the base deterministic URL to authorized JavaScript origins

## Secrets

### Secret has no versions
```
ERROR: NOT_FOUND: Secret version not found
```
**Fix:** Populate the secret:
```bash
printf '%s' '<value>' | gcloud secrets versions add <SECRET> --data-file=- --project=<PROJECT>
```

### Secrets updated but not picked up
**Cause:** Cloud Run caches secret values per revision.

**Fix:** Force a new revision:
```bash
SERVICE=$(yq -r '.projects.stage.service_name' .gcp-setup.yml)
REGION=$(yq -r '.region' .gcp-setup.yml)
PROJECT=$(yq -r '.projects.stage.id' .gcp-setup.yml)
gcloud run services update "$SERVICE" --region="$REGION" --project="$PROJECT" \
  --update-env-vars="SECRETS_REFRESHED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)" --quiet
```

## Multi-App Shared Projects

### Service account already exists (409)
```
ERROR: Resource already exists
```
**Cause:** Another app in the same GCP project uses the same `sa_prefix`.

**Fix:** Each app MUST use a unique `sa_prefix`. Update `.gcp-setup.yml`:
```yaml
sa_prefix:
  runtime: "myapp-rt"       # unique per app
  cloudbuild: "myapp-cb"    # unique per app
```

### Secret name collision
Running `secrets.sh --action create` reports `=exists` for secrets you did not expect.

**Cause:** Another app in the same GCP project uses the same secret name (e.g., `session-secret`).

**Fix:** Prefix secret names with the app name:
```yaml
secrets:
  - name: myapp-session-secret    # not just "session-secret"
    env_var: SESSION_SECRET
```

### OAuth redirect_uri_mismatch with multiple apps
```
Error 400: redirect_uri_mismatch
```
**Cause:** The new app's callback URL is not registered in the shared OAuth client.

**Fix:** In GCP Console > Google Auth Platform > Clients, edit the OAuth client and add:
- Authorized JavaScript origin: `https://<new-service>-<project-num>.<region>.run.app`
- Authorized redirect URI: `https://<new-service>-<project-num>.<region>.run.app<callback_path>`

See `cookbook/oauth-setup.md` "Multi-App: Shared OAuth Client" for details.

### Trigger name collision
Trigger names follow the pattern `deploy-<service_name>`. As long as each app has a unique `service_name`, triggers will not collide. If you see:
```
ERROR: Failed to create stage trigger
```
Verify that `projects.stage.service_name` is unique across all apps in the same GCP project.

## Health Check

### Health check returns non-200
```bash
HEALTH_ENDPOINT=$(yq -r '.health_endpoint' .gcp-setup.yml)
curl -v "https://<URL>${HEALTH_ENDPOINT}"
```
Expected response should match `health_response` from config (e.g., `"status":"healthy"` with HTTP 200).

If it returns 302 (redirect to auth), the health endpoint is behind auth middleware. Ensure the health endpoint route is mounted BEFORE auth middleware in your application.
