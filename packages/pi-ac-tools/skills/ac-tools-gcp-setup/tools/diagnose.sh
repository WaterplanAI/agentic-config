#!/usr/bin/env bash
# diagnose.sh — Post-deploy troubleshooting and health checks
# Usage: bash diagnose.sh --config .gcp-setup.yml --env <stage|prod|all>
# Output: KEY=VALUE pairs + DIAGNOSE=PASS|FAIL
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

parse_config_flag "$@"
require_config

# Read from config
REGION=$(read_config '.region')
HEALTH_ENDPOINT=$(read_config '.health_endpoint')
HEALTH_RESPONSE=$(read_config '.health_response')
OAUTH_MODE=$(read_config '.oauth.mode // "standalone"')

# --- Defaults ---
TARGET_ENV="all"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) shift 2 ;;
    --env)    TARGET_ENV="${2:?value required}"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

STAGE_PROJECT=$(get_project_id "stage")
PROD_PROJECT=$(get_project_id "prod")

FAIL=0

diagnose_service() {
  local PROJECT="$1" SERVICE="$2" LABEL="$3"
  local EXPECTED_SA
  EXPECTED_SA=$(compute_sa_email "runtime" "$PROJECT")

  echo "--- Diagnosing $LABEL ($SERVICE in $PROJECT) ---"

  # 1. Service exists
  SERVICE_JSON=$(gcloud run services describe "$SERVICE" --region="$REGION" --project="$PROJECT" --format=json 2>/dev/null || echo "")
  if [[ -z "$SERVICE_JSON" ]]; then
    echo "SERVICE_EXISTS_${LABEL}=false"
    echo "ERROR: Service $SERVICE not found in $PROJECT" >&2
    FAIL=1
    return
  fi
  echo "SERVICE_EXISTS_${LABEL}=true"

  # 2. Get service URL
  SERVICE_URL=$(gcloud run services describe "$SERVICE" --region="$REGION" --project="$PROJECT" --format='value(status.url)' 2>/dev/null || true)
  echo "SERVICE_URL_${LABEL}=$SERVICE_URL"

  # 3. Health check
  if [[ "$OAUTH_MODE" == "iap" ]]; then
    TOKEN=$(gcloud auth print-identity-token --audiences="$SERVICE_URL" 2>/dev/null || true)
    HEALTH=$(curl -sS --max-time 10 -H "Authorization: Bearer $TOKEN" "${SERVICE_URL}${HEALTH_ENDPOINT}" 2>/dev/null || echo "TIMEOUT")
  else
    HEALTH=$(curl -sS --max-time 10 "${SERVICE_URL}${HEALTH_ENDPOINT}" 2>/dev/null || echo "TIMEOUT")
  fi
  if echo "$HEALTH" | grep -qF "$HEALTH_RESPONSE"; then
    echo "HEALTH_CHECK_${LABEL}=PASS"
  else
    echo "HEALTH_CHECK_${LABEL}=FAIL"
    echo "HEALTH_RESPONSE_${LABEL}=$(echo "$HEALTH" | tr -cd '[:print:]' | head -c 80)"
    FAIL=1
  fi

  # 4. Runtime SA check
  ACTUAL_SA=$(gcloud run services describe "$SERVICE" --region="$REGION" --project="$PROJECT" --format='value(spec.template.spec.serviceAccountName)' 2>/dev/null || true)
  if [[ "$ACTUAL_SA" == "$EXPECTED_SA" ]]; then
    echo "RUNTIME_SA_${LABEL}=correct"
  else
    echo "RUNTIME_SA_${LABEL}=wrong"
    echo "EXPECTED_SA=$EXPECTED_SA"
    echo "ACTUAL_SA=$ACTUAL_SA"
    FAIL=1
  fi

  # 5. Secret references (not plaintext env vars)
  if echo "$SERVICE_JSON" | grep -q "secretKeyRef"; then
    echo "SECRET_REFS_${LABEL}=PASS"
  else
    echo "SECRET_REFS_${LABEL}=FAIL"
    echo "WARNING: No secret references found — secrets may be in plaintext env vars" >&2
    FAIL=1
  fi

  # 6. No placeholder env vars
  PLACEHOLDERS=$(echo "$SERVICE_JSON" | grep -oE '"value": "(HASH|TODO|PLACEHOLDER|REPLACE_ME)[^"]*"' || true)
  if [[ -z "$PLACEHOLDERS" ]]; then
    echo "NO_PLACEHOLDERS_${LABEL}=PASS"
  else
    echo "NO_PLACEHOLDERS_${LABEL}=FAIL"
    echo "FOUND_PLACEHOLDERS=$PLACEHOLDERS"
    FAIL=1
  fi

  # 7. allUsers invoker binding — depends on oauth.mode
  IAM_POLICY=$(gcloud run services get-iam-policy "$SERVICE" --region="$REGION" --project="$PROJECT" --format=json 2>/dev/null || echo "{}")
  if echo "$IAM_POLICY" | grep -qF "allUsers"; then
    HAS_ALL_USERS=true
  else
    HAS_ALL_USERS=false
  fi
  if [[ "$OAUTH_MODE" == "iap" ]]; then
    # IAP mode: allUsers MUST NOT be present (bypasses IAP)
    if [[ "$HAS_ALL_USERS" == "true" ]]; then
      echo "INVOKER_BINDING_${LABEL}=FAIL"
      echo "REMEDIATION: gcloud run services remove-iam-policy-binding \"$SERVICE\" --member=allUsers --role=roles/run.invoker --region=\"$REGION\" --project=\"$PROJECT\""
      FAIL=1
    else
      echo "INVOKER_BINDING_${LABEL}=PASS"
    fi
  else
    # standalone/auth-proxy: allUsers required for app-level auth
    if [[ "$HAS_ALL_USERS" == "true" ]]; then
      echo "INVOKER_BINDING_${LABEL}=PASS"
    else
      echo "INVOKER_BINDING_${LABEL}=FAIL"
      echo "REMEDIATION: gcloud run services add-iam-policy-binding \"$SERVICE\" --member=allUsers --role=roles/run.invoker --region=\"$REGION\" --project=\"$PROJECT\""
      FAIL=1
    fi
  fi

  # 8. Recent builds
  echo "RECENT_BUILDS_${LABEL}:"
  gcloud builds list --limit=3 --region="$REGION" --project="$PROJECT" --format="table(id,status,startTime)" 2>/dev/null || echo "  (unable to list builds)"
}

# --- Run diagnostics ---
case "$TARGET_ENV" in
  stage)
    diagnose_service "$STAGE_PROJECT" "$(get_service_name 'stage')" "STAGE"
    ;;
  prod)
    diagnose_service "$PROD_PROJECT" "$(get_service_name 'prod')" "PROD"
    ;;
  all)
    diagnose_service "$STAGE_PROJECT" "$(get_service_name 'stage')" "STAGE"
    echo ""
    diagnose_service "$PROD_PROJECT" "$(get_service_name 'prod')" "PROD"
    ;;
  *) echo "ERROR: Invalid --env value: $TARGET_ENV (expected: stage, prod, all)" >&2; exit 1 ;;
esac

# --- Summary ---
echo ""
if [[ $FAIL -eq 0 ]]; then
  echo "DIAGNOSE=PASS"
  exit 0
else
  echo "DIAGNOSE=FAIL"
  exit 1
fi
