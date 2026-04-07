#!/usr/bin/env bash
# provision.sh — Provision GCP resources for Cloud Build + Cloud Run
# Usage: bash provision.sh --config .gcp-setup.yml --env <stage|prod|all> [--cmek-only] [--skip-triggers]
# Output: KEY=VALUE pairs + PROVISION=PASS|FAIL
# NOTE: This script uses best-effort continuation — errors set FAIL=1 via ||
# clauses but execution continues to provision as much as possible. The FAIL
# counter at the end is the safety net; callers must check PROVISION=PASS|FAIL.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

# Parse --config first
parse_config_flag "$@"
require_config

# --- Read from config ---
REGION=$(read_config '.region')
REPO_NAME=$(read_config '.artifact_registry.repo_name')
KMS_KEYRING=$(read_config '.kms.keyring')
KMS_KEY=$(read_config '.kms.key')
GITHUB_CONNECTION=$(read_config '.github.connection_name')
GITHUB_LINKED_REPO=$(read_config '.github.linked_repo')
SA_RUNTIME_PREFIX=$(read_config '.sa_prefix.runtime')
SA_CB_PREFIX=$(read_config '.sa_prefix.cloudbuild')
FIRESTORE_ENABLED=$(read_config '.firestore.enabled')
FIRESTORE_COLLECTION=$(read_config '.firestore.collection')
FIRESTORE_TTL_FIELD=$(read_config '.firestore.ttl_field')

# --- Defaults ---
TARGET_ENV="all"
SKIP_TRIGGERS=false
CMEK_ONLY=false

# --- Parse remaining flags ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)        shift 2 ;;  # already parsed
    --env)           TARGET_ENV="${2:?--env requires a value}"; shift 2 ;;
    --skip-triggers) SKIP_TRIGGERS=true; shift ;;
    --cmek-only)     CMEK_ONLY=true; shift ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

STAGE_PROJECT=$(get_project_id "stage")
PROD_PROJECT=$(get_project_id "prod")

# --- Build project list ---
case "$TARGET_ENV" in
  stage) PROJECTS=("$STAGE_PROJECT") ;;
  prod)  PROJECTS=("$PROD_PROJECT") ;;
  all)   PROJECTS=("$STAGE_PROJECT" "$PROD_PROJECT") ;;
  *) echo "ERROR: Invalid --env value: $TARGET_ENV" >&2; exit 1 ;;
esac

FAIL=0

