"""P8 analysis (docs/p8-plan.md, D-038): agreement of EKS replay verdicts with the kind (P7) verdicts.

Reads scripts/p8/sample.json (frozen sample), the P7 final attempt of each sampled chain (S3 chains/...) and its EKS
replay (S3 p8/<label>/<run_id>/attempt.json). Outputs analysis/out/p8-agreement.md/.json.
Usage: cd harness; uv run python ../analysis/p8_agreement.py eks-p8-20261016
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis.stats import wilson  # noqa: E402

BUCKET = "sbb-artifacts-<AWS_ACCOUNT_ID>"
OUT = ROOT / "analysis" / "out"
GATES = ("l3", "l4", "l5", "l6", "l7")
s3 = boto3.Session(region_name="us-east-1").client("s3")


def get(key):
    try:
        return json.loads(s3.get_object(Bucket=BUCKET, Key=key)["Body"].read())
    except s3.exceptions.NoSuchKey:
        return None


def cohen_kappa(pairs: list[tuple[str, str]]) -> float:
    n = len(pairs)
    cats = sorted({c for p in pairs for c in p})
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[c] * cb[c] for c in cats) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def main(label: str) -> None:
    sample = json.loads((ROOT / "scripts" / "p8" / "sample.json").read_text(encoding="utf-8"))
    rows, missing = [], []
    for s in sample:
        eks = get(f"p8/{label}/{s['run_id']}/attempt.json")
        kind = get(f"chains/{s['run_id']}/iter-{s['n_iterations']}/attempt.json")
        if eks is None:
            missing.append(s["run_id"])
            continue
        rows.append({"run_id": s["run_id"], "case": s["case"], "model": s["model"], "netpol": s["case"].startswith("netpol-"),
                     "kind": kind["verdict"], "eks": eks["verdict"], "kind_gates": kind["gates"], "eks_gates": eks["gates"],
                     "eks_load": {k: (eks.get("load") or {}).get(k) for k in ("p95_ms", "error_rate")},
                     "kind_load": {k: (kind.get("load") or {}).get(k) for k in ("p95_ms", "error_rate")},
                     "eks_failed_checks": [k for k, v in ((eks.get("functional") or {}).get("checks") or {}).items() if v.get("fails")],
                     "kind_failed_checks": [k for k, v in ((kind.get("functional") or {}).get("checks") or {}).items() if v.get("fails")],
                     "eks_regression": {k: v for k, v in ((eks.get("intent") or {}).get("regression") or {}).items() if v and k != "ok"},
                     "eks_intent_runtime": ((eks.get("intent") or {}).get("runtime") or {}).get("result")})
    n = len(rows)
    agree = sum(r["kind"] == r["eks"] for r in rows)
    p, lo, hi = wilson(agree, n)
    res = {"label": label, "n_replayed": n, "missing": missing, "agreement": {"k": agree, "n": n, "p": p, "ci95": [lo, hi]},
           "cohen_kappa": cohen_kappa([(r["kind"], r["eks"]) for r in rows]) if n else None,
           "confusion": Counter(f"{r['kind']} -> {r['eks']}" for r in rows),
           "strata": {}, "gates": {}, "disagreements": [r for r in rows if r["kind"] != r["eks"]]}
    for name, sel in (("kind SAFE_FIX", lambda r: r["kind"] == "SAFE_FIX"), ("kind non-safe", lambda r: r["kind"] != "SAFE_FIX"),
                      ("NetworkPolicy", lambda r: r["netpol"]), ("other types", lambda r: not r["netpol"])):
        rs = [r for r in rows if sel(r)]
        k = sum(r["kind"] == r["eks"] for r in rs)
        res["strata"][name] = {"k": k, "n": len(rs), "ci95": list(wilson(k, len(rs))[1:])}
    for g in GATES:
        both = [r for r in rows if r["kind_gates"].get(g) is not None and r["eks_gates"].get(g) is not None]
        k = sum(r["kind_gates"][g] == r["eks_gates"][g] for r in both)
        res["gates"][g] = {"k": k, "n": len(both)}
    (OUT / "p8-agreement.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8", newline="\n")
    pct = lambda d: f"{d['k']}/{d['n']} = {100 * d['k'] / d['n']:.1f}%" if d["n"] else "-"  # noqa: E731
    L = [f"# P8 — EKS replay vs kind verdicts ({label})", "",
         f"Replayed: {n}/{len(sample)}" + (f" (missing: {len(missing)})" if missing else ""), "",
         f"- Verdict agreement: {agree}/{n} = {100 * p:.1f}% [Wilson 95% CI {100 * lo:.1f}, {100 * hi:.1f}]",
         f"- Cohen's kappa: {res['cohen_kappa']:.3f}" if n else "- Cohen's kappa: -", "", "## By stratum", ""]
    L += [f"- {k}: {pct(v)} [CI {100 * v['ci95'][0]:.1f}, {100 * v['ci95'][1]:.1f}]" for k, v in res["strata"].items()]
    L += ["", "## By gate (both platforms ran the gate)", ""] + [f"- {g.upper()}: {pct(v)}" for g, v in res["gates"].items()]
    L += ["", "## Confusion (kind -> EKS)", ""] + [f"- {k}: {v}" for k, v in sorted(res["confusion"].items())]
    L += ["", "## Disagreements", "", "| case | model | kind | EKS | gates that differ | EKS failed checks | EKS load p95 |",
          "|---|---|---|---|---|---|---|"]
    for r in res["disagreements"]:
        diff = [g for g in GATES if r["kind_gates"].get(g) != r["eks_gates"].get(g)]
        L.append(f"| {r['case']} | {r['model']} | {r['kind']} | {r['eks']} | {', '.join(diff)} | "
                 f"{', '.join(r['eks_failed_checks'][:3])} | {r['eks_load']['p95_ms']} |")
    (OUT / "p8-agreement.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(sys.argv[1])
