#!/usr/bin/env bash
# =============================================================================
# Write the real secret values into SSM Parameter Store (Master Doc §15.2, R6).
#
# Terraform only creates the parameters with a placeholder (write-only
# value_wo), so the real values never enter Terraform state. This script
# overwrites them. It NEVER prints a value.
#
# Usage:
#   scripts/init-params.sh [--env staging|prod|shared|all] [--from-dir DIR]
#                          [--only <path>] [--generate] [--region REGION]
#
#   --env       which group to set (default: all)
#   --from-dir  read each value from DIR/<env>/<path>, e.g.
#               DIR/staging/github/app_private_key   (PEM file as-is)
#               DIR/shared/postgres/superuser_password
#               Missing files are skipped (or prompted, unless --non-interactive).
#   --only      set just one parameter path, e.g. --only github/webhook_secret
#   --generate  generate random values for machine-only secrets
#               (db/password, app/session_pepper, github/webhook_secret,
#               postgres/superuser_password, grafana/admin_password) instead
#               of prompting. GitHub webhook secret must then be copied into
#               the GitHub App settings -> use `aws ssm get-parameter
#               --with-decryption` yourself; this script won't show it.
#   --non-interactive  never prompt; skip values that have no source
#
# Not handled here: /docify/<env>/app/origin_verify_header (Terraform owns it).
# After changing values: R6 (force-sync ExternalSecrets, restart pods).
# Needs: aws cli v2 with credentials for the account (aws login), openssl.
# =============================================================================
set -euo pipefail

REGION="${AWS_REGION:-ap-south-1}"
SCOPE="all"
FROM_DIR=""
ONLY=""
GENERATE=false
INTERACTIVE=true

ENV_PATHS=(
  db/password
  app/session_pepper
  github/app_private_key
  github/client_secret
  github/webhook_secret
  google/client_secret
  ai/anthropic_api_key
  ai/voyage_api_key
)
SHARED_PATHS=(
  postgres/superuser_password
  grafana/admin_password
)
GENERATABLE=" db/password app/session_pepper github/webhook_secret postgres/superuser_password grafana/admin_password "

usage() { sed -n '2,32p' "$0" | sed 's/^# \{0,1\}//'; }

while [ $# -gt 0 ]; do
  case "$1" in
    --env) SCOPE="$2"; shift 2 ;;
    --from-dir) FROM_DIR="${2%/}"; shift 2 ;;
    --only) ONLY="$2"; shift 2 ;;
    --generate) GENERATE=true; shift ;;
    --region) REGION="$2"; shift 2 ;;
    --non-interactive) INTERACTIVE=false; shift ;;
    -h | --help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$SCOPE" in
  staging | prod | shared | all) ;;
  *) echo "--env must be staging, prod, shared or all" >&2; exit 2 ;;
esac

command -v aws >/dev/null || { echo "aws cli not found" >&2; exit 2; }
if $GENERATE; then command -v openssl >/dev/null || { echo "openssl not found" >&2; exit 2; }; fi

# Values go through a private temp file (never argv: argv is visible in `ps`).
umask 077
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

# Fail early if not logged in (prints nothing about the account on purpose).
if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "AWS credentials not working - run 'aws login' first." >&2
  exit 1
fi
echo "AWS credentials OK. Region: $REGION"

SET=0
SKIPPED=0

# put_param <full-name> <relative-path> <group>
put_param() {
  local name="$1" rel="$2" group="$3"
  : >"$TMP"

  if [ -n "$FROM_DIR" ] && [ -f "$FROM_DIR/$group/$rel" ]; then
    cat "$FROM_DIR/$group/$rel" >"$TMP"
  elif $GENERATE && [[ "$GENERATABLE" == *" $rel "* ]]; then
    # 32 random bytes, URL-safe base64 without padding (~43 chars).
    openssl rand -base64 32 | tr '+/' '-_' | tr -d '=\n' >"$TMP"
  elif $INTERACTIVE; then
    if [ "$rel" = "github/app_private_key" ]; then
      echo "  $name: path to the .pem file (empty = skip): "
      local pem
      read -r pem
      if [ -n "$pem" ]; then
        [ -f "$pem" ] || { echo "  file not found: $pem" >&2; SKIPPED=$((SKIPPED + 1)); return; }
        cat "$pem" >"$TMP"
      fi
    else
      local value
      read -rsp "  $name (input hidden, empty = skip): " value
      echo
      printf '%s' "$value" >"$TMP"
      unset value
    fi
  fi

  if [ ! -s "$TMP" ]; then
    echo "  skip  $name"
    SKIPPED=$((SKIPPED + 1))
    return
  fi

  aws ssm put-parameter \
    --region "$REGION" \
    --name "$name" \
    --type SecureString \
    --overwrite \
    --value "file://$TMP" \
    --query Version --output text >/dev/null
  : >"$TMP"
  echo "  set   $name"
  SET=$((SET + 1))
}

process_group() {
  local group="$1"
  shift
  local rel
  echo "[$group]"
  for rel in "$@"; do
    if [ -n "$ONLY" ] && [ "$ONLY" != "$rel" ]; then continue; fi
    put_param "/docify/$group/$rel" "$rel" "$group"
  done
}

for env in staging prod; do
  if [ "$SCOPE" = "all" ] || [ "$SCOPE" = "$env" ]; then
    process_group "$env" "${ENV_PATHS[@]}"
  fi
done
if [ "$SCOPE" = "all" ] || [ "$SCOPE" = "shared" ]; then
  process_group shared "${SHARED_PATHS[@]}"
fi

echo "Done: $SET set, $SKIPPED skipped."
echo "Next (R6): force-sync ExternalSecrets and restart the affected deployments."
