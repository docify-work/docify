#!/usr/bin/env bash
# P11 burst generator: N synthetic `loadtest` messages -> KEDA scales the worker 0 -> max -> 0.
# Simulated work only (sleep), so it costs $0 in AI/GitHub calls. Needs LOADTEST_MESSAGES=true (set in
# deploy/values/{staging,prod}.yaml) and AWS credentials that may send to the queue.
#   scripts/load/burst.sh prod 500 3000      # env, messages, work per message (ms)
set -euo pipefail
ENV_NAME="${1:-staging}"; COUNT="${2:-500}"; WORK_MS="${3:-3000}"
PROFILE="${AWS_PROFILE:-docify}"; REGION="${AWS_REGION:-ap-south-1}"
URL=$(aws sqs get-queue-url --profile "$PROFILE" --region "$REGION" --queue-name "docify-${ENV_NAME}-events" \
      --query QueueUrl --output text)
echo "sending $COUNT loadtest messages (${WORK_MS} ms each) to docify-${ENV_NAME}-events"
sent=0
while [ "$sent" -lt "$COUNT" ]; do
  n=$(( COUNT - sent < 10 ? COUNT - sent : 10 ))
  entries=""
  for i in $(seq 1 "$n"); do
    entries+="{\"Id\":\"m$i\",\"MessageBody\":\"{\\\"v\\\":1,\\\"kind\\\":\\\"loadtest\\\",\\\"work_ms\\\":${WORK_MS}}\"},"
  done
  aws sqs send-message-batch --profile "$PROFILE" --region "$REGION" --queue-url "$URL" \
      --entries "[${entries%,}]" --query 'Failed[].Id' --output text | grep -v '^None$' && echo 'some messages failed' >&2 || true
  sent=$(( sent + n ))
done
echo "sent $sent. Watch: kubectl -n docify-${ENV_NAME} get deploy worker -w   (KEDA polls every 30 s)"
