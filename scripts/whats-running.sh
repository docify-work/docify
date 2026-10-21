#!/usr/bin/env bash
# =============================================================================
# "What is costing money right now?" - scan ALL enabled regions (§19.3, R12).
#
# Lists: running EC2 instances, EKS clusters, NAT gateways, load balancers
# (ALB/NLB + classic), unattached Elastic IPs, unattached EBS volumes,
# RDS instances/clusters, Lambda function URLs.
#
# Usage: scripts/whats-running.sh [--strict] [--regions "ap-south-1 us-east-1"]
#   --strict   exit 1 if anything other than the expected Docify Lambda URLs is found
# Expected while asleep: nothing except docify-*-webhook-ingest function URLs
# (the server's EBS volumes stay attached to the stopped instance, so they are
# not listed as unattached).
# Needs: aws cli v2 (read-only permissions are enough).
# =============================================================================
set -euo pipefail

STRICT=false
REGIONS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --strict) STRICT=true; shift ;;
    --regions) REGIONS="$2"; shift 2 ;;
    -h | --help) sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

command -v aws >/dev/null || { echo "aws cli not found" >&2; exit 2; }

if [ -z "$REGIONS" ]; then
  REGIONS="$(aws ec2 describe-regions --region us-east-1 --query 'Regions[].RegionName' --output text)"
fi

FINDINGS=0
EXPECTED=0

# report <region> <kind> <lines...>
report() {
  local region="$1" kind="$2" lines="$3"
  [ -z "$lines" ] && return 0
  [ "$lines" = "None" ] && return 0
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    printf '%-15s %-22s %s\n' "$region" "$kind" "$line"
    FINDINGS=$((FINDINGS + 1))
  done <<<"$lines"
}

q() { aws "$@" --output text 2>/dev/null || true; }
# q1: single-column lists come back tab-separated on one line -> one per line
q1() { q "$@" | tr '\t' '\n'; }

printf '%-15s %-22s %s\n' "REGION" "RESOURCE" "DETAILS"
printf '%-15s %-22s %s\n' "------" "--------" "-------"

for r in $REGIONS; do
  # JMESPath backticks are literal on purpose (not shell expansions).
  # shellcheck disable=SC2016
  report "$r" "EC2 running" "$(q ec2 describe-instances --region "$r" \
    --filters Name=instance-state-name,Values=pending,running \
    --query 'Reservations[].Instances[].[InstanceId,InstanceType,Tags[?Key==`Name`]|[0].Value]')"

  report "$r" "EKS cluster" "$(q1 eks list-clusters --region "$r" --query 'clusters[]')"

  report "$r" "NAT gateway" "$(q ec2 describe-nat-gateways --region "$r" \
    --filter Name=state,Values=pending,available \
    --query 'NatGateways[].[NatGatewayId,VpcId]')"

  report "$r" "Load balancer" "$(q elbv2 describe-load-balancers --region "$r" \
    --query 'LoadBalancers[].[LoadBalancerName,Type]')"

  report "$r" "Classic ELB" "$(q1 elb describe-load-balancers --region "$r" \
    --query 'LoadBalancerDescriptions[].LoadBalancerName')"

  report "$r" "EIP unattached" "$(q ec2 describe-addresses --region "$r" \
    --query 'Addresses[?AssociationId==null].[PublicIp,AllocationId]')"

  report "$r" "EBS unattached" "$(q ec2 describe-volumes --region "$r" \
    --filters Name=status,Values=available \
    --query 'Volumes[].[VolumeId,Size,VolumeType]')"

  report "$r" "RDS instance" "$(q rds describe-db-instances --region "$r" \
    --query 'DBInstances[].[DBInstanceIdentifier,DBInstanceClass,DBInstanceStatus]')"

  report "$r" "RDS cluster" "$(q rds describe-db-clusters --region "$r" \
    --query 'DBClusters[].[DBClusterIdentifier,Status]')"

  # Lambda function URLs: list functions, then ask each for a URL config.
  for fn in $(q lambda list-functions --region "$r" --query 'Functions[].FunctionName'); do
    [ "$fn" = "None" ] && continue
    url="$(q lambda list-function-url-configs --region "$r" --function-name "$fn" --query 'FunctionUrlConfigs[].FunctionUrl')"
    if [ -n "$url" ] && [ "$url" != "None" ]; then
      case "$fn" in
        docify-*-webhook-ingest) EXPECTED=$((EXPECTED + 1)); label="Lambda URL (expected)" ;;
        *) label="Lambda URL" ;;
      esac
      report "$r" "$label" "$fn $url"
    fi
  done
done

UNEXPECTED=$((FINDINGS - EXPECTED))
echo
echo "Found $FINDINGS item(s): $EXPECTED expected Docify webhook URL(s), $UNEXPECTED other."
if [ "$UNEXPECTED" -eq 0 ]; then
  echo "CLEAN - nothing unexpected is running."
fi
if $STRICT && [ "$UNEXPECTED" -gt 0 ]; then
  exit 1
fi
