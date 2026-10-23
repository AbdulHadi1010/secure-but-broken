"""One attempt end to end: repaired manifests -> L1..L7 on a fresh kind cluster -> deterministic verdict.

Also collects the runtime evidence a C2 moderator may use (pod states, warning events, log tails, failing
checks, k6 summary, intent output). Evidence never includes gold content.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from harness.cases import gold_findings
from harness.checks import intent, k6, scanners
from harness.deploy import kind
from harness.evaluate.verdict import Gates, verdict
from harness.gold import NAMESPACE

READY_TIMEOUT_S = 300  # D-020: ~7x the slowest warm-cache ready time seen (41 s baseline, 54 s case validation)
BASELINE_DIR = kind.ROOT / "app" / "baseline"


def active_baseline() -> Path:
    """The baseline whose band judges L6 is named in app/baseline/ACTIVE (one label per line, first wins), so a
    switch of measuring machine is one recorded change (D-023/D-024)."""
    import os

    # P8 (D-038): an EKS run is judged against the EKS baseline, named explicitly; kind runs keep ACTIVE
    label = os.environ.get("SBB_BASELINE") or (BASELINE_DIR / "ACTIVE").read_text(encoding="utf-8").split()[0]
    return BASELINE_DIR / f"{label}.json"


def band() -> dict:
    return json.loads(active_baseline().read_text(encoding="utf-8"))["band"]["thresholds"]


def l1_l2(repair_file: Path, meta: dict) -> dict:
    found = scanners.scan(repair_file)
    keys = scanners.keys(found)
    remaining_targets = sorted(k for k in keys if any(k.startswith(r + ":") for r in meta["target_rules"]))
    beyond_gold = sorted(keys - scanners.keys(gold_findings()))
    return {"l1": not remaining_targets, "remaining_target_findings": remaining_targets,
            "l2": not beyond_gold, "findings_beyond_gold": beyond_gold, "new_findings_count": len(beyond_gold)}


def _evidence(ctx: str) -> dict:
    """What went wrong in the cluster, in the words the cluster uses. Only unhealthy workloads: transient events
    from objects being created in parallel (e.g. 'serviceaccount not found' before the SA exists) are dropped."""
    pods = kind.pods(ctx, NAMESPACE)
    bad = [p for p in pods if not p["ready"] or p["restarts"]]
    bad_apps = {p["app"] for p in bad if p.get("app")}
    ev = kind.kubectl(ctx, "-n", NAMESPACE, "get", "events", "--field-selector", "type=Warning", "-o",
                      "custom-columns=OBJ:.involvedObject.name,REASON:.reason,MSG:.message", "--no-headers",
                      check=False).stdout.splitlines()
    ev = [e for e in ev if any(e.startswith(a) for a in bad_apps)][-15:]
    tails = {p["name"]: kind.kubectl(ctx, "-n", NAMESPACE, "logs", p["name"], "--tail=20", "--all-containers",
                                     check=False).stdout[-2000:] for p in bad}
    # D-028: when every pod is Ready but journeys or load fail, the cause lives in the logs of healthy pods
    # (e.g. a service that cannot reach its dependency). Error-like lines from EVERY pod, last few each.
    errors = {}
    for p in pods:
        log = kind.kubectl(ctx, "-n", NAMESPACE, "logs", p["name"], "--tail=300", "--all-containers",
                           check=False).stdout
        hits = [x.strip()[:300] for x in log.splitlines() if is_error_line(x)]
        if hits:
            errors[p["name"]] = hits[-4:]
    return {"pods": bad, "warning_events": ev, "log_tails": tails, "error_lines": errors}


ERROR_LINE = re.compile(r"error|fail|refused|timeout|timed out|no such host|unavailable|deadline exceeded|"
                        r"could not|cannot|unreachable|reset by peer", re.IGNORECASE)
# F14: a line its own logger marks as INFO/DEBUG/TRACE is not an error, even if it contains such a word
# (e.g. adservice's '"level":"INFO" ... Stats enabled, but temporarily unavailable').
QUIET_LEVEL = re.compile(r"""("level"|"severity")\s*:\s*"(info|debug|trace)"|\blevel=(info|debug|trace)\b|^\S*\s*(INFO|DEBUG|TRACE)\b""",
                         re.IGNORECASE)


def is_error_line(line: str) -> bool:
    return bool(ERROR_LINE.search(line)) and not QUIET_LEVEL.search(line)


def run_attempt(repair_docs: list[dict], meta: dict, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    repair_file = out_dir / "repair.yaml"
    repair_file.write_text(yaml.safe_dump_all(repair_docs, sort_keys=False), encoding="utf-8", newline="\n")
    rec: dict = {"case_id": meta["case_id"], "started": datetime.now(timezone.utc).isoformat(),
                 "repair_sha256": hashlib.sha256(repair_file.read_bytes()).hexdigest()}
    t_all = time.perf_counter()
    rec["static"] = l1_l2(repair_file, meta)
    g = Gates(parsed=True, l1=rec["static"]["l1"], l2=rec["static"]["l2"])
    if g.l1 and g.l2:
        ctx = f"sbb-att-{rec['repair_sha256'][:8]}"
        try:
            kind.create_cluster(ctx)
            kind.kubectl(ctx, "create", "namespace", NAMESPACE)
            dry = kind.kubectl(ctx, "apply", "--dry-run=server", "-f", str(repair_file), check=False)
            g.l3 = dry.returncode == 0
            rec["l3_error"] = None if g.l3 else dry.stderr[-1500:]
            if g.l3:
                t0 = time.perf_counter()
                kind.kubectl(ctx, "apply", "-f", str(repair_file), check=False)
                w = kind.kubectl(ctx, "-n", NAMESPACE, "wait", "deploy", "--all", "--for=condition=Available",
                                 f"--timeout={READY_TIMEOUT_S}s", check=False, timeout=READY_TIMEOUT_S + 60)
                g.l4 = w.returncode == 0
                rec["ready_s"] = round(time.perf_counter() - t0, 1)
                if g.l4:
                    f = k6.with_email_check(k6.functional_result(k6.run_job(ctx, "functional", "functional.js", 180)),
                                            k6.email_check(ctx))
                    rec["functional"] = f
                    g.l5 = f["pass_rate"] == 1.0
                    th = band()

                    def within(ld: dict) -> bool:
                        return (ld["error_rate"] or 0) <= th["error_rate_max"] and (ld["p95_ms"] or 1e9) <= th["p95_ms_max"]

                    load = k6.load_result(k6.run_job(ctx, "load", "load.js", 400))
                    rec["load"] = {**load, "band": th}
                    g.l6 = within(load)
                    if not g.l6:  # D-024: retest once on the same cluster; L6 fails only if both runs fail
                        retest = k6.load_result(k6.run_job(ctx, "load-retest", "load.js", 400))
                        rec["load_retest"] = retest
                        g.l6 = within(retest)
                try:
                    rec["intent"] = intent.check(ctx, repair_file, meta)
                    g.l7 = rec["intent"]["pass"]
                except Exception as e:  # noqa: BLE001 - e.g. target pod never became ready: intent not judgeable
                    rec["intent"] = {"error": f"{type(e).__name__}: {e}"[:500]}
                if not all((g.l4, g.l5, g.l6)):
                    rec["evidence"] = _evidence(ctx)
        finally:
            kind.delete_cluster(ctx)
    rec["gates"] = g.model_dump()
    rec["verdict"] = verdict(g).value
    rec["wallclock_s"] = round(time.perf_counter() - t_all, 1)
    (out_dir / "attempt.json").write_text(json.dumps(rec, indent=1), encoding="utf-8", newline="\n")
    return rec
