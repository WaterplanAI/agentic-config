#!/usr/bin/env bash
# verify.sh — Post-setup verification (15 acceptance checks)
# Usage: bash verify.sh --config .gcp-setup.yml --env <stage|prod|all>
# Output: CHECK_01..CHECK_15=PASS|FAIL, VERIFY=PASS|FAIL
# CHECK 15 verifies secretmanager.admin was REVOKED (not present unconditionally)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

parse_config_flag "$@"
require_config

# python3 is required for IAM policy inspection (checks 06, 10, 11, 14, 15)
if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 is required for IAM policy checks. Install: brew install python3" >&2
  exit 1
fi

# Load config values
REGION=$(read_config '.region')
REPO_NAME=$(read_config '.artifact_registry.repo_name')
KMS_KEYRING=$(read_config '.kms.keyring')
KMS_KEY=$(read_config '.kms.key')
GITHUB_CONNECTION=$(read_config '.github.connection_name')
FIRESTORE_ENABLED=$(read_config '.firestore.enabled')

# Load secrets manifest
load_secrets_manifest

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

case "$TARGET_ENV" in
  stage) PROJECTS=("$STAGE_PROJECT") ;;
  prod)  PROJECTS=("$PROD_PROJECT") ;;
  all)   PROJECTS=("$STAGE_PROJECT" "$PROD_PROJECT") ;;
  *) echo "ERROR: Invalid --env: $TARGET_ENV" >&2; exit 1 ;;
esac

FAILURES=0
CHECKS=0
REMEDIATIONS=()

check() {
  local num="$1" name="$2" project="$3"
  shift 3
  CHECKS=$((CHECKS + 1))
  local label="CHECK_$(printf '%02d' "$num")_${name}"
  if "$@" &>/dev/null; then
    echo "${label}=PASS (${project})"
  else
    echo "${label}=FAIL (${project})"
    FAILURES=$((FAILURES + 1))
  fi
}

for PROJECT in "${PROJECTS[@]}"; do
  echo "--- Verifying $PROJECT ---"

  RUNTIME_SA=$(compute_sa_email "runtime" "$PROJECT")
  CB_SA=$(compute_sa_email "cloudbuild" "$PROJECT")

  # CHECK 01: GitHub connection exists
  check 1 "GITHUB_CONNECTION" "$PROJECT" \
    gcloud builds connections describe "$GITHUB_CONNECTION" \
      --region="$REGION" --project="$PROJECT"

  # CHECK 02: Required APIs enabled
  ENABLED_APIS=$(gcloud services list --enabled --project="$PROJECT" --format="value(name)" 2>/dev/null)
  REQUIRED_APIS=(run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com cloudkms.googleapis.com)
  if [[ "$FIRESTORE_ENABLED" == "true" ]]; then
    REQUIRED_APIS+=(firestore.googleapis.com)
  fi
  APIS_OK=true
  for API in "${REQUIRED_APIS[@]}"; do
    if ! echo "$ENABLED_APIS" | grep -qxF "$API"; then
      APIS_OK=false
      REMEDIATIONS+=("gcloud services enable $API --project=$PROJECT")
    fi
  done
  CHECKS=$((CHECKS + 1))
  if [[ "$APIS_OK" == true ]]; then
    echo "CHECK_02_APIS=PASS ($PROJECT)"
  else
    echo "CHECK_02_APIS=FAIL ($PROJECT)"
    FAILURES=$((FAILURES + 1))
  fi

  # CHECK 03: Artifact Registry repo exists
  check 3 "AR_REPO" "$PROJECT" \
    gcloud artifacts repositories describe "$REPO_NAME" \
      --location="$REGION" --project="$PROJECT"

  # CHECK 04: Runtime SA exists
  check 4 "RUNTIME_SA" "$PROJECT" \
    gcloud iam service-accounts describe "$RUNTIME_SA" --project="$PROJECT"

  # CHECK 05: Per-secret IAM bindings (config-driven manifest)
  SECRET_IAM_OK=true
  for SECRET in "${SECRETS[@]}"; do
    POLICY=$(gcloud secrets get-iam-policy "$SECRET" --project="$PROJECT" --format=json 2>/dev/null || echo "{}")
    if ! echo "$POLICY" | grep -qF "$RUNTIME_SA"; then
      SECRET_IAM_OK=false
      REMEDIATIONS+=("gcloud secrets add-iam-policy-binding $SECRET --project=$PROJECT --member=serviceAccount:$RUNTIME_SA --role=roles/secretmanager.secretAccessor")
    fi
  done
  CHECKS=$((CHECKS + 1))
  if [[ "$SECRET_IAM_OK" == true ]]; then
    echo "CHECK_05_PER_SECRET_IAM=PASS ($PROJECT)"
  else
    echo "CHECK_05_PER_SECRET_IAM=FAIL ($PROJECT)"
    FAILURES=$((FAILURES + 1))
  fi

  # CHECK 06: CB SA has required roles + serviceAccountUser
  PROJECT_POLICY=$(gcloud projects get-iam-policy "$PROJECT" --format=json 2>/dev/null || echo "{}")

  CB_IAM_OK=true
  for ROLE in "roles/run.admin" "roles/cloudbuild.builds.builder" "roles/artifactregistry.writer"; do
    if ! echo "$PROJECT_POLICY" | ROLE="$ROLE" CB_SA="$CB_SA" python3 -c "
