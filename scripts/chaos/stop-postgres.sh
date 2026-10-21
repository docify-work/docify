#!/usr/bin/env bash
# Chaos 3 (P13): Postgres down for ~60 s → readiness fails, CloudFront serves 502 → the SPA shows the
# "backend sleeping" banner; workers back off; everything recovers by itself (F23).
#   scripts/chaos/stop-postgres.sh
set -euo pipefail
kubectl -n data scale statefulset/postgres --replicas=0
echo "Postgres stopped. Watch /api/ready fail and the UI banner. Restoring in 60 s ..."
sleep 60
kubectl -n data scale statefulset/postgres --replicas=1
kubectl -n data rollout status statefulset/postgres --timeout=5m
echo "Restored. Verify: smoke.sh + Grafana error rate back to 0."
