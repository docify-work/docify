#!/usr/bin/env bash
# Chaos 2 (P13): kill a worker while it runs a job → the lease expires (≤ 5 min), the reconciler or
# SQS redelivery re-claims it with a higher fence, and the job still succeeds exactly once (F50).
#   scripts/chaos/kill-worker-mid-job.sh docify-staging
set -euo pipefail
NS="${1:?namespace}"
pod=$(kubectl -n "$NS" get pods -l app.kubernetes.io/component=worker -o jsonpath='{.items[0].metadata.name}')
echo "Trigger a reindex in the UI now (Repos → ⋯ → Reindex). Killing $pod in 20 s (no grace) ..."
sleep 20
kubectl -n "$NS" delete pod "$pod" --grace-period=0 --force
echo "Watch: Jobs page — the job returns to 'queued' after its lease expires, then succeeds."
echo "Check fences: kubectl -n $NS exec deploy/api -- python -c \"...\" or Grafana 'Workers & Jobs'."
