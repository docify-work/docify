#!/usr/bin/env bash
# =============================================================================
# Smoke test a deployed environment through CloudFront (Master Doc §14.4).
#
# Usage:   scripts/smoke.sh <base-url> <sha> [env]
# Example: scripts/smoke.sh https://staging.docify.work 3f2a9c1... staging
#
# env defaults to "staging" if the host starts with "staging.", else "prod".
# Prints PASS/FAIL per check; exits 1 if any check fails.
# Needs: curl, jq.
# =============================================================================
set -uo pipefail

if [ $# -lt 2 ]; then
  echo "usage: $0 <base-url> <sha> [env]" >&2
  exit 2
fi

BASE_URL="${1%/}"
SHA="$2"
HOST="${BASE_URL#*://}"
HOST="${HOST%%/*}"
if [ $# -ge 3 ]; then
  EXPECTED_ENV="$3"
elif [[ "$HOST" == staging.* ]]; then
  EXPECTED_ENV="staging"
else
  EXPECTED_ENV="prod"
fi

for tool in curl jq; do
  command -v "$tool" >/dev/null 2>&1 || {
    echo "missing tool: $tool" >&2
    exit 2
  }
done

CURL=(curl -sS --max-time 15 --retry 2 --retry-delay 2 --retry-all-errors)
BODY_FILE="$(mktemp)"
trap 'rm -f "$BODY_FILE"' EXIT

PASSED=0
FAILED=0

pass() {
  echo "PASS  $1"
  PASSED=$((PASSED + 1))
}
fail() {
  echo "FAIL  $1${2:+  ($2)}"
  FAILED=$((FAILED + 1))
}

# fetch <path> -> sets STATUS, body in $BODY_FILE
fetch() {
  STATUS="$("${CURL[@]}" -o "$BODY_FILE" -w '%{http_code}' "$BASE_URL$1" 2>/dev/null)" || STATUS="000"
}

# Extract a sha from /api/version: accept JSON {"sha": ...}/{"version": ...}/{"git_sha": ...} or plain text.
version_sha() {
  jq -r '.sha // .git_sha // .commit // .version // empty' "$BODY_FILE" 2>/dev/null ||
    tr -d '[:space:]"' <"$BODY_FILE"
}

echo "Smoke test: $BASE_URL  sha=$SHA  env=$EXPECTED_ENV"
echo "---------------------------------------------------------------"

# 1. liveness
fetch /api/health
if [ "$STATUS" = "200" ]; then pass "GET /api/health -> 200"; else fail "GET /api/health -> 200" "got $STATUS"; fi

# 2. the expected backend version is live
fetch /api/version
if [ "$STATUS" = "200" ]; then
  GOT="$(version_sha)"
  if [ "$GOT" = "$SHA" ]; then pass "GET /api/version == $SHA"; else fail "GET /api/version == $SHA" "got '$GOT'"; fi
else
  fail "GET /api/version == $SHA" "HTTP $STATUS"
fi

# 3. the SPA is served
fetch /
if [ "$STATUS" = "200" ] && grep -q '<title>Docify' "$BODY_FILE"; then
  pass "GET / contains <title>Docify"
else
  fail "GET / contains <title>Docify" "HTTP $STATUS"
fi

# 4. runtime config matches the environment
fetch /config.json
if [ "$STATUS" = "200" ]; then
  GOT_ENV="$(jq -r '.env // empty' "$BODY_FILE" 2>/dev/null)"
  if [ "$GOT_ENV" = "$EXPECTED_ENV" ]; then pass "GET /config.json env == $EXPECTED_ENV"; else fail "GET /config.json env == $EXPECTED_ENV" "got '$GOT_ENV'"; fi
else
  fail "GET /config.json env == $EXPECTED_ENV" "HTTP $STATUS"
fi

# 5. public demo endpoint
fetch /api/demo
if [ "$STATUS" = "200" ]; then pass "GET /api/demo -> 200"; else fail "GET /api/demo -> 200" "got $STATUS"; fi

# 6. auth is enforced
fetch /api/me
if [ "$STATUS" = "401" ]; then pass "GET /api/me (anonymous) -> 401"; else fail "GET /api/me (anonymous) -> 401" "got $STATUS"; fi

# 7. readiness endpoint is internal-only (404 when X-Origin-Verify is present, §4.2)
fetch /api/ready
if [ "$STATUS" = "404" ]; then pass "GET /api/ready via CloudFront -> 404"; else fail "GET /api/ready via CloudFront -> 404" "got $STATUS"; fi

echo "---------------------------------------------------------------"
echo "Result: $PASSED passed, $FAILED failed"
[ "$FAILED" -eq 0 ]
