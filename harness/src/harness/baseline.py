"""P1 baseline: deploy the gold app N times, each on a fresh cluster, and record the working band.

Per run: create cluster -> apply gold -> wait all Deployments Available -> L5 functional -> L6 load -> delete.
Same procedure and same k6 scripts as the experiment (protocol.md, D-013).
"""

from __future__ import annotations

import hashlib
import json
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from harness.checks import k6
from harness.deploy import kind
from harness.gold import NAMESPACE, OUT as GOLD_MANIFEST

READY_TIMEOUT_S = 600


def _git_commit() -> str:
    r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=kind.ROOT)
    # tracked changes only: result files written into the tree by earlier runs must not mark the code dirty
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True,
                           cwd=kind.ROOT).stdout.strip()
    return r.stdout.strip() + ("-dirty" if dirty else "")


def run_once(run_id: str, out_dir: Path) -> dict:
    ctx = f"sbb-{run_id}"
    rec: dict = {"run_id": run_id, "started": datetime.now(timezone.utc).isoformat(), "ok": False}
    try:
        rec["cluster_create_s"] = round(kind.create_cluster(ctx), 1)
        kind.kubectl(ctx, "create", "namespace", NAMESPACE)
        t0 = time.perf_counter()
        kind.kubectl(ctx, "apply", "-f", str(GOLD_MANIFEST))
        w = kind.kubectl(ctx, "-n", NAMESPACE, "wait", "deploy", "--all", "--for=condition=Available",
                         f"--timeout={READY_TIMEOUT_S}s", check=False, timeout=READY_TIMEOUT_S + 60)
        rec["ready_s"] = round(time.perf_counter() - t0, 1)
        rec["all_available"] = w.returncode == 0
        rec["pods_after_ready"] = kind.pods(ctx, NAMESPACE)

        fsum = k6.run_job(ctx, "functional", "functional.js", timeout_s=180)
        rec["functional"] = k6.with_email_check(k6.functional_result(fsum), k6.email_check(ctx))
        lsum = k6.run_job(ctx, "load", "load.js", timeout_s=400)
        rec["load"] = k6.load_result(lsum)
        rec["pods_after_load"] = kind.pods(ctx, NAMESPACE)
        rec["restarts_total"] = sum(p["restarts"] for p in rec["pods_after_load"])
        (out_dir / f"{run_id}.k6-functional.json").write_text(json.dumps(fsum, indent=1), encoding="utf-8", newline="\n")
        (out_dir / f"{run_id}.k6-load.json").write_text(json.dumps(lsum, indent=1), encoding="utf-8", newline="\n")
        rec["ok"] = rec["all_available"] and rec["functional"]["pass_rate"] == 1.0
    except Exception as e:  # noqa: BLE001 - a failed baseline run is recorded, never dropped
        rec["error"] = f"{type(e).__name__}: {e}"[:2000]
    finally:
        rec["finished"] = datetime.now(timezone.utc).isoformat()
        kind.delete_cluster(ctx)
    (out_dir / f"{run_id}.json").write_text(json.dumps(rec, indent=1), encoding="utf-8", newline="\n")
    return rec


def band(runs: list[dict]) -> dict:
    """Working band per protocol.md D-013. Uses every run (failed runs are reported, not dropped)."""
    good = [r for r in runs if r.get("ok")]
    p95 = [r["load"]["p95_ms"] for r in good]
    err = [r["load"]["error_rate"] for r in good]
    sd = statistics.stdev(p95) if len(p95) > 1 else 0.0
    return {
        "n_runs": len(runs),
        "n_ok": len(good),
        "p95_ms": {"mean": statistics.mean(p95), "sd": sd, "min": min(p95), "max": max(p95)},
        "error_rate": {"mean": statistics.mean(err), "max": max(err)},
        "ready_s": {"mean": statistics.mean(r["ready_s"] for r in good), "max": max(r["ready_s"] for r in good)},
        "restarts_total": sum(r.get("restarts_total", 0) for r in good),
        "thresholds": {
            "p95_ms_max": statistics.mean(p95) + 3 * sd,
            "error_rate_max": max(err) + 0.01,
        },
    }


def run_baseline(n: int, label: str) -> dict:
    out_dir = kind.ROOT / "runs" / "baseline" / label
    out_dir.mkdir(parents=True, exist_ok=True)
    kind.ensure_caches()
    meta = {
        "label": label,
        "git_commit": _git_commit(),
        "gold_sha256": hashlib.sha256(GOLD_MANIFEST.read_bytes()).hexdigest(),
        "k6_image": k6.K6_IMAGE,
        "versions": kind.versions(),
        "ready_timeout_s": READY_TIMEOUT_S,
    }
    runs = []
    for i in range(1, n + 1):
        runs.append(run_once(f"{label}-r{i}", out_dir))
    result = {"meta": meta, "runs": runs, "band": band(runs) if any(r.get("ok") for r in runs) else None}
    (out_dir / "baseline.json").write_text(json.dumps(result, indent=1), encoding="utf-8", newline="\n")
    return result
