#!/usr/bin/env bash
# P4 exit check (exploratory, D-025/D-026): the feedback loops on one case, one model. NOT counted in the analysis.
# Run from the repo root on the VM:  bash scripts/vm/loop_check.sh <case> <model-key>
set -uo pipefail
case_id="${1:-netpol-cartservice}"
model="${2:-deepseek-v3-2}"
log="/tmp/loopcheck-${case_id}-${model}.log"
: > "$log"
for cond in C1 C2-template C2-LLM; do
  echo "=== ${cond} $(date -Is)" >> "$log"
  uv run harness run-one --case "$case_id" --model "$model" --condition "$cond" >> "$log" 2>&1
done
aws s3 cp "$log" "s3://sbb-artifacts-<AWS_ACCOUNT_ID>/vm-results/loopcheck-${case_id}-${model}.log" --only-show-errors
grep -E '^=== |"final_verdict"|"n_iterations"|"run_id"' "$log"