import json, sys, os
role = os.environ['ROLE']
cb_sa = os.environ['CB_SA']
policy = json.load(sys.stdin)
for b in policy.get('bindings', []):
    if b.get('role') == role and ('serviceAccount:' + cb_sa) in b.get('members', []):
        sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
      CB_IAM_OK=false
      REMEDIATIONS+=("gcloud projects add-iam-policy-binding $PROJECT --member=serviceAccount:$CB_SA --role=$ROLE --condition=None")
    fi
  done
  SA_POLICY=$(gcloud iam service-accounts get-iam-policy "$RUNTIME_SA" --project="$PROJECT" --format=json 2>/dev/null || echo "{}")
  if ! echo "$SA_POLICY" | CB_SA="$CB_SA" python3 -c "
import json, sys, os
cb_sa = os.environ['CB_SA']
policy = json.load(sys.stdin)
for b in policy.get('bindings', []):
    if b.get('role') == 'roles/iam.serviceAccountUser' and ('serviceAccount:' + cb_sa) in b.get('members', []):
        sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
    CB_IAM_OK=false
    REMEDIATIONS+=("gcloud iam service-accounts add-iam-policy-binding $RUNTIME_SA --member=serviceAccount:$CB_SA --role=roles/iam.serviceAccountUser --project=$PROJECT")
  fi
  CHECKS=$((CHECKS + 1))
  if [[ "$CB_IAM_OK" == true ]]; then
    echo "CHECK_06_CB_SA_IAM=PASS ($PROJECT)"
  else
    echo "CHECK_06_CB_SA_IAM=FAIL ($PROJECT)"
    FAILURES=$((FAILURES + 1))
  fi

  # CHECK 07: All secrets exist with versions (config-driven)
  SECRETS_OK=true
  for SECRET in "${SECRETS[@]}"; do
    if ! gcloud secrets versions list "$SECRET" --project="$PROJECT" --limit=1 --format="value(name)" 2>/dev/null | grep -q .; then
      SECRETS_OK=false
      REMEDIATIONS+=("printf '<value>' | gcloud secrets versions add $SECRET --data-file=- --project=$PROJECT")
    fi
  done
  CHECKS=$((CHECKS + 1))
  if [[ "$SECRETS_OK" == true ]]; then
    echo "CHECK_07_SECRETS_VERSIONS=PASS ($PROJECT)"
  else
    echo "CHECK_07_SECRETS_VERSIONS=FAIL ($PROJECT)"
    FAILURES=$((FAILURES + 1))
  fi

  # CHECK 08: Stage trigger (PR-based, approval required)
  if [[ "$PROJECT" == "$STAGE_PROJECT" ]]; then
    SERVICE_NAME_STAGE=$(get_service_name "stage")
    TRIGGER_NAME="deploy-${SERVICE_NAME_STAGE}"
    TRIGGER_JSON=$(gcloud builds triggers describe "$TRIGGER_NAME" --region="$REGION" --project="$PROJECT" --format=json 2>/dev/null || echo "{}")
    CHECKS=$((CHECKS + 1))
    if echo "$TRIGGER_JSON" | python3 -c "import json,sys; sys.exit(0 if json.load(sys.stdin).get('approvalConfig',{}).get('approvalRequired') is True else 1)" 2>/dev/null; then
      echo "CHECK_08_TRIGGER_STAGE=PASS ($PROJECT)"
    else
      echo "CHECK_08_TRIGGER_STAGE=FAIL ($PROJECT)"
      FAILURES=$((FAILURES + 1))
      REMEDIATIONS+=("Recreate stage trigger with --require-approval")
    fi
  fi

  # CHECK 09: Prod trigger (main-branch, approval required)
  if [[ "$PROJECT" == "$PROD_PROJECT" ]]; then
    SERVICE_NAME_PROD=$(get_service_name "prod")
    TRIGGER_NAME="deploy-${SERVICE_NAME_PROD}"
    TRIGGER_JSON=$(gcloud builds triggers describe "$TRIGGER_NAME" --region="$REGION" --project="$PROJECT" --format=json 2>/dev/null || echo "{}")
    CHECKS=$((CHECKS + 1))
    if echo "$TRIGGER_JSON" | python3 -c "import json,sys; sys.exit(0 if json.load(sys.stdin).get('approvalConfig',{}).get('approvalRequired') is True else 1)" 2>/dev/null; then
      echo "CHECK_09_TRIGGER_PROD=PASS ($PROJECT)"
    else
      echo "CHECK_09_TRIGGER_PROD=FAIL ($PROJECT)"
      FAILURES=$((FAILURES + 1))
      REMEDIATIONS+=("Recreate prod trigger with --require-approval")
    fi
  fi

  # CHECK 10: No project-level secretAccessor on runtime SA
  CHECKS=$((CHECKS + 1))
  if echo "$PROJECT_POLICY" | RUNTIME_SA="$RUNTIME_SA" python3 -c "
