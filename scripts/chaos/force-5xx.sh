#!/usr/bin/env bash
# Chaos 5 (P10/P11 leftover): prove the "API 5xx above 5%" alert end to end on STAGING.
# Why not just stop Postgres? Readiness (/api/ready = SELECT 1) would fail, Traefik stops routing, and
# no request ever reaches the app's 5xx counter. Instead: revoke SELECT on one table from the staging DB
# role - /api/ready stays OK (pods stay Ready) while every docs-list request fails with 500.
# Then drive traffic for ~13 min (the rule needs > 5% for 10 min), expect the SNS e-mail, and restore.
# Runs ON the server (kubectl); traffic comes from anywhere:
#   sudo bash scripts/chaos/force-5xx.sh break     # then: k6 / curl loop against staging docs list
#   sudo bash scripts/chaos/force-5xx.sh restore
set -euo pipefail
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"
psql_() { kubectl -n data exec postgres-0 -- psql -U postgres -d docify_staging -v ON_ERROR_STOP=1 -Atc "$1"; }
case "${1:-}" in
  break)   psql_ "REVOKE SELECT ON documents FROM docify_staging"; echo "staging: documents unreadable (500s) at $(date +%T)";;
  restore) psql_ "GRANT SELECT ON documents TO docify_staging"; echo "staging: restored at $(date +%T)";;
  status)  psql_ "SELECT has_table_privilege('docify_staging', 'documents', 'SELECT')";;
  *) echo "usage: $0 break|restore|status"; exit 2;;
esac
