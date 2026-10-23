#!/usr/bin/env bash
# P9 exit check: from a CLEAN clone of the current commit, rebuild every analysis output from S3 and compare it with
# the committed copy. Usage (Git Bash, AWS_PROFILE set): bash scripts/trials/2026-10-17_repro_check.sh <scratch dir>
set -euo pipefail
src="$(cd "$(dirname "$0")/../.." && pwd)"
dst="$1/repro-$(git -C "$src" rev-parse --short HEAD)"
rm -rf "$dst" && git clone -q "$src" "$dst" && cd "$dst"
uv sync -q --group analysis
rm -f analysis/out/p7-* analysis/out/p8-* paper/numbers.tex
(cd harness && uv run python ../analysis/pilot_summary.py p7-20261014-W0-std p7-20261014-W0-netpol p7-20261014-W1-std p7-20261014-W1-netpol > /dev/null)
(cd harness && uv run python ../analysis/p7_analysis.py > /dev/null)
uv run --group analysis python analysis/p7_regression.py > /dev/null
(cd harness && uv run python ../analysis/p8_agreement.py eks-p8-20261016 > /dev/null)
uv run python analysis/paper_numbers.py
uv run --group analysis python analysis/figures.py > /dev/null
fail=0
for f in analysis/out/p7-20261014-W0-std-p7-20261014-W0-netpol-p7-20261014-W1-std-p7-20261014-W1-netpol-chains.csv \
         analysis/out/p7-results-W0.json analysis/out/p7-results-W1.json analysis/out/p7-results-W0.md \
         analysis/out/p7-results-W1.md analysis/out/p7-results-wording.md analysis/out/p7-regression.json \
         analysis/out/p8-agreement.json paper/numbers.tex; do
  if cmp -s "$f" "$src/$f"; then echo "SAME     $f"; else echo "DIFFERENT $f"; fail=1; fi
done
for f in analysis/figures/*.png; do
  if cmp -s "$f" "$src/$f"; then echo "SAME     $f"; else echo "DIFFERENT $f (image bytes)"; fi
done
exit $fail
