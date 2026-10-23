"""Format-only check of the D-032 models (exploratory, excluded from results).

For each repairer: send the frozen first prompt for one case, check the reply parses (format only, no gates,
no verdict) and record tokens / cost / wall time. Moderator: one call with the frozen moderator system prompt
on a synthetic evaluator record, check leakage + grounding. Output: scripts/trials/2026-10-06_format_check.json.
"""

import json
import os
import sys
from pathlib import Path

import yaml

from harness.cases import CASES
from harness.moderator import feedback
from harness.orchestrate import loop
from harness.repair import bedrock, prompt
from harness.repair.prompt import InvalidOutput

CASE = "privileged-frontend"
PROFILE = os.environ.get("AWS_PROFILE")  # VM: instance role
OUT = Path(__file__).with_suffix(".json")

case_dir = CASES / CASE
meta = json.loads((case_dir / "meta.json").read_text(encoding="utf-8"))
manifests = (case_dir / "manifests.yaml").read_text(encoding="utf-8")
expected = [d for d in yaml.safe_load_all(manifests) if d]
first = prompt.build_user_prompt(loop.case_findings(case_dir, meta), manifests, False)
br = bedrock.client(PROFILE)
results = []
for m in loop.MODELS["repairers"] + loop.MODELS["stretch_repairers"]:
    spec = loop.model_spec(m["key"])
    row = {"key": m["key"], "model_id": m["model_id"]}
    try:
        r = bedrock.converse(br, spec["model_id"], prompt.SYSTEM, [{"role": "user", "text": first}], spec["temperature"])
        row |= {k: r[k] for k in ("input_tokens", "output_tokens", "cost_usd", "wall_s", "stop_reason", "temperature_sent")}
        try:
            docs = prompt.parse_response(r["text"], expected)
            row |= {"parsed": True, "n_docs": len(docs)}
        except InvalidOutput as e:
            row |= {"parsed": False, "invalid_reason": str(e), "text_head": r["text"][:300]}
    except Exception as e:  # noqa: BLE001 - recorded, not hidden
        row |= {"error": repr(e)[:300]}
    print(row, flush=True)
    results.append(row)

mod = loop.MODELS["moderator"]
rec = {"verdict": "BREAKING_FIX", "gates": {"parsed": True, "l1": True, "l2": True, "l3": True, "l4": False,
                                            "l5": None, "l6": None, "l7": None},
       "evidence": {"pods": [{"name": "frontend-x", "phase": "Running", "ready": False, "restarts": 4,
                              "waiting_reason": "CrashLoopBackOff", "last_terminated_reason": "Error"}],
                    "error_lines": {"frontend-x": ["listen tcp :80: bind: permission denied"]}}}
usage = []


def call(system, user):
    r = bedrock.converse(br, mod["model_id"], system, [{"role": "user", "text": user}], mod["temperature"], max_tokens=2000)
    usage.append({k: r.get(k) for k in ("input_tokens", "output_tokens", "wall_s", "cost_usd")})
    return r["text"]


try:
    fb = feedback.c2_llm(rec, manifests, feedback.gold_diff_tokens(manifests, manifests), call)
    mrow = {"key": mod["key"], "source": fb["source"], "usage": usage, "message_head": fb["message"][:600]}
except Exception as e:  # noqa: BLE001
    mrow = {"key": mod["key"], "error": repr(e)[:300], "usage": usage}
print(mrow, flush=True)
OUT.write_text(json.dumps({"case": CASE, "repairers": results, "moderator": mrow}, indent=1), encoding="utf-8", newline="\n")
sys.exit(0)
