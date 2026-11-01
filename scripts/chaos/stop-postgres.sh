#!/usr/bin/env bash
# Chaos 3 (P13): Postgres down for ~60 s → readiness fails, CloudFront serves 503 → the SPA shows the
# "backend sleeping" banner; workers back off; everything recovers by itself (F23).
# Argo CD selfHeal would scale Postgres straight back (seen 2026-11-02: in 4 s), so auto-sync is paused on
# root + data first and restored at the end (root re-applies the child apps' sync policy).
#   scripts/chaos/stop-postgres.sh          (on the server, or with kubectl over the SSM tunnel)
set -euo pipefail
restore_sync() {
  kubectl -n argocd patch application root --type merge \
    -p '{"spec":{"syncPolicy":{"automated":{"prune":true,"selfHeal":true}}}}' >/dev/null
  echo "auto-sync restored (root re-applies the data app's policy within a minute)"
}
trap restore_sync EXIT
for app in root data; do
  kubectl -n argocd patch application "$app" --type json \
    -p '[{"op":"remove","path":"/spec/syncPolicy/automated"}]' >/dev/null 2>&1 || true
done
kubectl -n data scale statefulset/postgres --replicas=0
kubectl -n data wait --for=delete pod/postgres-0 --timeout=90s
echo "Postgres stopped at $(date +%T). Watch /api/ready fail and the UI banner. Restoring in 60 s ..."
sleep 60
kubectl -n data scale statefulset/postgres --replicas=1
kubectl -n data wait --for=condition=Ready pod/postgres-0 --timeout=5m
echo "Restored at $(date +%T). Verify: smoke.sh + Grafana error rate back to 0."
