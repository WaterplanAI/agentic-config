#!/usr/bin/env bash
# config.sh — Shared config reader for gcp-setup tools
# Source this file: source "$(dirname "$0")/config.sh"
# Requires: yq, CONFIG_FILE env var or --config flag parsed by caller

set -euo pipefail

if ((BASH_VERSINFO[0] < 4 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] < 2))); then
  echo "ERROR: bash 4.2+ required (found ${BASH_VERSION}). Install: brew install bash" >&2
  exit 1
fi

# Validate environment name is one of the known values
# Used by get_project_id, get_service_name, get_build_config to prevent
# untrusted input from reaching yq query interpolation.
validate_env_name() {
  case "$1" in
    stage|prod) ;;
    *) echo "ERROR: Invalid environment name: $1 (expected: stage or prod)" >&2; exit 1 ;;
  esac
}

# Validate config values contain only safe characters
validate_config_value() {
  local value="$1" field="$2"
  if [[ ! "$value" =~ ^[a-zA-Z0-9._:/@-]+$ ]]; then
    echo "ERROR: Invalid characters in config field '$field': $value" >&2
    exit 1
  fi
}

# Resolve config file path
resolve_config() {
  if [[ -z "${CONFIG_FILE:-}" ]]; then
    CONFIG_FILE=".gcp-setup.yml"
  fi
}

# Read a value from the config file
# Usage: read_config '.projects.stage.id'
# SAFETY: Callers must use hardcoded yq query strings only.
# Never interpolate untrusted input into the query parameter — yq
# expressions can execute arbitrary logic (e.g., env, shell).
read_config() {
  local query="$1"
  yq -r "$query" "$CONFIG_FILE"
}

# Validate config file exists and yq is installed
require_config() {
  if ! command -v yq &>/dev/null; then
    echo "ERROR: yq not found. Install: brew install yq" >&2
    exit 1
  fi
  resolve_config
  if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "ERROR: Config file not found: $CONFIG_FILE" >&2
    echo "Run the gcp-setup skill to generate .gcp-setup.yml" >&2
    exit 1
  fi
  # Basic validation
  local version
  version=$(read_config '.version' 2>/dev/null)
  if [[ "$version" != "1" ]]; then
    echo "ERROR: Unsupported config version: $version (expected: 1)" >&2
    exit 1
  fi
  # Validate all config values that flow into gcloud commands
  local VALUE
  for field in \
    '.region' \
    '.projects.stage.id' '.projects.prod.id' \
    '.sa_prefix.runtime' '.sa_prefix.cloudbuild' \
    '.kms.keyring' '.kms.key' \
    '.github.connection_name' '.github.linked_repo' \
    '.artifact_registry.repo_name'; do
    VALUE=$(read_config "$field" 2>/dev/null || true)
    if [[ -n "$VALUE" && "$VALUE" != "null" ]]; then
      validate_config_value "$VALUE" "$field"
    fi
  done
}

# Load secrets manifest from config into SECRETS array and SECRET_MAP associative array
# After calling: SECRETS=("secret-name-1" "secret-name-2" ...)
#                SECRET_MAP[ENV_VAR]="secret-name"
load_secrets_manifest() {
  local count
  count=$(read_config '.secrets | length')
  if [[ "$count" == "0" || "$count" == "null" ]]; then
    echo "ERROR: No secrets defined in config" >&2
    exit 1
  fi

  SECRETS=()
  declare -gA SECRET_MAP=()

  local i name env_var
  for ((i=0; i<count; i++)); do
    name=$(read_config ".secrets[$i].name")
    env_var=$(read_config ".secrets[$i].env_var")
    validate_config_value "$name" ".secrets[$i].name"
    if [[ ! "$env_var" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
      echo "ERROR: Invalid env_var name in config field '.secrets[$i].env_var': $env_var" >&2
      exit 1
    fi
    SECRETS+=("$name")
    SECRET_MAP["$env_var"]="$name"
  done
}

# Compute service account email from prefix and project
# Usage: compute_sa_email "runtime" "$PROJECT"
compute_sa_email() {
  local prefix="$1" project="$2"
  local sa_prefix
  sa_prefix=$(read_config ".sa_prefix.$prefix")
  echo "${sa_prefix}@${project}.iam.gserviceaccount.com"
}

# Get project ID for an environment
# Usage: get_project_id "stage" or get_project_id "prod"
get_project_id() {
  validate_env_name "$1"
  read_config ".projects.${1}.id"
}

# Get service name for an environment
get_service_name() {
  validate_env_name "$1"
  read_config ".projects.${1}.service_name"
}

# Get build config path for an environment
get_build_config() {
  validate_env_name "$1"
  read_config ".projects.${1}.build_config"
}

# Parse --config flag from args (call before require_config)
# Usage: parse_config_flag "$@"  — sets CONFIG_FILE if --config is present
# LIMITATION: This scans args linearly, shifting one token at a time for
# unknown flags. Two-arg flags other than --config are not recognized here,
# so a stray value could be mistaken for a flag. Callers must ensure --config
# appears before any ambiguous positional arguments.
parse_config_flag() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --config) CONFIG_FILE="${2:?--config requires a path}"; return 0 ;;
      *) shift ;;
    esac
  done
}
