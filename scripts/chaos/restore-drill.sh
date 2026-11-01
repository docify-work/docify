#!/usr/bin/env bash
# Restore drill (P13, runbook R7, then every 3 months): restore the LATEST S3 backup into a throwaway
# Postgres in namespace restore-drill, migrate it to head (like a real R7 restore: the backup can be
# older than the running code), run `docify verify-db` against each restored env DB, compare row
# counts with live, print the elapsed time (RTO target < 30 min). Live data is never touched.
# Runs ON the server (kubectl + instance role):
#   aws ssm start-session ...  then  sudo bash scripts/chaos/restore-drill.sh
# or pipe it through `aws ssm send-command` (see docs/incidents/*restore-drill*.md).
set -euo pipefail
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"
NS=restore-drill
start=$(date +%s)
t() { echo "[$(( $(date +%s) - start ))s] $*"; }

bucket=$(kubectl -n data get cronjob pg-backup -o jsonpath='{.spec.jobTemplate.spec.template.spec.containers[0].env[?(@.name=="BUCKET")].value}')
pg_image=$(kubectl -n data get statefulset postgres -o jsonpath='{.spec.template.spec.containers[0].image}')
app_image=$(kubectl -n docify-prod get deploy api -o jsonpath='{.spec.template.spec.containers[0].image}')
key=$(aws s3api list-objects-v2 --bucket "$bucket" --prefix postgres/ --query 'sort_by(Contents,&LastModified)[-1].Key' --output text)
[ "$key" != "None" ] || { echo "no backup found in s3://$bucket/postgres/"; exit 1; }
t "latest backup: s3://$bucket/$key"
tmp=$(mktemp -d); trap 'rm -rf "$tmp"; kubectl delete ns "$NS" --wait=false >/dev/null 2>&1 || true' EXIT
aws s3 cp "s3://$bucket/$key" "$tmp/dump.sql.gz" --only-show-errors
t "downloaded $(du -h "$tmp/dump.sql.gz" | cut -f1)"

pw=$(head -c 18 /dev/urandom | base64 | tr -dc 'A-Za-z0-9')
kubectl create ns "$NS" >/dev/null
kubectl -n "$NS" run pg --image="$pg_image" --restart=Never --port=5432 \
  --env=POSTGRES_PASSWORD="$pw" --labels=app=pg >/dev/null
kubectl -n "$NS" expose pod pg --port=5432 >/dev/null
kubectl -n "$NS" wait --for=condition=Ready pod/pg --timeout=180s >/dev/null
until kubectl -n "$NS" exec pg -- pg_isready -q -U postgres 2>/dev/null; do sleep 2; done
t "scratch postgres ready ($pg_image)"

kubectl -n "$NS" cp "$tmp/dump.sql.gz" pg:/tmp/dump.sql.gz
# pg_dumpall output re-creates roles (the existing postgres role errors harmlessly) and every DB.
kubectl -n "$NS" exec pg -- bash -c 'gunzip -c /tmp/dump.sql.gz | psql -q -U postgres -d postgres -v ON_ERROR_STOP=0' \
  > "$tmp/restore.log" 2>&1 || true
t "restored ($(grep -c ERROR "$tmp/restore.log" || true) psql errors - expected: role \"postgres\" already exists)"
# The dump also carries ALTER ROLE postgres ... PASSWORD (live hash): set the scratch password again
# (local socket = trust inside the container).
kubectl -n "$NS" exec pg -- psql -q -U postgres -d postgres -c "ALTER ROLE postgres PASSWORD '${pw}'" >/dev/null

rc=0
for env in prod staging; do
  db="docify_${env}"
  t "verify-db $db"
  kubectl -n "$NS" run "verify-$env" --image="$app_image" --restart=Never --rm -i --quiet \
    --env=DATABASE_URL="postgresql+asyncpg://postgres:${pw}@pg.${NS}.svc:5432/${db}" \
    --command -- sh -c "docify migrate >/dev/null 2>&1 && docify verify-db 2>/dev/null" || rc=1
  live=$(kubectl -n data exec postgres-0 -- psql -U postgres -d "$db" -Atc \
    "select (select count(*) from repositories)||' repos, '||(select count(*) from chunks)||' chunks, '||(select count(*) from document_versions)||' doc versions'")
  t "live $db now: $live"
done
t "RTO (download + restore + verify): $(( $(date +%s) - start ))s - target < 1800 s"
exit $rc
