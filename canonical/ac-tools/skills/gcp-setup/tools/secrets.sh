#!/usr/bin/env bash
# secrets.sh — Secret Manager operations (create, populate, verify, rotate)
# Usage: bash secrets.sh --config .gcp-setup.yml --action <create|populate|verify|rotate> --env <stage|prod|all> [options]
# Output: KEY=VALUE pairs + SECRETS=PASS|FAIL
# SECURITY: NEVER writes secrets to files. NEVER echoes secret values.
# WARNING: This file must be executed (bash secrets.sh), NEVER sourced.
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  echo "ERROR: secrets.sh must not be sourced — run it with: bash secrets.sh ..." >&2
  return 1 2>/dev/null || exit 1
fi
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

# Parse --config first
parse_config_flag "$@"
require_config

# Load secret manifest from config
load_secrets_manifest

# --- Read from config ---
REGION=$(read_config '.region')

# --- Defaults ---
ACTION=""
TARGET_ENV="all"
ENV_FILE=""

# --- Parse remaining flags ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)   shift 2 ;;  # already parsed
    --action)   ACTION="${2:?--action requires a value}"; shift 2 ;;
    --env)      TARGET_ENV="${2:?--env requires a value}"; shift 2 ;;
    --env-file) ENV_FILE="${2:?value required}"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$ACTION" ]]; then
  echo "ERROR: --action is required" >&2
  echo "Usage: $0 --config .gcp-setup.yml --action <create|populate|verify|rotate> --env <stage|prod|all>" >&2
  exit 1
fi

STAGE_PROJECT=$(get_project_id "stage")
PROD_PROJECT=$(get_project_id "prod")

# Guard: stage and prod must be different projects (environment inference depends on it)
if [[ "$STAGE_PROJECT" == "$PROD_PROJECT" ]]; then
  echo "ERROR: projects.stage.id and projects.prod.id must be different (both are '$STAGE_PROJECT')" >&2
  exit 1
fi

# --- Build project list ---
case "$TARGET_ENV" in
  stage) PROJECTS=("$STAGE_PROJECT") ;;
  prod)  PROJECTS=("$PROD_PROJECT") ;;
  all)   PROJECTS=("$STAGE_PROJECT" "$PROD_PROJECT") ;;
  *) echo "ERROR: Invalid --env: $TARGET_ENV" >&2; exit 1 ;;
esac

FAIL=0

# --- ACTION: create ---
if [[ "$ACTION" == "create" ]]; then
  for PROJECT in "${PROJECTS[@]}"; do
    echo "Creating secrets in $PROJECT..."
    RUNTIME_SA=$(compute_sa_email "runtime" "$PROJECT")
    for SECRET in "${SECRETS[@]}"; do
      if gcloud secrets describe "$SECRET" --project="$PROJECT" &>/dev/null; then
        echo "SECRET_${SECRET//-/_}_${PROJECT}=exists"
      elif gcloud secrets create "$SECRET" --project="$PROJECT" 2>/dev/null; then
        echo "SECRET_${SECRET//-/_}_${PROJECT}=created"
      else
        echo "ERROR: Failed to create secret $SECRET in $PROJECT" >&2
        echo "SECRET_${SECRET//-/_}_${PROJECT}=FAIL"
        FAIL=1
      fi
      # Per-secret IAM binding — skip if already bound
      existing_policy=$(gcloud secrets get-iam-policy "$SECRET" --project="$PROJECT" --format=json 2>/dev/null || echo "{}")
      if ! echo "$existing_policy" | grep -q "$RUNTIME_SA"; then
        if ! gcloud secrets add-iam-policy-binding "$SECRET" \
          --project="$PROJECT" \
          --member="serviceAccount:$RUNTIME_SA" \
          --role="roles/secretmanager.secretAccessor" --quiet 2>/dev/null; then
          echo "WARNING: Failed to bind secretAccessor on $SECRET for $RUNTIME_SA" >&2
          FAIL=1
        fi
      fi
    done
  done
  if [[ $FAIL -eq 0 ]]; then
    echo "SECRETS=PASS"
    exit 0
  else
    echo "SECRETS=FAIL"
    exit 1
  fi
fi

# --- ACTION: verify ---
if [[ "$ACTION" == "verify" ]]; then
  for PROJECT in "${PROJECTS[@]}"; do
    echo "Verifying secrets in $PROJECT..."
    for SECRET in "${SECRETS[@]}"; do
      if gcloud secrets versions list "$SECRET" --project="$PROJECT" --limit=1 --format="value(name)" 2>/dev/null | grep -q .; then
        echo "SECRET_${SECRET//-/_}=verified"
      else
        echo "SECRET_${SECRET//-/_}=MISSING_VERSION"
        FAIL=1
      fi
    done
  done
  if [[ $FAIL -eq 0 ]]; then
    echo "SECRETS=PASS"
    exit 0
  else
    echo "SECRETS=FAIL"
    exit 1
  fi
fi

