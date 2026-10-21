#!/usr/bin/env bash
# =============================================================================
# Validate everything under deploy/ (used locally and by the CI "chart" job,
# §14.2 / §21): helm lint + helm template | kubeconform for every chart and
# values file, kustomize build of the monitoring config, JSON check of the
# dashboards.
#
#   deploy/validate.sh                 # uses helm/kubeconform/kubectl from PATH
#   HELM=.tools/helm.exe KUBECONFORM=.tools/kubeconform.exe deploy/validate.sh
#
# CRD-based objects (Application, ExternalSecret, ScaledObject, Certificate,
# ServiceMonitor, ...) are validated against the community CRD schema catalog;
# anything without a schema is reported as skipped, not failed.
# =============================================================================
set -euo pipefail

cd "$(dirname "$0")/.."

HELM="${HELM:-helm}"
KUBECONFORM="${KUBECONFORM:-kubeconform}"
KUBECTL="${KUBECTL:-kubectl}"
K8S_VERSION="${K8S_VERSION:-1.34.0}"
CRD_CATALOG='https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json'

out="$(mktemp -d)"
trap 'rm -rf "$out"' EXIT
fail=0

conform() {  # $1 = label, stdin = manifests
  echo "--- kubeconform: $1"
  if ! "$KUBECONFORM" -strict -summary -ignore-missing-schemas \
        -kubernetes-version "$K8S_VERSION" \
        -schema-location default -schema-location "$CRD_CATALOG" -; then
    fail=1
  fi
}

render() {  # $1 label, $2 release, $3 namespace, $4 chart, rest = helm args
  local label="$1" rel="$2" ns="$3" chart="$4"; shift 4
  echo "=== $label"
  if ! "$HELM" lint --strict "$chart" "$@" >"$out/lint.txt" 2>&1; then
    cat "$out/lint.txt"; fail=1; return
  fi
  if ! "$HELM" template "$rel" "$chart" -n "$ns" "$@" >"$out/manifest.yaml"; then
    fail=1; return
  fi
  conform "$label" <"$out/manifest.yaml"
}

# --- app chart, one run per environment ------------------------------------
for env in local staging prod eks-lab; do
  ns="docify-$env"; [ "$env" = eks-lab ] && ns=docify-staging
  render "docify ($env)" docify "$ns" deploy/helm/docify -f "deploy/values/$env.yaml"
done
# all optional features on (ServiceMonitor, dev services) to cover every template
render "docify (all features)" docify docify-staging deploy/helm/docify \
  -f deploy/values/staging.yaml --set serviceMonitor.enabled=true \
  --set devServices.elasticmq.enabled=true --set devServices.mailpit.enabled=true

# --- data chart --------------------------------------------------------------
render "data (cloud)" data data deploy/helm/data
render "data (local)" data data deploy/helm/data -f deploy/values/data-local.yaml

# --- platform-config ---------------------------------------------------------
render "platform-config" platform-config argocd deploy/helm/platform-config

# --- Argo CD roots (defaults = P8 set, and everything enabled) --------------
render "root (P8 defaults)" root argocd deploy/argocd/root
render "root (all apps)" root argocd deploy/argocd/root \
  --set apps.keda.enabled=true --set apps.monitoring.enabled=true \
  --set apps.data.enabled=true --set apps.docifyStaging.enabled=true \
  --set apps.docifyProd.enabled=true
render "root-local" root-local argocd deploy/argocd/local

# --- monitoring config (kustomize) -------------------------------------------
if command -v "$KUBECTL" >/dev/null 2>&1; then
  echo "=== monitoring config (kustomize)"
  "$KUBECTL" kustomize deploy/values/platform/dashboards | conform "dashboards"
else
  echo "(kubectl not found - skipping kustomize build)"
fi

# --- dashboards are valid JSON -----------------------------------------------
for f in deploy/values/platform/dashboards/*.json; do
  python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$f" 2>/dev/null \
    || python -c 'import json,sys; json.load(open(sys.argv[1]))' "$f" \
    || { echo "invalid JSON: $f"; fail=1; }
done

if [ "$fail" -ne 0 ]; then
  echo "VALIDATION FAILED"; exit 1
fi
echo "ALL OK"
