"""Run a k6 script as an in-cluster Job and parse its summary (used by L5 functional and L6 load)."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from harness.deploy.kind import ROOT, kubectl

K6_IMAGE = "grafana/k6:2.3.0@sha256:9c2dee7f8ed74d317e4027c06a10f169b625638189de8d4555d0b3486a5aeb34"
K6_DIR = ROOT / "loadtest" / "k6"
NS = "loadtest"
BASE_URL = "http://frontend.boutique.svc.cluster.local"


def _objects(job: str, script: str) -> list[dict]:
    files = {p.name: p.read_text(encoding="utf-8") for p in K6_DIR.glob("*.js")}
    return [
        {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": NS}},
        {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": f"{job}-scripts", "namespace": NS}, "data": files},
        {
            "apiVersion": "batch/v1", "kind": "Job", "metadata": {"name": job, "namespace": NS},
            "spec": {
                "backoffLimit": 0,
                "template": {"spec": {
                    "restartPolicy": "Never",
                    "containers": [{
                        "name": "k6", "image": K6_IMAGE,
                        "args": ["run", "--quiet", "-e", f"BASE_URL={BASE_URL}", f"/scripts/{script}"],
                        "volumeMounts": [{"name": "scripts", "mountPath": "/scripts"}],
                    }],
                    "volumes": [{"name": "scripts", "configMap": {"name": f"{job}-scripts"}}],
                }},
            },
        },
    ]


def parse_summary(log: str) -> dict:
    start, end = "===K6_SUMMARY_BEGIN===", "===K6_SUMMARY_END==="
    if start not in log or end not in log:
        raise ValueError("k6 summary markers not found in job log")
    return json.loads(log.split(start, 1)[1].split(end, 1)[0])


def run_job(ctx: str, job: str, script: str, timeout_s: int) -> dict:
    manifest = yaml.safe_dump_all(_objects(job, script), sort_keys=False)
    kubectl(ctx, "apply", "-f", "-", input=manifest)
    kubectl(ctx, "-n", NS, "wait", f"job/{job}", "--for=condition=Complete", f"--timeout={timeout_s}s", check=False,
            timeout=timeout_s + 60)
    log = kubectl(ctx, "-n", NS, "logs", f"job/{job}", "--tail=-1").stdout
    return parse_summary(log)


def _metric(summary: dict, name: str) -> dict:
    m = summary["metrics"].get(name, {})
    return m.get("values", m)  # k6 summary JSON keeps values under "values"


def functional_result(summary: dict) -> dict:
    checks = {}
    for g in [summary["root_group"], *summary["root_group"].get("groups", [])]:
        for c in g.get("checks", []):
            checks[c["name"]] = {"passes": c["passes"], "fails": c["fails"]}
    total = sum(v["passes"] + v["fails"] for v in checks.values())
    passed = sum(v["passes"] for v in checks.values())
    return {"checks": checks, "pass_rate": passed / total if total else 0.0}


EMAIL_OK = "order confirmation email sent to"  # upstream checkoutservice/main.go v0.10.7, line 276
EMAIL_FAIL = "failed to send order confirmation"  # line 274


def email_check(ctx: str, since: str = "5m") -> dict:
    """emailservice failures are invisible to the frontend (checkout still succeeds), so read checkoutservice logs."""
    log = kubectl(ctx, "-n", "boutique", "logs", "deploy/checkoutservice", f"--since={since}", check=False).stdout
    ok = EMAIL_OK in log and EMAIL_FAIL not in log
    return {"passes": int(ok), "fails": int(not ok)}


def with_email_check(result: dict, email: dict) -> dict:
    checks = {**result["checks"], "checkout email sent (checkoutservice log)": email}
    total = sum(v["passes"] + v["fails"] for v in checks.values())
    return {"checks": checks, "pass_rate": sum(v["passes"] for v in checks.values()) / total if total else 0.0}


def load_result(summary: dict) -> dict:
    dur = _metric(summary, "http_req_duration{phase:main}")
    failed = _metric(summary, "http_req_failed{phase:main}")
    checks = _metric(summary, "checks{phase:main}")
    reqs = _metric(summary, "http_reqs")
    return {
        "p95_ms": dur.get("p(95)"),
        "p99_ms": dur.get("p(99)"),
        "median_ms": dur.get("med"),
        "error_rate": failed.get("rate"),
        "check_pass_rate": checks.get("rate"),
        "requests_total": reqs.get("count"),
        "rps": reqs.get("rate"),
    }
