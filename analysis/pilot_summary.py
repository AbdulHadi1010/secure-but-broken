"""P6 pilot summary (descriptive only; pilot chains are excluded from the main analysis, protocol "Pilot (P6) design").

Reads every chain of the given batches from S3 (batch manifest -> done markers -> chains/<run_id>/summary.json),
writes one row per chain to analysis/out/<label>-chains.csv and prints:
  - final verdicts per model x condition x wording
  - iterations, tokens, cost (repairer + moderator) and wall time per chain
  - repeat agreement: share of cells (case x model x condition x wording) whose 3 repeats reach the same verdict
Usage: uv run python analysis/pilot_summary.py pilot-20261006-W0 pilot-20261006-W1
"""

from __future__ import annotations

import csv
import json
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ConnectionError as BotoConnectionError, ReadTimeoutError

BUCKET = "sbb-artifacts-<AWS_ACCOUNT_ID>"
OUT = Path(__file__).resolve().parent / "out"


def _get(s3, key: str) -> dict:
    """Read one JSON object; a network timeout while reading the body is retried (botocore does not retry it)."""
    for attempt in range(5):
        try:
            return json.loads(s3.get_object(Bucket=BUCKET, Key=key)["Body"].read())
        except (ReadTimeoutError, BotoConnectionError):
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)


def chains(s3, batch: str) -> list[dict]:
    manifest = _get(s3, f"batches/{batch}/manifest.json")
    with ThreadPoolExecutor(max_workers=16) as pool:  # map keeps the manifest order, so the table is unchanged
        return list(pool.map(lambda j: _row(s3, batch, j), manifest["jobs"]))


def _row(s3, batch: str, j: dict) -> dict:
    key = f"batches/{batch}/done/{j['case']}__{j['model']}__{j['condition']}__r{j['repeat']}.json"
    try:
        run_id = _get(s3, key)["run_id"]
    except s3.exceptions.NoSuchKey:
        return {**j, "wording": "W1" if j.get("keep_working") else "W0", "final_verdict": "MISSING"}
    s = _get(s3, f"chains/{run_id}/summary.json")
    its = s["iterations"]
    mod = [u for it in its for u in (it.get("moderator_usage") or [])]
    return {
        "batch": batch, "run_id": run_id, "case": s["case_id"], "fix_class": s["fix_class"],
        "model": s["model_key"], "condition": s["condition"], "repeat": s["repeat"],
        "wording": "W1" if s["keep_working_wording"] else "W0", "git_commit": s["git_commit"],
        "worker": s.get("worker"), "final_verdict": s["final_verdict"], "n_iterations": s["n_iterations"],
        "first_verdict": its[0]["verdict"],
        "repairer_tokens_in": sum(it["tokens_in"] or 0 for it in its),
        "repairer_tokens_out": sum(it["tokens_out"] or 0 for it in its),
        "repairer_cost_usd": round(sum(it.get("cost_usd") or 0 for it in its), 6),
        "moderator_calls": len(mod),
        "moderator_cost_usd": round(sum(u.get("cost_usd") or 0 for u in mod), 6),
        "llm_wall_s": round(sum(it["llm_wall_s"] or 0 for it in its), 1),
        "attempt_wall_s": round(sum(it.get("attempt_wallclock_s") or 0 for it in its), 1),
        "feedback_sources": ";".join(it.get("feedback_source") or "" for it in its[:-1]),
    }


def main(batches: list[str]) -> None:
    s3 = boto3.Session(region_name="us-east-1").client(
        "s3", config=Config(max_pool_connections=32, retries={"max_attempts": 8, "mode": "standard"}, read_timeout=60))
    rows = [r for b in batches for r in chains(s3, b)]
    OUT.mkdir(exist_ok=True)
    label = "-".join(batches)
    path = OUT / f"{label}-chains.csv"
    fields = sorted({k for r in rows for k in r})
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    done = [r for r in rows if r["final_verdict"] != "MISSING"]
    print(f"chains: {len(done)} done / {len(rows)} planned -> {path}")

    print("\nFinal verdict by model x condition x wording")
    groups = defaultdict(Counter)
    for r in done:
        groups[(r["model"], r["condition"], r["wording"])][r["final_verdict"]] += 1
    for k in sorted(groups):
        print(f"  {k[0]:8} {k[1]:12} {k[2]}  " + ", ".join(f"{v}={n}" for v, n in groups[k].most_common()))

    print("\nPer chain, by model (mean / max)")
    for m in sorted({r["model"] for r in done}):
        rs = [r for r in done if r["model"] == m]
        for f in ("n_iterations", "repairer_tokens_in", "repairer_tokens_out", "repairer_cost_usd",
                  "moderator_cost_usd", "llm_wall_s", "attempt_wall_s"):
            vals = [r[f] for r in rs]
            print(f"  {m:8} {f:20} {sum(vals) / len(vals):10.3f} {max(vals):10.3f}")
        print(f"  {m:8} total cost USD      {sum(r['repairer_cost_usd'] + r['moderator_cost_usd'] for r in rs):10.2f}")

    print("\nRepeat agreement (cells whose repeats all reach the same final verdict)")
    cells = defaultdict(list)
    for r in done:
        cells[(r["case"], r["model"], r["condition"], r["wording"])].append(r["final_verdict"])
    full = {k: v for k, v in cells.items() if len(v) == 3}
    agree = [k for k, v in full.items() if len(set(v)) == 1]
    print(f"  {len(agree)}/{len(full)} complete cells agree")
    for k, v in sorted(full.items()):
        if len(set(v)) > 1:
            print(f"  disagree: {k}: {v}")


if __name__ == "__main__":
    main(sys.argv[1:])
