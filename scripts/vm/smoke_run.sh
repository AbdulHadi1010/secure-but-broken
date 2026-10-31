#!/usr/bin/env bash
# Exploratory smoke run (D-025): one model, C0, one case per type. NOT counted in the analysis; cases are not
# changed in response to its results. Run from the repo root on the VM:  bash scripts/vm/smoke_run.sh <model-key>
set -uo pipefail
model="${1:-deepseek-v3-2}"
log="/tmp/smoke-${model}.log"
: > "$log"
for case_id in allow-privilege-escalation-checkoutservice added-capabilities-cartservice run-as-root-frontend \
               missing-limits-cartservice netpol-cartservice privileged-checkoutservice; do
  echo "=== ${case_id} $(date -Is)" >> "$log"
  uv run harness run-one --case "$case_id" --model "$model" --condition C0 >> "$log" 2>&1
done
aws s3 cp "$log" "s3://sbb-artifacts-<AWS_ACCOUNT_ID>/vm-results/smoke-${model}.log" --only-show-errors
grep -E '^=== |"final_verdict"|"run_id"' "$log"
