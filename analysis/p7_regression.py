"""P7 robustness analysis (protocol "Analysis plan", sensitivity, not the primary test):
mixed-effects logistic regression of SAFE_FIX on condition, model, misconfiguration type and wording,
with a random intercept per case.

Fitted with statsmodels' BinomialBayesMixedGLM (variational Bayes, default priors): several types have 100% SAFE_FIX,
which makes a maximum-likelihood GLMM fail (complete separation); the weak priors keep the estimates finite (D-037).
Reference levels: condition C1 (prior work's loop), model kimi-k3, type privileged, wording W0.
Output: analysis/out/p7-regression.md/.json for all 1,440 chains and for W0 only.
Usage : uv run --group analysis python analysis/p7_regression.py [chains.csv]
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd
from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis" / "out"
DEFAULT_CSV = OUT / "p7-20261014-W0-std-p7-20261014-W0-netpol-p7-20261014-W1-std-p7-20261014-W1-netpol-chains.csv"
TYPES = ["privileged", "allow-privilege-escalation", "added-capabilities", "run-as-root", "missing-limits", "netpol"]
FORMULA = ("safe ~ C(condition, Treatment('C1')) + C(model, Treatment('kimi-k3')) "
           "+ C(type, Treatment('privileged')){wording}")


def fit(df: pd.DataFrame, with_wording: bool) -> list[dict]:
    f = FORMULA.format(wording=" + C(wording, Treatment('W0'))" if with_wording else "")
    m = BinomialBayesMixedGLM.from_formula(f, {"case": "0 + C(case)"}, df)
    r = m.fit_vb(rng=20261016)  # fixed seed: fit_vb draws random starting SDs otherwise (P9 repro check)
    rows = []
    for name, mean, sd in zip(m.exog_names, r.fe_mean, r.fe_sd):
        lo, hi = mean - 1.959964 * sd, mean + 1.959964 * sd
        rows.append({"term": name, "log_odds": float(mean), "sd": float(sd), "odds_ratio": math.exp(mean),
                     "or_95": [math.exp(lo), math.exp(hi)], "excludes_1": bool(lo > 0 or hi < 0)})
    rows.append({"term": "case random-intercept SD (log scale param)", "log_odds": float(r.vcp_mean[0]),
                 "sd": float(r.vcp_sd[0]), "odds_ratio": None, "or_95": None, "excludes_1": None})
    return rows


def md(rows, title) -> str:
    L = [f"## {title}", "", "| term | log-odds | SD | OR | OR 95% interval | excludes 1 |", "|---|---|---|---|---|---|"]
    for r in rows:
        if r["odds_ratio"] is None:
            L.append(f"| {r['term']} | {r['log_odds']:.3f} | {r['sd']:.3f} | | | |")
        else:
            L.append(f"| {r['term']} | {r['log_odds']:.3f} | {r['sd']:.3f} | {r['odds_ratio']:.3g} | "
                     f"[{r['or_95'][0]:.3g}, {r['or_95'][1]:.3g}] | {r['excludes_1']} |")
    return "\n".join(L) + "\n"


def main(path: Path) -> None:
    df = pd.read_csv(path)
    df["type"] = [next(t for t in TYPES if c.startswith(t + "-")) for c in df["case"]]
    df["safe"] = (df["final_verdict"] == "SAFE_FIX").astype(int)
    res = {"all_chains": fit(df, True), "w0_only": fit(df[df["wording"] == "W0"], False)}
    (OUT / "p7-regression.json").write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    text = ("# P7 sensitivity: mixed-effects logistic regression of SAFE_FIX\n\nVariational Bayes (statsmodels "
            "BinomialBayesMixedGLM); random intercept per case; references C1, kimi-k3, privileged, W0.\n\n"
            + md(res["all_chains"], f"All chains (n={len(df)})") + "\n"
            + md(res["w0_only"], f"W0 only (n={int((df['wording'] == 'W0').sum())})"))
    (OUT / "p7-regression.md").write_text(text, encoding="utf-8", newline="\n")
    print(text)


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV)
