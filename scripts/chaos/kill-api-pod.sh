#!/usr/bin/env bash
# Chaos 1 (P13): kill an api pod under traffic → expect zero failed requests (PDB + 2 replicas + readiness).
#   scripts/chaos/kill-api-pod.sh docify-prod https://docify.work
set -euo pipefail
NS="${1:?namespace}"; BASE="${2:?base url}"
fail=0; ok=0
( for _ in $(seq 1 300); do
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$BASE/api/version")
    if [ "$code" = "200" ]; then ok=$((ok+1)); else fail=$((fail+1)); fi
    sleep 0.1
  done; echo "ok=$ok fail=$fail" ) &
sleep 3
victim=$(kubectl -n "$NS" get pods -l app.kubernetes.io/component=api -o jsonpath='{.items[0].metadata.name}')
echo "deleting $victim"
kubectl -n "$NS" delete pod "$victim" --wait=false
wait
