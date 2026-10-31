"""P8 replay (docs/p8-plan.md, D-038): deploy the final repair of sampled P7 chains on EKS with the unchanged harness.

Runs on the measurement VM with SBB_PLATFORM=eks, SBB_KUBE_CONTEXT=<EKS context>, SBB_BASELINE=<EKS baseline label>.
  uv run python scripts/p8/replay.py sample            # write the sample (deterministic) to scripts/p8/sample.json
  uv run python scripts/p8/replay.py run <label>       # replay every sampled chain not yet done; results to S3
Resumable: a replay whose result already exists under s3://.../p8/<label>/<run_id>/attempt.json is skipped.
"""

from __future__ import annotations

import csv
import json
import os
import random
import sys
from pathlib import Path

import boto3
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "harness" / "src"))
from harness.orchestrate.attempt import run_attempt  # noqa: E402

CSV = ROOT / "analysis/out/p7-20261014-W0-std-p7-20261014-W0-netpol-p7-20261014-W1-std-p7-20261014-W1-netpol-chains.csv"
SAMPLE = Path(__file__).with_name("sample.json")
BUCKET = "sbb-artifacts-<AWS_ACCOUNT_ID>"
SEED = 20261017
TYPES = ["privileged", "allow-privilege-escalation", "added-capabilities", "run-as-root", "missing-limits", "netpol"]
NON_SAFE = ("BREAKING_FIX", "DECEPTIVE_FIX", "BREAKING_AND_DECEPTIVE")
s3 = boto3.Session(region_name="us-east-1").client("s3")


def make_sample() -> list[dict]:
    rows = sorted(csv.DictReader(CSV.open(encoding="utf-8")), key=lambda r: r["run_id"])
    rng = random.Random(SEED)
    pick = rng.sample([r for r in rows if r["final_verdict"] in NON_SAFE], 40)
    for t in TYPES:
        pick += rng.sample([r for r in rows if r["final_verdict"] == "SAFE_FIX" and r["case"].startswith(t + "-")], 8)
    rng.shuffle(pick)
    out = [{k: r[k] for k in ("run_id", "case", "model", "condition", "wording", "repeat", "n_iterations",
                              "final_verdict")} for r in pick]
    SAMPLE.write_text(json.dumps(out, indent=1), encoding="utf-8", newline="\n")
    return out


def done(label: str, run_id: str) -> bool:
    try:
        s3.head_object(Bucket=BUCKET, Key=f"p8/{label}/{run_id}/attempt.json")
        return True
    except s3.exceptions.ClientError:
        return False


def replay(label: str) -> None:
    assert os.environ.get("SBB_PLATFORM") == "eks" and os.environ.get("SBB_BASELINE"), "set SBB_PLATFORM=eks and SBB_BASELINE"
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    for i, s in enumerate(sample, 1):
        if done(label, s["run_id"]):
            continue
        key = f"chains/{s['run_id']}/iter-{s['n_iterations']}/repair.yaml"
        docs = [d for d in yaml.safe_load_all(s3.get_object(Bucket=BUCKET, Key=key)["Body"].read().decode("utf-8")) if d]
        meta = json.loads((ROOT / "cases" / s["case"] / "meta.json").read_text(encoding="utf-8"))
        out = ROOT / "runs" / "p8" / label / s["run_id"]
        for attempt_no in (1, 2):  # one re-run only for infrastructure failures (plan: not a disagreement)
            try:
                rec = run_attempt(docs, meta, out)
                break
            except Exception as e:  # noqa: BLE001 - recorded
                (out / f"infra-error-{attempt_no}.txt").write_text(repr(e)[:4000], encoding="utf-8")
                if attempt_no == 2:
                    raise
        rec["p8"] = {"kind_verdict": s["final_verdict"], "source_run_id": s["run_id"], "source_key": key,
                     "baseline": os.environ["SBB_BASELINE"], "git_commit": os.environ.get("SBB_GIT_COMMIT")}
        (out / "attempt.json").write_text(json.dumps(rec, indent=1), encoding="utf-8", newline="\n")
        for f in out.iterdir():
            s3.upload_file(str(f), BUCKET, f"p8/{label}/{s['run_id']}/{f.name}")
        print(f"{i}/{len(sample)} {s['case']} kind={s['final_verdict']} eks={rec['verdict']}", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "sample":
        print(len(make_sample()))
    else:
        replay(sys.argv[2])
