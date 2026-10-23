#!/usr/bin/env bash
# Watch the P7 batches from the laptop (read-only). Prints one line every INTERVAL seconds and exits when
# something needs attention: a job in the DLQ, fewer workers running than at start, all chains done,
# or the AWS login expired (status lines show '?').  Usage: bash scripts/vm/watch_p7.sh [interval_s]
set -u
export AWS_PROFILE=secure-but-broken
INTERVAL="${1:-1200}"
IDS="i-0f071573463a5a2e5 i-06d8ae62f07a357e8 i-0e97b3a8c1758f16e i-060c0e3ad90a43fde"
BATCHES="p7-20261014-W0-std p7-20261014-W0-netpol p7-20261014-W1-std p7-20261014-W1-netpol"
cd "$(dirname "$0")/../../harness"
PY=../.venv/Scripts/python.exe
DLQ=$(aws sqs get-queue-url --queue-name sbb-jobs-dlq --query QueueUrl --output text)
start_running=$(aws ec2 describe-instances --instance-ids $IDS --query "length(Reservations[].Instances[?State.Name=='running'][])" --output text)
while true; do
  sleep "$INTERVAL"
  total=0; line=""
  for b in $BATCHES; do
    d=$(uv run harness completeness "$b" 2>/dev/null | $PY -c "import json,sys;print(json.load(sys.stdin)['done'])" 2>/dev/null || echo "?")
    line="$line ${b#p7-20261014-}=$d"
    [ "$d" != "?" ] && total=$((total + d))
  done
  dl=$(aws sqs get-queue-attributes --queue-url "$DLQ" --attribute-names ApproximateNumberOfMessages --query Attributes.ApproximateNumberOfMessages --output text 2>/dev/null || echo "?")
  run=$(aws ec2 describe-instances --instance-ids $IDS --query "length(Reservations[].Instances[?State.Name=='running'][])" --output text 2>/dev/null || echo "?")
  echo "$(date +%m-%d_%H:%M) total=$total/1440$line dlq=$dl running=$run"
  [ "$dl" = "?" ] || [ "$run" = "?" ] && { echo "STOP: AWS login expired"; exit 0; }
  [ "$dl" != "0" ] && { echo "STOP: job(s) in DLQ"; exit 0; }
  [ "$total" -ge 1440 ] && { echo "STOP: all done"; exit 0; }
  [ "$run" -lt "$start_running" ] && { echo "STOP: a worker stopped (running=$run, was $start_running)"; exit 0; }
done
