# Baseline (working band)

| Label | Platform | Runs | ok | ready s (mean/max) | restarts | L5 | error rate (max) | p95 ms (mean ± SD) | L6 thresholds |
|---|---|---|---|---|---|---|---|---|---|
| local-20261003 | kind 1.37 on laptop (WSL2, 12 CPU, 15 GB to Docker) | 5 | 5 | 37.6 / 41.0 | 0 | 100% all runs | 0.0 | 177.5 ± 24.5 | p95 ≤ 251.2 ms; error rate ≤ 1.0% |

Per-run p95 (ms): 135.6, 181.3, 182.3, 189.4, 199.2. Gold sha256 08aa0fee…, commit e63f9ac. Raw files: `runs/baseline/local-20261003/` (S3 `baseline/local-20261003/`).
Rule: docs/protocol.md "Working band" (D-013), fixed before these numbers existed.
Note: p95 rose run over run (r1 lowest). Watch for drift; see journal.
