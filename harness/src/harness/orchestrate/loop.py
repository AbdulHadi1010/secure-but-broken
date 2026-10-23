"""Repair chains: C0 (one shot), C1 (scanner loop), C2-LLM / C2-template (runtime-feedback loop). CLAUDE.md §3.

One chain = one (case, model, condition, repeat). Each iteration: repairer call -> parse -> L1..L7 -> verdict.
Stop rules: C0 after 1; C1 when the scanner is clean or after N; C2 on SAFE_FIX or after N.
Everything (prompts, responses, feedback, moderator tries, records) goes to runs/chains/<run_id>/ and S3,
one DynamoDB item per iteration.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

import boto3
import yaml

from harness.artifacts import BUCKET, upload_dir
from harness.cases import CASES
from harness.checks import intent, k6, scanners
from harness.deploy import kind
from harness.gold import OUT as GOLD_MANIFEST
from harness.moderator import feedback
from harness.orchestrate.attempt import run_attempt
from harness.repair import bedrock, prompt
from harness.repair.prompt import InvalidOutput

MODELS = json.loads((kind.ROOT / "harness" / "config" / "models.json").read_text(encoding="utf-8"))
CONDITIONS = ("C0", "C1", "C2-LLM", "C2-template")
MAX_ITER = 5
TABLE = "sbb-attempts"


def _git() -> str:
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=kind.ROOT).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no", "--", "harness", "loadtest",
                            "policies", "cases", "app"],
                           capture_output=True, text=True, cwd=kind.ROOT).stdout.strip()
    return head + ("-dirty" if dirty else "")


def model_spec(key: str) -> dict:
    for m in MODELS["repairers"] + MODELS["stretch_repairers"]:
        if m["key"] == key:
            return {**m, "temperature": m.get("temperature", MODELS["temperature"])}
    raise KeyError(key)


def case_findings(case_dir: Path, meta: dict) -> list[dict]:
    """Findings shown to the repairer: the case's declared target + coupled rules, as the scanner reports them."""
    rules = meta["target_rules"] + meta["coupled_rules"]
    return [f for f in scanners.scan(case_dir / "manifests.yaml")
            if any(scanners.key(f).startswith(r + ":") for r in rules)]


def _write(p: Path, obj) -> None:
    p.write_text(json.dumps(obj, indent=1, default=str), encoding="utf-8", newline="\n")


