#!/usr/bin/env bash
# Validate every case (V1-V4) on the measurement VM, one fresh cluster each, then upload the evidence.
# Run from the repo root on the VM:  bash scripts/vm/validate_all_cases.sh <label>
set -uo pipefail
label="${1:-vm-validation}"
bucket="sbb-artifacts-<AWS_ACCOUNT_ID>"
log="/tmp/${label}.log"
: > "$log"
for meta in cases/*/meta.json; do
  case_id="$(basename "$(dirname "$meta")")"
  echo "=== ${case_id} $(date -Is)" >> "$log"
  uv run harness case-validate "$case_id" >> "$log" 2>&1
done
aws s3 cp "$log" "s3://${bucket}/vm-results/${label}/validation.log" --only-show-errors
aws s3 sync cases "s3://${bucket}/vm-results/${label}/cases/" --exclude '*' --include '*/validation.json' --only-show-errors
echo "valid: $(grep -c '"valid": true' "$log") of $(ls cases/*/meta.json | wc -l)"