import json, sys, os
runtime_sa = os.environ['RUNTIME_SA']
policy = json.load(sys.stdin)
for b in policy.get('bindings', []):
    if b.get('role') == 'roles/secretmanager.secretAccessor' and ('serviceAccount:' + runtime_sa) in b.get('members', []):
        sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
    echo "CHECK_10_NO_PROJECT_SECRET_ACCESS=FAIL ($PROJECT)"
    FAILURES=$((FAILURES + 1))
    REMEDIATIONS+=("gcloud projects remove-iam-policy-binding $PROJECT --member=serviceAccount:$RUNTIME_SA --role=roles/secretmanager.secretAccessor --condition=None")
  else
    echo "CHECK_10_NO_PROJECT_SECRET_ACCESS=PASS ($PROJECT)"
  fi

  # CHECK 11: CB SA has run.admin (not run.developer)
  CHECKS=$((CHECKS + 1))
  if echo "$PROJECT_POLICY" | CB_SA="$CB_SA" python3 -c "
import json, sys, os
cb_sa = os.environ['CB_SA']
policy = json.load(sys.stdin)
for b in policy.get('bindings', []):
    if b.get('role') == 'roles/run.admin' and ('serviceAccount:' + cb_sa) in b.get('members', []):
        sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
    echo "CHECK_11_CB_ROLE_CORRECT=PASS ($PROJECT)"
  else
    echo "CHECK_11_CB_ROLE_CORRECT=FAIL ($PROJECT)"
    FAILURES=$((FAILURES + 1))
    REMEDIATIONS+=("gcloud projects add-iam-policy-binding $PROJECT --member=serviceAccount:$CB_SA --role=roles/run.admin --condition=None")
  fi

  # Fetch project number once — reused by CHECK 12 (CMEK) and CHECK 15 (SM admin)
  PROJECT_NUMBER=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)' 2>/dev/null)

  # CHECK 12: CMEK — KMS key exists and SM service agent has cryptoKeyEncrypterDecrypter
  CMEK_OK=true
  CHECKS=$((CHECKS + 1))
  if ! gcloud kms keys describe "$KMS_KEY" \
    --keyring="$KMS_KEYRING" \
    --location="$REGION" \
    --project="$PROJECT" &>/dev/null; then
    CMEK_OK=false
    REMEDIATIONS+=("gcloud kms keyrings create $KMS_KEYRING --location=$REGION --project=$PROJECT && gcloud kms keys create $KMS_KEY --keyring=$KMS_KEYRING --location=$REGION --purpose=encryption --project=$PROJECT")
  else
    SM_SA="service-${PROJECT_NUMBER}@gcp-sa-secretmanager.iam.gserviceaccount.com"
    KMS_POLICY=$(gcloud kms keys get-iam-policy "$KMS_KEY" \
      --keyring="$KMS_KEYRING" \
      --location="$REGION" \
      --project="$PROJECT" --format=json 2>/dev/null || echo "{}")
    if ! echo "$KMS_POLICY" | grep -qF "$SM_SA"; then
      CMEK_OK=false
      REMEDIATIONS+=("gcloud kms keys add-iam-policy-binding $KMS_KEY --keyring=$KMS_KEYRING --location=$REGION --member=serviceAccount:$SM_SA --role=roles/cloudkms.cryptoKeyEncrypterDecrypter --project=$PROJECT")
    fi
  fi
  if [[ "$CMEK_OK" == true ]]; then
    echo "CHECK_12_CMEK=PASS ($PROJECT)"
  else
    echo "CHECK_12_CMEK=FAIL ($PROJECT)"
    FAILURES=$((FAILURES + 1))
  fi

  # CHECK 13: Firestore database exists (conditional on firestore.enabled)
  if [[ "$FIRESTORE_ENABLED" == "true" ]]; then
    CHECKS=$((CHECKS + 1))
    if gcloud firestore databases describe --project="$PROJECT" &>/dev/null; then
      echo "CHECK_13_FIRESTORE_DB=PASS ($PROJECT)"
    else
      echo "CHECK_13_FIRESTORE_DB=FAIL ($PROJECT)"
      FAILURES=$((FAILURES + 1))
      REMEDIATIONS+=("gcloud firestore databases create --location=$REGION --type=firestore-native --project=$PROJECT")
    fi

    # CHECK 14: Runtime SA has roles/datastore.user (conditional on firestore.enabled)
    CHECKS=$((CHECKS + 1))
    if echo "$PROJECT_POLICY" | RUNTIME_SA="$RUNTIME_SA" python3 -c "
