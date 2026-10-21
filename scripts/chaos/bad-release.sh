#!/usr/bin/env bash
# Chaos 4 (P13): ship a broken image tag to staging → new pods never become ready, old pods keep
# serving (maxUnavailable 0); roll back with `git revert` of the bump commit (runbook R5).
#   scripts/chaos/bad-release.sh
set -euo pipefail
file=deploy/values/staging.yaml
cp "$file" "$file.bak"
sed -i 's/^\(  tag: \).*/\1does-not-exist/' "$file"
git add "$file" && git commit -m "chaos: deploy a non-existent image tag to staging" && git push
mv "$file.bak" "$file"
cat <<'EOF'
Pushed a bad tag. Watch Argo CD: the new ReplicaSet is stuck in ImagePullBackOff, the old pods still
serve (check /api/version). Roll back:  git revert --no-edit HEAD && git push
Time it, and write an incident note in docs/incidents/ (runbook R14).
EOF