# --- CMEK: Encryption key setup for GitHub connection ---
for PROJECT in "${PROJECTS[@]}"; do
  echo "Setting up CMEK encryption in $PROJECT..."

  # Enable Cloud KMS + Secret Manager APIs
  gcloud services enable cloudkms.googleapis.com secretmanager.googleapis.com \
    --project="$PROJECT" || { echo "ERROR: Failed to enable KMS/SM APIs in $PROJECT" >&2; FAIL=1; }

  # Provision Secret Manager service agent (enabling API alone does NOT create it)
  gcloud beta services identity create \
    --service=secretmanager.googleapis.com \
    --project="$PROJECT" 2>/dev/null || true

  # Create keyring (idempotent)
  if gcloud kms keyrings create "$KMS_KEYRING" \
    --location="$REGION" \
    --project="$PROJECT" 2>/dev/null; then
    echo "KMS_KEYRING_${PROJECT}=created"
  else
    echo "KMS_KEYRING_${PROJECT}=exists"
  fi

  # Create key (idempotent)
  if gcloud kms keys create "$KMS_KEY" \
    --keyring="$KMS_KEYRING" \
    --location="$REGION" \
    --purpose=encryption \
    --project="$PROJECT" 2>/dev/null; then
    echo "KMS_KEY_${PROJECT}=created"
  else
    echo "KMS_KEY_${PROJECT}=exists"
  fi

  # Grant Secret Manager service agent access to the key
  PROJECT_NUMBER=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
  SM_SA="service-${PROJECT_NUMBER}@gcp-sa-secretmanager.iam.gserviceaccount.com"
  gcloud kms keys add-iam-policy-binding "$KMS_KEY" \
    --keyring="$KMS_KEYRING" \
    --location="$REGION" \
    --member="serviceAccount:${SM_SA}" \
    --role="roles/cloudkms.cryptoKeyEncrypterDecrypter" \
    --project="$PROJECT" --quiet || { echo "ERROR: Failed to grant KMS access to SM agent in $PROJECT" >&2; FAIL=1; }
  echo "KMS_IAM_${PROJECT}=OK"

  # JIT: Temporarily grant Cloud Build P4SA secretmanager.admin for GitHub connection
  # creation. Skip if connection already exists (grant not needed).
  # WARNING: roles/secretmanager.admin grants full secret management for ALL secrets
  # in the project during the 20-minute window. This is required for Cloud Build
  # to create the GitHub connection secret. The binding auto-expires via IAM condition.
  # Risk: any Cloud Build trigger firing during this window has full secret access.
  # RECOMMENDATION: Avoid triggering builds during this window. Complete the GitHub
  # connection creation promptly so the grant expires unused for as long as possible.
  if ! gcloud builds connections describe "$GITHUB_CONNECTION" --region="$REGION" --project="$PROJECT" &>/dev/null; then
    CB_P4SA="service-${PROJECT_NUMBER}@gcp-sa-cloudbuild.iam.gserviceaccount.com"
    EXPIRY=$(date -u -v+20M '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u -d '+20 minutes' '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || true)
    if [[ -z "$EXPIRY" ]]; then
      echo "ERROR: Failed to compute expiry timestamp — cannot create time-bound IAM grant safely" >&2
      FAIL=1
      continue
    fi
    gcloud projects add-iam-policy-binding "$PROJECT" \
      --member="serviceAccount:${CB_P4SA}" \
      --role="roles/secretmanager.admin" \
      --condition="expression=request.time < timestamp('${EXPIRY}'),title=temp-connection-bootstrap,description=Temporary for GitHub connection - auto-expires ${EXPIRY}" \
      --quiet || { echo "ERROR: Failed to grant temporary secretmanager.admin to CB P4SA in $PROJECT" >&2; FAIL=1; }
    echo "CB_P4SA_SM_ADMIN_${PROJECT}=GRANTED_UNTIL_${EXPIRY}"
  else
    echo "CB_P4SA_SM_ADMIN_${PROJECT}=skipped (connection exists)"
  fi
done

if [[ "$CMEK_ONLY" == true ]]; then
  if [[ $FAIL -eq 0 ]]; then
    echo "CMEK=PASS"
    exit 0
  else
    echo "CMEK=FAIL"
    exit 1
  fi
fi

# --- Enable APIs ---
APIS=(run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com)
if [[ "$FIRESTORE_ENABLED" == "true" ]]; then
  APIS+=(firestore.googleapis.com)
fi