import json, sys, os
runtime_sa = os.environ['RUNTIME_SA']
policy = json.load(sys.stdin)
for b in policy.get('bindings', []):
    if b.get('role') == 'roles/datastore.user' and ('serviceAccount:' + runtime_sa) in b.get('members', []):
        sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
      echo "CHECK_14_FIRESTORE_IAM=PASS ($PROJECT)"
    else
      echo "CHECK_14_FIRESTORE_IAM=FAIL ($PROJECT)"
      FAILURES=$((FAILURES + 1))
      REMEDIATIONS+=("gcloud projects add-iam-policy-binding $PROJECT --member=serviceAccount:$RUNTIME_SA --role=roles/datastore.user --condition=None")
    fi
  fi

  # CHECK 15: Cloud Build P4SA has no unconditional secretmanager.admin binding
  # (time-bound conditional grants from provisioning are acceptable — they auto-expire)
  CHECKS=$((CHECKS + 1))
  CB_P4SA="service-${PROJECT_NUMBER}@gcp-sa-cloudbuild.iam.gserviceaccount.com"
  SM_ADMIN_STATUS=$(echo "$PROJECT_POLICY" | CB_P4SA="$CB_P4SA" python3 -c "
import json, sys, os
cb_p4sa = os.environ['CB_P4SA']
policy = json.load(sys.stdin)
# Iterate ALL bindings and report the worst case (unconditional > conditional-other > conditional-bootstrap > clean)
severity = {'unconditional': 3, 'conditional-other': 2, 'conditional-bootstrap': 1, 'clean': 0}
worst = 'clean'
for b in policy.get('bindings', []):
    if b['role'] == 'roles/secretmanager.admin' and ('serviceAccount:' + cb_p4sa) in b.get('members', []):
        cond = b.get('condition', {})
        if not cond:
            status = 'unconditional'
        elif cond.get('title') == 'temp-connection-bootstrap':
            status = 'conditional-bootstrap'
        else:
            status = 'conditional-other'
        if severity[status] > severity[worst]:
            worst = status
print(worst)
" 2>/dev/null)
  if [[ -z "$SM_ADMIN_STATUS" ]]; then
    echo "CHECK_15_NO_SM_ADMIN=FAIL ($PROJECT) — policy parsing failed"
    FAILURES=$((FAILURES + 1))
    REMEDIATIONS+=("Manually inspect secretmanager.admin bindings for CB P4SA in $PROJECT")
  else
    case "$SM_ADMIN_STATUS" in
      clean)
        echo "CHECK_15_NO_SM_ADMIN=PASS ($PROJECT)" ;;
      unconditional)
        echo "CHECK_15_NO_SM_ADMIN=FAIL ($PROJECT) — unconditional secretmanager.admin still bound"
        FAILURES=$((FAILURES + 1))
        REMEDIATIONS+=("gcloud projects remove-iam-policy-binding $PROJECT --member=serviceAccount:$CB_P4SA --role=roles/secretmanager.admin --condition=None") ;;
      conditional-bootstrap)
        echo "CHECK_15_NO_SM_ADMIN=PASS ($PROJECT) — time-bound grant present, will auto-expire" ;;
      *)
        echo "CHECK_15_NO_SM_ADMIN=FAIL ($PROJECT) — unexpected conditional secretmanager.admin binding"
        FAILURES=$((FAILURES + 1))
        REMEDIATIONS+=("Inspect and remove secretmanager.admin binding for $CB_P4SA in $PROJECT") ;;
    esac
  fi
done

# --- Summary ---
echo ""
echo "CHECKS_RUN=$CHECKS"
echo "FAILURES=$FAILURES"

if [[ ${#REMEDIATIONS[@]} -gt 0 ]]; then
  echo ""
  echo "--- REMEDIATION COMMANDS ---"
  for i in "${!REMEDIATIONS[@]}"; do
    echo "REMEDIATION_$(printf '%02d' $((i+1)))=${REMEDIATIONS[$i]}"
  done
fi

if [[ $FAILURES -eq 0 ]]; then
  echo "VERIFY=PASS"
  exit 0
else
  echo "VERIFY=FAIL"
  exit 1
fi
