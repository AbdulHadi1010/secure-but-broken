"""Worker fleet (D-027): identical on-demand VMs from one validated image, pulling chains from an SQS queue.

enqueue  : expand a design (cases x models x conditions x repeats) into one SQS message per chain, and write the
           batch manifest to S3 so completeness can be checked later (no chain may silently go missing)
qualify  : before taking jobs, a worker runs the gold known-answer attempt; it must be SAFE_FIX within the band,
           otherwise the worker refuses work (guards against a slow or noisy host)
work     : take one chain at a time, run it, delete the message; stop the instance when the queue stays empty
"""

from __future__ import annotations

import itertools
import json
import subprocess
import time
import urllib.request
from datetime import datetime, timezone

import boto3

from harness.artifacts import BUCKET
from harness.cases import CASES
from harness.deploy import kind
from harness.gold import build, harden
from harness.orchestrate.attempt import active_baseline, run_attempt
from harness.orchestrate.loop import CONDITIONS, run_chain

REGION = "us-east-1"
QUEUE_NAME = "sbb-jobs"


def _session():
    return boto3.Session(region_name=REGION)


def queue_url() -> str:
    return _session().client("sqs").get_queue_url(QueueName=QUEUE_NAME)["QueueUrl"]


def enqueue(batch: str, cases: list[str], models: list[str], conditions: list[str], repeats: int,
            keep_working: bool = False) -> dict:
    for c in conditions:
        if c not in CONDITIONS:
            raise ValueError(f"unknown condition {c}")
    for c in cases:
        if not (CASES / c / "validation.json").exists() or not json.loads(
                (CASES / c / "validation.json").read_text(encoding="utf-8"))["valid"]:
            raise ValueError(f"case {c} is not validated")
    jobs = [{"batch": batch, "case": c, "model": m, "condition": k, "repeat": r, "keep_working": keep_working}
            for c, m, k, r in itertools.product(cases, models, conditions, range(1, repeats + 1))]
    manifest = {"batch": batch, "created": datetime.now(timezone.utc).isoformat(), "n_jobs": len(jobs),
                "baseline": active_baseline().name, "jobs": jobs}
    s3 = _session().client("s3")
    s3.put_object(Bucket=BUCKET, Key=f"batches/{batch}/manifest.json", Body=json.dumps(manifest, indent=1).encode(),
                  ContentType="application/json")
    sqs, url = _session().client("sqs"), queue_url()
    for i in range(0, len(jobs), 10):
        sqs.send_message_batch(QueueUrl=url, Entries=[{"Id": str(j), "MessageBody": json.dumps(job)}
                                                      for j, job in enumerate(jobs[i:i + 10])])
    return {"batch": batch, "n_jobs": len(jobs), "manifest": f"s3://{BUCKET}/batches/{batch}/manifest.json"}


def _instance_id() -> str:
    tok = urllib.request.urlopen(urllib.request.Request(
        "http://169.254.169.254/latest/api/token", method="PUT",
        headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"}), timeout=2).read().decode()
    return urllib.request.urlopen(urllib.request.Request(
        "http://169.254.169.254/latest/meta-data/instance-id", headers={"X-aws-ec2-metadata-token": tok}),
        timeout=2).read().decode()


def qualify(worker: str) -> dict:
    """Gold as the repair of a case must be SAFE_FIX on this host (all gates, inside the L6 band)."""
    meta = json.loads((CASES / "privileged-frontend" / "meta.json").read_text(encoding="utf-8"))
    out = kind.ROOT / "runs" / "qualification" / f"{worker}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    rec = run_attempt(harden(build()), meta, out)
    result = {"worker": worker, "verdict": rec["verdict"], "gates": rec["gates"], "load": rec.get("load"),
              "baseline": active_baseline().name, "qualified": rec["verdict"] == "SAFE_FIX"}
    _session().client("s3").put_object(Bucket=BUCKET, Key=f"workers/{worker}/{out.name}.json",
                                       Body=json.dumps(result, indent=1, default=str).encode())
    return result


def work(max_idle_s: int = 900, stop_when_idle: bool = True) -> dict:
    worker = _instance_id()
    q = qualify(worker)
    if not q["qualified"]:
        return {"worker": worker, "qualified": False, "qualification": q}
    sqs, url, done, idle_since = _session().client("sqs"), queue_url(), 0, time.time()
    while True:
        msgs = sqs.receive_message(QueueUrl=url, MaxNumberOfMessages=1, WaitTimeSeconds=20).get("Messages", [])
        if not msgs:
            if time.time() - idle_since > max_idle_s:
                break
            continue
        m = msgs[0]
        job = json.loads(m["Body"])
        run_chain(job["case"], job["model"], job["condition"], job["repeat"], job.get("keep_working", False),
                  batch=job["batch"], worker=worker)
        sqs.delete_message(QueueUrl=url, ReceiptHandle=m["ReceiptHandle"])
        done += 1
        idle_since = time.time()
    if stop_when_idle:
        subprocess.run(["sudo", "shutdown", "-h", "+1"], check=False)  # instance_initiated_shutdown_behavior=stop
    return {"worker": worker, "qualified": True, "chains_done": done}


def completeness(batch: str) -> dict:
    """Which planned chains of a batch have a finished summary in S3 (from the batch manifest)."""
    s3 = _session().client("s3")
    manifest = json.loads(s3.get_object(Bucket=BUCKET, Key=f"batches/{batch}/manifest.json")["Body"].read())
    done = set()
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=f"batches/{batch}/done/"):
        for o in page.get("Contents", []):
            done.add(o["Key"].rsplit("/", 1)[-1].removesuffix(".json"))
    key = lambda j: f"{j['case']}__{j['model']}__{j['condition']}__r{j['repeat']}"  # noqa: E731
    missing = [j for j in manifest["jobs"] if key(j) not in done]
    return {"batch": batch, "planned": manifest["n_jobs"], "done": manifest["n_jobs"] - len(missing),
            "missing": missing[:20]}