APIS_COUNT=0
for PROJECT in "${PROJECTS[@]}"; do
  echo "Enabling APIs for $PROJECT..."
  if gcloud services enable "${APIS[@]}" --project="$PROJECT"; then
    APIS_COUNT=$((APIS_COUNT + ${#APIS[@]}))
  else
    echo "ERROR: Failed to enable APIs in $PROJECT" >&2
    FAIL=1
  fi
done
echo "APIS_ENABLED=$APIS_COUNT"

# --- Create Firestore database (conditional) ---
if [[ "$FIRESTORE_ENABLED" == "true" ]]; then
  for PROJECT in "${PROJECTS[@]}"; do
    echo "Creating Firestore database in $PROJECT..."
    if gcloud firestore databases create \
      --location="$REGION" --type=firestore-native \
      --project="$PROJECT" 2>/dev/null; then
      echo "FIRESTORE_DB_${PROJECT}=created"
    else
      echo "FIRESTORE_DB_${PROJECT}=exists"
    fi
  done
fi

# --- Create Artifact Registry repos ---
for PROJECT in "${PROJECTS[@]}"; do
  echo "Creating Artifact Registry repo in $PROJECT..."
  if gcloud artifacts repositories create "$REPO_NAME" \
    --repository-format=docker \
    --location="$REGION" \
    --description="Docker images" \
    --project="$PROJECT" 2>/dev/null; then
    echo "AR_REPO_${PROJECT}=created"
  else
    echo "AR_REPO_${PROJECT}=exists"
  fi
done

# --- Create service accounts ---
for PROJECT in "${PROJECTS[@]}"; do
  echo "Creating runtime SA in $PROJECT..."
  if gcloud iam service-accounts create "$SA_RUNTIME_PREFIX" \
    --display-name="Cloud Run Runtime" \
    --project="$PROJECT" 2>/dev/null; then
    echo "RUNTIME_SA_${PROJECT}=created"
  else
    echo "RUNTIME_SA_${PROJECT}=exists"
  fi

  echo "Creating Cloud Build SA in $PROJECT..."
  if gcloud iam service-accounts create "$SA_CB_PREFIX" \
    --display-name="Cloud Build" \
    --project="$PROJECT" 2>/dev/null; then
    echo "CB_SA_${PROJECT}=created"
  else
    echo "CB_SA_${PROJECT}=exists"
  fi
done

# --- Grant IAM permissions ---
for PROJECT in "${PROJECTS[@]}"; do
  echo "Granting IAM permissions in $PROJECT..."
  CB_SA=$(compute_sa_email "cloudbuild" "$PROJECT")
  RUNTIME_SA=$(compute_sa_email "runtime" "$PROJECT")

  # Cloud Build SA: build ops, push images, deploy Cloud Run + set IAM
  for ROLE in roles/cloudbuild.builds.builder roles/artifactregistry.writer roles/run.admin; do
    gcloud projects add-iam-policy-binding "$PROJECT" \
      --member="serviceAccount:${CB_SA}" \
      --role="$ROLE" \
      --condition=None --quiet || { echo "ERROR: Failed to grant $ROLE to $CB_SA" >&2; FAIL=1; }
  done

  # CB SA must impersonate runtime SA for Cloud Run revisions
  gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_SA" \
    --member="serviceAccount:${CB_SA}" \
    --role="roles/iam.serviceAccountUser" \
    --project="$PROJECT" --quiet || { echo "ERROR: Failed to grant serviceAccountUser" >&2; FAIL=1; }

  # Firestore access for runtime SA (conditional)
  if [[ "$FIRESTORE_ENABLED" == "true" ]]; then
    gcloud projects add-iam-policy-binding "$PROJECT" \
      --member="serviceAccount:${RUNTIME_SA}" \
      --role="roles/datastore.user" \
      --condition=None --quiet || { echo "ERROR: Failed to grant datastore.user to $RUNTIME_SA" >&2; FAIL=1; }
  fi

  # Defensive cleanup: remove project-level secretAccessor from runtime SA
  # Attempt removal directly to avoid TOCTOU race between check and remove
  echo "Checking for project-level secretmanager.secretAccessor on ${RUNTIME_SA}..."
  gcloud projects remove-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --condition=None --quiet 2>/dev/null && echo "DEFENSIVE_CLEANUP_${PROJECT}=removed" || echo "DEFENSIVE_CLEANUP_${PROJECT}=clean"
done
echo "IAM_BINDINGS=OK"

# --- Create Cloud Build triggers ---
if [[ "$SKIP_TRIGGERS" == true ]]; then
  echo "TRIGGER_STAGE=skipped"
  echo "TRIGGER_PROD=skipped"
else
  if [[ "$GITHUB_CONNECTION" == "null" || -z "$GITHUB_CONNECTION" || "$GITHUB_LINKED_REPO" == "null" || -z "$GITHUB_LINKED_REPO" ]]; then
    echo "WARNING: github.connection_name and github.linked_repo required in config for triggers. Skipping." >&2
    echo "TRIGGER_STAGE=skipped"
    echo "TRIGGER_PROD=skipped"
  else
    SERVICE_NAME_STAGE=$(get_service_name "stage")
    SERVICE_NAME_PROD=$(get_service_name "prod")
    BUILD_CONFIG_STAGE=$(get_build_config "stage")
    BUILD_CONFIG_PROD=$(get_build_config "prod")
    CB_SA_STAGE=$(compute_sa_email "cloudbuild" "$STAGE_PROJECT")
    CB_SA_PROD=$(compute_sa_email "cloudbuild" "$PROD_PROJECT")

    # Stage trigger: PR targeting main, requires approval
    # NOTE: --comment-control=COMMENTS_ENABLED_FOR_EXTERNAL_CONTRIBUTORS_ONLY
    # is not yet supported by gcloud builds triggers create github. When available,
    # add it to prevent external contributors from triggering builds via /gcbrun.
    if [[ "$TARGET_ENV" == "stage" || "$TARGET_ENV" == "all" ]]; then
      if [[ -z "$BUILD_CONFIG_STAGE" || "$BUILD_CONFIG_STAGE" == "null" ]]; then
        echo "WARNING: projects.stage.build_config not set. Skipping stage trigger." >&2
        echo "TRIGGER_STAGE=skipped"
      elif gcloud builds triggers describe "deploy-${SERVICE_NAME_STAGE}" \
        --region="$REGION" --project="$STAGE_PROJECT" &>/dev/null; then
        echo "TRIGGER_STAGE=exists"
      elif gcloud builds triggers create github \
        --name="deploy-${SERVICE_NAME_STAGE}" \
        --region="$REGION" \
        --repository="projects/$STAGE_PROJECT/locations/$REGION/connections/$GITHUB_CONNECTION/repositories/$GITHUB_LINKED_REPO" \
        --pull-request-pattern="^main$" \
        --require-approval \
        --build-config="$BUILD_CONFIG_STAGE" \
        --service-account="projects/$STAGE_PROJECT/serviceAccounts/${CB_SA_STAGE}" \
        --project="$STAGE_PROJECT"; then
        echo "TRIGGER_STAGE=created"
      else
        echo "ERROR: Failed to create stage trigger" >&2
        echo "TRIGGER_STAGE=FAIL"
        FAIL=1
      fi
    fi

    # Prod trigger: push to main, requires approval
    if [[ "$TARGET_ENV" == "prod" || "$TARGET_ENV" == "all" ]]; then
      if [[ -z "$BUILD_CONFIG_PROD" || "$BUILD_CONFIG_PROD" == "null" ]]; then
        echo "WARNING: projects.prod.build_config not set. Skipping prod trigger." >&2
        echo "TRIGGER_PROD=skipped"
      elif gcloud builds triggers describe "deploy-${SERVICE_NAME_PROD}" \
        --region="$REGION" --project="$PROD_PROJECT" &>/dev/null; then
        echo "TRIGGER_PROD=exists"
      elif gcloud builds triggers create github \
        --name="deploy-${SERVICE_NAME_PROD}" \
        --region="$REGION" \
        --repository="projects/$PROD_PROJECT/locations/$REGION/connections/$GITHUB_CONNECTION/repositories/$GITHUB_LINKED_REPO" \
        --branch-pattern="^main$" \
        --require-approval \
        --build-config="$BUILD_CONFIG_PROD" \
        --service-account="projects/$PROD_PROJECT/serviceAccounts/${CB_SA_PROD}" \
        --project="$PROD_PROJECT"; then
        echo "TRIGGER_PROD=created"
      else
        echo "ERROR: Failed to create prod trigger" >&2
        echo "TRIGGER_PROD=FAIL"
        FAIL=1
      fi
    fi
  fi
fi

# --- Configure Firestore TTL policy (conditional) ---
if [[ "$FIRESTORE_ENABLED" == "true" ]]; then
  for PROJECT in "${PROJECTS[@]}"; do
    echo "Configuring Firestore TTL policy in $PROJECT..."
    if gcloud firestore fields ttls update "$FIRESTORE_TTL_FIELD" \
      --collection-group="$FIRESTORE_COLLECTION" \
      --enable-ttl \
      --project="$PROJECT" --async 2>/dev/null; then
      echo "FIRESTORE_TTL_${PROJECT}=configured"
    else
      echo "FIRESTORE_TTL_${PROJECT}=exists_or_pending"
    fi
  done
fi

# --- Summary ---
if [[ $FAIL -eq 0 ]]; then
  echo "PROVISION=PASS"
  exit 0
else
  echo "PROVISION=FAIL"
  exit 1
fi
