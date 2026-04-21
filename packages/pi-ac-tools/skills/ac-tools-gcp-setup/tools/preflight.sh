#!/usr/bin/env bash
# preflight.sh — Validate prerequisites for GCP setup
# Usage: bash preflight.sh --config .gcp-setup.yml [--stage-project <id> --prod-project <id>]
# Output: KEY=VALUE pairs + PREFLIGHT=PASS|FAIL
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

# Parse --config first, then fall back to explicit flags
parse_config_flag "$@"

# --- Override defaults from flags (backwards compat) ---
STAGE_PROJECT=""
PROD_PROJECT=""
REGION=""
REPO_NAME=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)        shift 2 ;;  # already parsed
    --stage-project) STAGE_PROJECT="${2:?value required}"; shift 2 ;;
    --prod-project)  PROD_PROJECT="${2:?value required}"; shift 2 ;;
    --region)        REGION="${2:?value required}"; shift 2 ;;
    --repo-name)     REPO_NAME="${2:?value required}"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# Load from config if available, allow flag overrides
if [[ -f "${CONFIG_FILE:-.gcp-setup.yml}" ]]; then
  require_config
  [[ -z "$STAGE_PROJECT" ]] && STAGE_PROJECT=$(get_project_id "stage")
  [[ -z "$PROD_PROJECT" ]] && PROD_PROJECT=$(get_project_id "prod")
  [[ -z "$REGION" ]] && REGION=$(read_config '.region')
  [[ -z "$REPO_NAME" ]] && REPO_NAME=$(read_config '.artifact_registry.repo_name')
fi

REGION="${REGION:-us-central1}"

if [[ -z "$STAGE_PROJECT" || -z "$PROD_PROJECT" ]]; then
  echo "ERROR: Stage and prod project IDs required (via --config or --stage-project/--prod-project)" >&2
  exit 1
fi

FAIL=0

# --- Check gcloud ---
if command -v gcloud &>/dev/null; then
  echo "GCLOUD_INSTALLED=true"
  ACCOUNT=$(gcloud auth list --filter="status:ACTIVE" --format="value(account)" 2>/dev/null | head -1)
  if [[ -n "$ACCOUNT" ]]; then
    echo "GCLOUD_AUTHENTICATED=true"
    echo "GCLOUD_ACCOUNT=$ACCOUNT"
    # Domain check (only if oauth.domain_restriction is configured)
    DOMAIN_RESTRICTION=""
    if [[ -f "${CONFIG_FILE:-.gcp-setup.yml}" ]]; then
      DOMAIN_RESTRICTION=$(read_config '.oauth.domain_restriction // empty' 2>/dev/null || true)
    fi
    if [[ -n "$DOMAIN_RESTRICTION" && "$DOMAIN_RESTRICTION" != "null" ]]; then
      if [[ "$ACCOUNT" == *"@${DOMAIN_RESTRICTION}" ]]; then
        echo "GCLOUD_DOMAIN=true"
      else
        echo "GCLOUD_DOMAIN=false"
        echo "WARNING: Active account ($ACCOUNT) is not @${DOMAIN_RESTRICTION}" >&2
      fi
    fi
  else
    echo "GCLOUD_AUTHENTICATED=false"
    echo "ERROR: No active gcloud account. Run: gcloud auth login" >&2
    FAIL=1
  fi
else
  echo "GCLOUD_INSTALLED=false"
  echo "ERROR: gcloud not found. Install: https://cloud.google.com/sdk/docs/install" >&2
  FAIL=1
fi

# --- Check project access ---
for PROJECT_VAR in STAGE_PROJECT PROD_PROJECT; do
  PROJECT="${!PROJECT_VAR}"
  if gcloud projects describe "$PROJECT" &>/dev/null; then
    echo "${PROJECT_VAR}_OK=true"
  else
    echo "${PROJECT_VAR}_OK=false"
    echo "ERROR: Cannot access project $PROJECT" >&2
    FAIL=1
  fi
done

# --- Check yq (required for config parsing) ---
if command -v yq &>/dev/null; then
  echo "YQ_OK=true"
else
  echo "YQ_OK=false"
  echo "ERROR: yq not found. Required for config parsing. Install: brew install yq" >&2
  FAIL=1
fi

# --- Check docker (optional) ---
if command -v docker &>/dev/null; then
  echo "DOCKER_OK=true"
else
  echo "DOCKER_OK=false"
  echo "WARNING: Docker not found. Only needed for local builds. Install: brew install --cask docker" >&2
fi

# --- Check gh CLI (optional) ---
if command -v gh &>/dev/null; then
  echo "GH_OK=true"
else
  echo "GH_OK=false"
  echo "WARNING: GitHub CLI not found. Only needed for PR operations. Install: brew install gh" >&2
fi

# --- Summary ---
echo "REGION=$REGION"
echo "REPO_NAME=$REPO_NAME"
if [[ $FAIL -eq 0 ]]; then
  echo "PREFLIGHT=PASS"
  exit 0
else
  echo "PREFLIGHT=FAIL"
  exit 1
fi