# --- ACTION: populate ---
if [[ "$ACTION" == "populate" ]]; then
  if [[ "${#PROJECTS[@]}" -gt 1 ]]; then
    echo "WARNING: Populating multiple projects with the same values." >&2
    echo "WARNING: OAuth credentials SHOULD differ per environment." >&2
    echo "WARNING: Consider: --env stage first, then --env prod --env-file /path/to/prod.env" >&2
  fi

  # Build reverse map: secret_name -> env_var (for env-file lookup)
  declare -A SECRET_TO_ENV=()
  SECRET_COUNT=$(read_config '.secrets | length')
  for ((i=0; i<SECRET_COUNT; i++)); do
    s_name=$(read_config ".secrets[$i].name")
    s_env=$(read_config ".secrets[$i].env_var")
    SECRET_TO_ENV["$s_name"]="$s_env"
  done

  # Build allowlist of expected env var names from SECRET_TO_ENV values
  declare -a ALLOWED_ENV_KEYS=()
  for _k in "${!SECRET_TO_ENV[@]}"; do
    ALLOWED_ENV_KEYS+=("${SECRET_TO_ENV[$_k]}")
  done

  # Associative array for parsed .env values (avoids dynamic variable naming)
  declare -A SECENV=()

  # Parse .env file if provided (STRICT parser — no source, no eval)
  if [[ -n "$ENV_FILE" ]]; then
    if [[ ! -f "$ENV_FILE" ]]; then
      echo "ERROR: .env file not found: $ENV_FILE" >&2
      exit 1
    fi
    # Parse .env as data (not shell) to prevent arbitrary code execution
    while IFS='=' read -r key value; do
      [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
      key="${key#"${key%%[![:space:]]*}"}"
      [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || { echo "ERROR: invalid key '$key' in $ENV_FILE" >&2; exit 1; }
      if [[ "$value" =~ ^\"(.*)\"$ ]] || [[ "$value" =~ ^\'(.*)\'$ ]]; then
        value="${BASH_REMATCH[1]}"
      fi
      # Trim leading/trailing whitespace from value
      value="${value#"${value%%[![:space:]]*}"}"
      value="${value%"${value##*[![:space:]]}"}"
      # Validate key is in the expected allowlist
      allowed=false
      for _allowed_key in "${ALLOWED_ENV_KEYS[@]}"; do
        if [[ "$key" == "$_allowed_key" ]]; then
          allowed=true
          break
        fi
      done
      if [[ "$allowed" != "true" ]]; then
        echo "WARNING: Ignoring unexpected key '$key' in $ENV_FILE" >&2
        continue
      fi
      SECENV["$key"]="$value"
    done < "$ENV_FILE"
  fi

  # Generate auto-generate secrets
  declare -A GENERATED=()
  for ((i=0; i<SECRET_COUNT; i++)); do
    auto=$(read_config ".secrets[$i].auto_generate")
    if [[ "$auto" == "true" ]]; then
      s_name=$(read_config ".secrets[$i].name")
      generator=$(read_config ".secrets[$i].generator")
      if [[ -n "$generator" && "$generator" != "null" ]]; then
        if [[ "$generator" =~ ^openssl\ rand\ -(hex|base64)\ ([0-9]+)$ ]]; then
          GENERATED["$s_name"]=$(openssl rand "-${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}")
          echo "Generated fresh $s_name (not using .env value)"
        else
          echo "ERROR: Untrusted generator for secret $s_name: $generator" >&2
          echo "ERROR: Only 'openssl rand -hex <N>' and 'openssl rand -base64 <N>' are allowed" >&2
          FAIL=1
        fi
      fi
    fi
  done

  OVERALL_FAIL=0
  for PROJECT in "${PROJECTS[@]}"; do
    echo "Populating secrets in $PROJECT..."
    FAIL=0

    for SECRET in "${SECRETS[@]}"; do
      # Use generated value if available, otherwise look up env var
      if [[ -n "${GENERATED[$SECRET]:-}" ]]; then
        printf '%s' "${GENERATED[$SECRET]}" | gcloud secrets versions add "$SECRET" --data-file=- --project="$PROJECT" || { FAIL=1; continue; }
      else
        ENV_VAR="${SECRET_TO_ENV[$SECRET]:-}"
        if [[ -z "$ENV_VAR" ]]; then
          echo "ERROR: No env_var mapping for secret $SECRET" >&2
          FAIL=1
          continue
        fi
        VALUE="${SECENV[$ENV_VAR]:-}"
        if [[ -z "$VALUE" ]]; then
          echo "ERROR: $ENV_VAR not set (needed for secret $SECRET)" >&2
          FAIL=1
          continue
        fi
        printf '%s' "$VALUE" | gcloud secrets versions add "$SECRET" --data-file=- --project="$PROJECT" || { FAIL=1; continue; }
      fi
    done

    if [[ $FAIL -eq 0 ]]; then
      echo "All ${#SECRETS[@]} secrets populated in $PROJECT"
    else
      echo "WARNING: Some secrets failed to populate in $PROJECT" >&2
      OVERALL_FAIL=1
    fi

    # Refresh Cloud Run revision to pick up new secrets
    if [[ "$PROJECT" == "$STAGE_PROJECT" ]]; then
      SERVICE=$(get_service_name "stage")
    else
      SERVICE=$(get_service_name "prod")
    fi

    echo "Refreshing Cloud Run service $SERVICE..."
    if gcloud run services describe "$SERVICE" --region="$REGION" --project="$PROJECT" &>/dev/null; then
      gcloud run services update "$SERVICE" --region="$REGION" --project="$PROJECT" \
        --update-env-vars="SECRETS_REFRESHED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)" --quiet
      echo "REVISION_REFRESH_${PROJECT}=done"
    else
      echo "REVISION_REFRESH_${PROJECT}=service_not_deployed"
    fi
  done

  if [[ $OVERALL_FAIL -eq 0 ]]; then
    echo "SECRETS=PASS"
    exit 0
  else
    echo "SECRETS=FAIL"
    exit 1
  fi
fi

# --- ACTION: rotate ---
if [[ "$ACTION" == "rotate" ]]; then
  echo "Rotate is equivalent to populate + revision refresh."
  echo "Run: $0 --config $CONFIG_FILE --action populate --env $TARGET_ENV --env-file <path>"
  exit 0
fi

echo "ERROR: Unknown action: $ACTION (expected: create, populate, verify, rotate)" >&2
exit 1