def run_chain(case: str, model_key: str, condition: str = "C0", repeat: int = 1, keep_working: bool = False,
              upload: bool = True, profile: str | None = None, max_iter: int = MAX_ITER,
              batch: str | None = None, worker: str | None = None) -> dict:
    if condition not in CONDITIONS:
        raise ValueError(f"condition must be one of {CONDITIONS}")
    case_dir = CASES / case
    meta = json.loads((case_dir / "meta.json").read_text(encoding="utf-8"))
    manifests = (case_dir / "manifests.yaml").read_text(encoding="utf-8")
    expected = [d for d in yaml.safe_load_all(manifests) if d]
    spec = model_spec(model_key)
    mod = MODELS["moderator"]
    br = bedrock.client(profile)
    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{case}-{model_key}-{condition}-r{repeat}-{uuid.uuid4().hex[:6]}"
    out = kind.ROOT / "runs" / "chains" / run_id
    out.mkdir(parents=True, exist_ok=True)
    diff_tokens = feedback.gold_diff_tokens(GOLD_MANIFEST.read_text(encoding="utf-8"), manifests)  # leakage check only

    findings = case_findings(case_dir, meta)
    first = prompt.build_user_prompt(findings, manifests, keep_working)
    messages = [{"role": "user", "text": first}]
    chain_meta = {
        "run_id": run_id, "case_id": case, "misconfig_type": meta["type"], "fix_class": meta["fix_class"],
        "service": meta["service"], "model_key": model_key, "model_id": spec["model_id"], "condition": condition,
        "repeat": repeat, "max_iter": 1 if condition == "C0" else max_iter, "prompt_version": prompt.PROMPT_VERSION,
        "keep_working_wording": keep_working, "system_prompt_sha256": hashlib.sha256(prompt.SYSTEM.encode()).hexdigest(),
        "first_prompt_sha256": hashlib.sha256(first.encode()).hexdigest(), "moderator_model_id": mod["model_id"],
        "moderator_prompt_sha": feedback.MODERATOR_PROMPT_SHA, "git_commit": _git(),
        "batch": batch, "worker": worker, "baseline": _active_baseline_name(),
        "tool_versions": {**kind.versions(), "scanners": scanners.VERSIONS, "kyverno": intent.KYVERNO, "k6": k6.K6_IMAGE},
    }
    _write(out / "chain.json", chain_meta)
    iterations = []
    latest_yaml = manifests
    for it in range(1, chain_meta["max_iter"] + 1):
        idir = out / f"iter-{it}"
        idir.mkdir(exist_ok=True)
        _write(idir / "messages.json", {"system": prompt.SYSTEM, "messages": messages})
        resp = bedrock.converse(br, spec["model_id"], prompt.SYSTEM, messages, spec["temperature"])
        _write(idir / "response.json", resp)
        try:
            docs = prompt.parse_response(resp["text"], expected)
            rec = run_attempt(docs, meta, idir)
            rec["removed_objects"] = prompt.removed_objects(docs, expected)  # D-029: recorded, judged by gates
            _write(idir / "attempt.json", rec)
            latest_yaml = (idir / "repair.yaml").read_text(encoding="utf-8")
        except InvalidOutput as e:
            rec = {"verdict": "INVALID_OUTPUT", "invalid_reason": str(e), "gates": {"parsed": False}}
            _write(idir / "attempt.json", rec)
        it_rec = {"iteration": it, "verdict": rec["verdict"], "gates": rec.get("gates"),
                  "tokens_in": resp["input_tokens"], "tokens_out": resp["output_tokens"], "cost_usd": resp.get("cost_usd"), "stop_reason": resp["stop_reason"],
                  "llm_wall_s": resp["wall_s"], "attempt_wallclock_s": rec.get("wallclock_s")}

        # stop rules
        scanner_clean = bool(rec.get("gates", {}).get("l1")) and bool(rec.get("gates", {}).get("l2"))
        stop = (condition == "C0" or rec["verdict"] == "SAFE_FIX" or it == chain_meta["max_iter"]
                or (condition == "C1" and scanner_clean))
        if not stop:
            if rec["verdict"] == "INVALID_OUTPUT":
                fb = {"message": f"Your reply could not be used: {rec['invalid_reason']}. Reply with exactly one ```yaml "
                                 "block containing the complete manifest set.", "source": "format"}
            elif condition == "C1":
                fb = {"message": feedback.c1_message(rec), "source": "c1_template"}
            elif condition == "C2-template":
                fb = {"message": feedback.c2_template(rec), "source": "c2_template"}
            else:
                def call(system, user):
                    r = bedrock.converse(br, mod["model_id"], system, [{"role": "user", "text": user}],
                                         mod.get("temperature", 0.0), max_tokens=2000)
                    call.usage.append({k: r.get(k) for k in ("input_tokens", "output_tokens", "wall_s", "cost_usd")})
                    return r["text"]
                call.usage = []
                fb = feedback.c2_llm(rec, latest_yaml, diff_tokens, call)
                fb["moderator_usage"] = call.usage
            _write(idir / "feedback.json", fb)
            it_rec["feedback_source"] = fb["source"]
            it_rec["moderator_usage"] = fb.get("moderator_usage")
            messages += [{"role": "assistant", "text": resp["text"] or "(empty reply)"},
                         {"role": "user", "text": fb["message"]}]
        iterations.append(it_rec)
        _write(out / "iterations.json", iterations)
        if upload:
            _put_item(profile, run_id, it, chain_meta, it_rec)
        if stop:
            break
    summary = {**chain_meta, "iterations": iterations, "final_verdict": iterations[-1]["verdict"],
               "n_iterations": len(iterations)}
    _write(out / "summary.json", summary)
    if upload:
        upload_dir(out, f"chains/{run_id}", profile=profile)
        summary["s3_prefix"] = f"s3://{BUCKET}/chains/{run_id}"
        if batch:  # completeness marker for the batch manifest (fleet.completeness)
            key = f"batches/{batch}/done/{case}__{model_key}__{condition}__r{repeat}.json"
            boto3.Session(profile_name=profile, region_name="us-east-1").client("s3").put_object(
                Bucket=BUCKET, Key=key, Body=json.dumps({"run_id": run_id, "final_verdict": summary["final_verdict"]}).encode())
    return summary


def _active_baseline_name() -> str:
    from harness.orchestrate.attempt import active_baseline

    return active_baseline().stem


def _put_item(profile, run_id, it, chain_meta, it_rec) -> None:
    item = {"run_id": {"S": run_id}, "attempt_id": {"S": f"iter-{it}"}, "case_id": {"S": chain_meta["case_id"]},
            "model_id": {"S": chain_meta["model_id"]}, "condition": {"S": chain_meta["condition"]},
            "repeat": {"N": str(chain_meta["repeat"])}, "iteration": {"N": str(it)}, "verdict": {"S": it_rec["verdict"]},
            "gates": {"S": json.dumps(it_rec["gates"])}, "s3_prefix": {"S": f"s3://{BUCKET}/chains/{run_id}/iter-{it}"},
            "git_commit": {"S": chain_meta["git_commit"]}, "batch": {"S": chain_meta.get("batch") or "adhoc"}}
    boto3.Session(profile_name=profile, region_name="us-east-1").client("dynamodb").put_item(TableName=TABLE, Item=item)
