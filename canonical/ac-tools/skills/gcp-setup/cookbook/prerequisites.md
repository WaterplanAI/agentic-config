# Prerequisites

## Required Tools

| Tool | Required | Install | Purpose |
|------|----------|---------|---------|
| `gcloud` | Yes | [Install Guide](https://cloud.google.com/sdk/docs/install) | GCP CLI for all infrastructure operations |
| `yq` | Yes | `brew install yq` | YAML config file parsing |
| `python3` | Yes | `brew install python3` | IAM policy inspection during verification |
| `docker` | No | `brew install --cask docker` | Local builds only (remote builds use Cloud Build) |
| `gh` | No | `brew install gh` | GitHub PR operations |

## GCP Access

- **Account:** Must have appropriate access to the target GCP projects
- **Permissions:** `Owner` or equivalent on both stage and prod GCP projects
- **Authenticate:** `gcloud auth login`
- **Domain restriction:** If `oauth.domain_restriction` is configured in `.gcp-setup.yml`, the active gcloud account should match that domain

## GitHub Access

- **Org:** As configured in `.gcp-setup.yml` (`github.repo_slug`)
- **Permissions:** Admin access (needed for Cloud Build GitHub App connection)

## Project Config

A `.gcp-setup.yml` file must exist in the project root. The gcp-setup skill generates this interactively on first run. See `assets/gcp-setup-example.yml` for the full schema.

## Verify Setup

```bash
# Check gcloud
gcloud auth list --filter="status:ACTIVE" --format="value(account)"

# Check project access (read IDs from .gcp-setup.yml)
STAGE=$(yq -r '.projects.stage.id' .gcp-setup.yml)
PROD=$(yq -r '.projects.prod.id' .gcp-setup.yml)
gcloud projects describe "$STAGE" --format="value(projectId)"
gcloud projects describe "$PROD" --format="value(projectId)"

# Check yq
yq --version

# Check docker (optional)
docker --version
```
