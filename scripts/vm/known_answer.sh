#!/usr/bin/env bash
# Run all known-answer tests on the measurement VM from a clean result file, then upload.
# Run from the repo root on the VM:  bash scripts/vm/known_answer.sh <label>
set -uo pipefail
label="${1:-known-answer}"
bucket="sbb-artifacts-<AWS_ACCOUNT_ID>"
result="scripts/trials/2026-10-04_p3_known_answer_tests.result.json"
rm -f "$result"                      # never merge with results of an earlier run
rm -rf runs/known-answer
uv run python scripts/trials/2026-10-04_p3_known_answer_tests.py > "/tmp/${label}.log" 2>&1
aws s3 cp "$result" "s3://${bucket}/vm-results/${label}/known-answer.result.json" --only-show-errors
aws s3 cp "/tmp/${label}.log" "s3://${bucket}/vm-results/${label}/console.log" --only-show-errors
aws s3 sync runs/known-answer "s3://${bucket}/vm-results/${label}/attempts/" --only-show-errors
uv run python -c "
import json; s = json.load(open('$result'))
for k, v in s.items(): print(k.ljust(34), v['expected'].ljust(14), v['got'].ljust(14), v['ok'])
print('correct:', sum(v['ok'] for v in s.values()), 'of', len(s))"
