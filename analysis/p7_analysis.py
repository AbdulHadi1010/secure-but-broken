"""P7 analysis exactly as pre-registered in docs/protocol.md (FROZEN v1, D-035), section "Analysis plan".

Input : the chain table built by analysis/pilot_summary.py from S3 (one row per chain, final verdict per chain).
Output: analysis/out/p7-results-<wording>.json + .md for W0 (primary) and W1 (secondary), and
        analysis/out/p7-results-wording.md (W0 vs W1, descriptive).
Usage : uv run python analysis/p7_analysis.py [chains.csv]

Definitions (from the verdict rules, harness/evaluate/verdict.py):
  scanner-clean = L1 and L2 pass = verdict in {SAFE_FIX, BREAKING_FIX, DECEPTIVE_FIX, BREAKING_AND_DECEPTIVE}
  breaking      = BREAKING_FIX or BREAKING_AND_DECEPTIVE   (RQ1, among scanner-clean)
  deceptive     = DECEPTIVE_FIX or BREAKING_AND_DECEPTIVE  (RQ2, among scanner-clean)
  safe          = SAFE_FIX                                 (primary outcome, all chains)
No chain is dropped; INVALID_OUTPUT and NOT_FIXED count as not safe and not scanner-clean.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis.stats import chi_square, fisher_2x2, holm, mcnemar_exact, newcombe_diff, rxc_exact, wilson  # noqa: E402

OUT = ROOT / "analysis" / "out"
DEFAULT_CSV = OUT / "p7-20261014-W0-std-p7-20261014-W0-netpol-p7-20261014-W1-std-p7-20261014-W1-netpol-chains.csv"
TYPES = ["privileged", "allow-privilege-escalation", "added-capabilities", "run-as-root", "missing-limits", "netpol"]
CLEAN = {"SAFE_FIX", "BREAKING_FIX", "DECEPTIVE_FIX", "BREAKING_AND_DECEPTIVE"}
CONDITIONS = ["C0", "C1", "C2-LLM", "C2-template"]
PRIMARY_FAMILY = [("C2-LLM", "C1"), ("C2-LLM", "C0"), ("C2-template", "C1")]
SECONDARY = [("C2-LLM", "C2-template")]


def load(path: Path) -> list[dict]:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    missing = [r for r in rows if r["final_verdict"] == "MISSING"]
    if missing:
        raise SystemExit(f"{len(missing)} chains MISSING - completeness must be 1,440/1,440 before analysis")
    for r in rows:
        r["type"] = next(t for t in TYPES if r["case"].startswith(t + "-"))
        v = r["final_verdict"]
        r["clean"] = v in CLEAN
        r["breaking"] = v in ("BREAKING_FIX", "BREAKING_AND_DECEPTIVE")
        r["deceptive"] = v in ("DECEPTIVE_FIX", "BREAKING_AND_DECEPTIVE")
        r["safe"] = v == "SAFE_FIX"
        for k in ("n_iterations", "repairer_tokens_in", "repairer_tokens_out"):
            r[k] = int(r[k])
        r["usd"] = float(r["repairer_cost_usd"]) + float(r["moderator_cost_usd"])
    return rows


def prop(rows, flag, among=None) -> dict:
    base = [r for r in rows if among is None or r[among]]
    k = sum(r[flag] for r in base)
    p, lo, hi = wilson(k, len(base))
    return {"k": k, "n": len(base), "p": p, "ci95": [lo, hi]}


def by(rows, key) -> dict:
    groups = defaultdict(list)
    for r in rows:
        groups[r[key]].append(r)
    return dict(sorted(groups.items()))


def rq3_test(rows, key, flag, among) -> dict:
    """Rate of `flag` (among `among`) across levels of `key`: chi-square, or the exact test if an expected count < 5."""
    table, levels = [], []
    for level, rs in by(rows, key).items():
        base = [r for r in rs if among is None or r[among]]
        if base:
            k = sum(r[flag] for r in base)
            table.append([k, len(base) - k])
            levels.append(level)
    if len(table) < 2 or all(t[0] == 0 for t in table) or all(t[1] == 0 for t in table):
        return {"levels": levels, "table": table, "test": "none (no variation)", "p": None}
    cs = chi_square(table)
    if cs["min_expected"] < 5:
        ex = rxc_exact(table)
        return {"levels": levels, "table": table, "test": "exact (Monte Carlo, seed 20261016)", "p": ex["p"],
                "chi2": ex["chi2"], "min_expected": cs["min_expected"]}
    return {"levels": levels, "table": table, "test": "chi-square", "p": cs["p"], "chi2": cs["chi2"], "dof": cs["dof"],
            "min_expected": cs["min_expected"]}


def paired(rows, a, b) -> dict:
    """SAFE under condition a vs b, paired by (case, model, repeat) within one wording."""
    idx = {(r["case"], r["model"], r["repeat"], r["condition"]): r["safe"] for r in rows}
    units = sorted({(r["case"], r["model"], r["repeat"]) for r in rows})
    pairs = [(idx[u + (a,)], idx[u + (b,)]) for u in units if u + (a,) in idx and u + (b,) in idx]
    mc = mcnemar_exact(pairs)
    ka, kb, n = sum(x for x, _ in pairs), sum(y for _, y in pairs), len(pairs)
    d, lo, hi = newcombe_diff(ka, n, kb, n)
    return {"a": a, "b": b, "n_pairs": n, "safe_a": ka, "safe_b": kb, "risk_difference": d, "rd_ci95": [lo, hi],
            "a_only": mc["a_only"], "b_only": mc["b_only"], "p": mc["p"]}


def effort(rows) -> dict:
    """RQ4 'at what cost': iterations, tokens and money per chain and per SAFE_FIX, per condition."""
    out = {}
    for c, rs in by(rows, "condition").items():
        safe = sum(r["safe"] for r in rs)
        tok = sum(r["repairer_tokens_in"] + r["repairer_tokens_out"] for r in rs)
        usd = sum(r["usd"] for r in rs)
        out[c] = {"chains": len(rs), "safe": safe, "mean_iterations": sum(r["n_iterations"] for r in rs) / len(rs),
                  "tokens_per_chain": tok / len(rs), "usd_per_chain": usd / len(rs),
                  "tokens_per_safe_fix": tok / safe if safe else None, "usd_per_safe_fix": usd / safe if safe else None}
    return out


def analyse(rows) -> dict:
    res = {"n_chains": len(rows)}
    res["overall"] = {"safe": prop(rows, "safe"), "scanner_clean": prop(rows, "clean"),
                      "rq1_breaking_among_clean": prop(rows, "breaking", "clean"),
                      "rq2_deceptive_among_clean": prop(rows, "deceptive", "clean")}
    for key in ("model", "condition"):
        res[f"by_{key}"] = {g: {"safe": prop(rs, "safe"), "scanner_clean": prop(rs, "clean"),
                                "rq1_breaking_among_clean": prop(rs, "breaking", "clean"),
                                "rq2_deceptive_among_clean": prop(rs, "deceptive", "clean")}
                            for g, rs in by(rows, key).items()}
    res["by_model_condition"] = {f"{m} · {c}": {"safe": prop(rs2, "safe"),
                                                "rq1_breaking_among_clean": prop(rs2, "breaking", "clean"),
                                                "rq2_deceptive_among_clean": prop(rs2, "deceptive", "clean")}
                                 for m, rs in by(rows, "model").items() for c, rs2 in by(rs, "condition").items()}
    c0 = [r for r in rows if r["condition"] == "C0"]
    res["c0_scanner_only_view"] = {"scanner_clean": prop(c0, "clean"), "of_which_safe": prop(c0, "safe", "clean"),
                                   "of_which_breaking": prop(c0, "breaking", "clean"),
                                   "of_which_deceptive": prop(c0, "deceptive", "clean")}
    res["by_type"] = {t: {"safe": prop(rs, "safe"), "rq1_breaking_among_clean": prop(rs, "breaking", "clean"),
                          "rq2_deceptive_among_clean": prop(rs, "deceptive", "clean")} for t, rs in by(rows, "type").items()}
    res["rq3_tests"] = {f"{flag}_by_{key}": rq3_test(rows, key, flag, among)
                        for key in ("type", "model") for flag, among in (("breaking", "clean"), ("deceptive", "clean"),
                                                                       ("safe", None))}
    bc = [r for r in rows if r["clean"] and r["fix_class"] in ("b", "c")]
    a = [r for r in rows if r["clean"] and r["fix_class"] == "a"]
    kb, ka = sum(r["breaking"] for r in bc), sum(r["breaking"] for r in a)
    res["h_fc"] = {"classes_bc": {"breaking": kb, "clean": len(bc)}, "class_a": {"breaking": ka, "clean": len(a)},
                   **fisher_2x2(kb, len(bc) - kb, ka, len(a) - ka, alternative="greater")}
    prim = {f"{x} vs {y}": paired(rows, x, y) for x, y in PRIMARY_FAMILY}
    adj = holm({k: v["p"] for k, v in prim.items()})
    for k in prim:
        prim[k].update(p_holm=adj[k]["p_holm"], reject_at_0_05=adj[k]["reject"])
    res["rq4_primary"] = prim
    res["rq4_secondary"] = {f"{x} vs {y}": paired(rows, x, y) for x, y in SECONDARY}
    res["rq4_effort"] = effort(rows)
    return res


def pct(d) -> str:
    return f"{d['k']}/{d['n']} = {100 * d['p']:.1f}% [{100 * d['ci95'][0]:.1f}, {100 * d['ci95'][1]:.1f}]"


def markdown(res, label) -> str:
    L = [f"# P7 results — {label}", "", f"Chains: {res['n_chains']}. Proportions: k/n = % [Wilson 95% CI].", ""]
    o = res["overall"]
    L += ["## Overall", "", f"- SAFE_FIX: {pct(o['safe'])}", f"- Scanner-clean: {pct(o['scanner_clean'])}",
          f"- RQ1 breaking among scanner-clean: {pct(o['rq1_breaking_among_clean'])}",
          f"- RQ2 deceptive among scanner-clean: {pct(o['rq2_deceptive_among_clean'])}", ""]
    c0 = res["c0_scanner_only_view"]
    L += ["## C0: what a scanner-only evaluation would call success", "",
          f"- Scanner-clean: {pct(c0['scanner_clean'])}", f"- of which actually SAFE: {pct(c0['of_which_safe'])}",
          f"- of which breaking: {pct(c0['of_which_breaking'])}", f"- of which deceptive: {pct(c0['of_which_deceptive'])}", ""]
    for key in ("model", "condition", "type"):
        L += [f"## By {key}", "", "| | SAFE_FIX | breaking among clean | deceptive among clean |", "|---|---|---|---|"]
        for g, d in res[f"by_{key}"].items():
            L.append(f"| {g} | {pct(d['safe'])} | {pct(d['rq1_breaking_among_clean'])} | {pct(d['rq2_deceptive_among_clean'])} |")
        L.append("")
    L += ["## By model x condition", "", "| | SAFE_FIX | breaking among clean | deceptive among clean |", "|---|---|---|---|"]
    for g, d in res["by_model_condition"].items():
        L.append(f"| {g} | {pct(d['safe'])} | {pct(d['rq1_breaking_among_clean'])} | {pct(d['rq2_deceptive_among_clean'])} |")
    L += ["", "## RQ3 tests", "", "| test | method | p |", "|---|---|---|"]
    for k, t in res["rq3_tests"].items():
        pv = "-" if t["p"] is None else f"{t['p']:.4g}"
        L.append(f"| {k} | {t['test']} | {pv} |")
    h = res["h_fc"]
    L += ["", f"H-FC (one-sided Fisher, breaking among clean, classes b+c vs a): b+c {h['classes_bc']['breaking']}/"
          f"{h['classes_bc']['clean']}, a {h['class_a']['breaking']}/{h['class_a']['clean']}, OR {h['odds_ratio']:.3g}, "
          f"p = {h['p']:.4g}", "", "## RQ4 primary family (exact McNemar, Holm)", "",
          "| comparison | pairs | safe A | safe B | A only | B only | risk diff [95% CI] | p | p Holm | reject |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for k, t in res["rq4_primary"].items():
        L.append(f"| {k} | {t['n_pairs']} | {t['safe_a']} | {t['safe_b']} | {t['a_only']} | {t['b_only']} | "
                 f"{100 * t['risk_difference']:+.1f} pp [{100 * t['rd_ci95'][0]:+.1f}, {100 * t['rd_ci95'][1]:+.1f}] | "
                 f"{t['p']:.4g} | {t['p_holm']:.4g} | {t['reject_at_0_05']} |")
    L += ["", "Secondary:", ""]
    for k, t in res["rq4_secondary"].items():
        L.append(f"- {k}: safe {t['safe_a']} vs {t['safe_b']} of {t['n_pairs']} pairs, A only {t['a_only']}, "
                 f"B only {t['b_only']}, risk diff {100 * t['risk_difference']:+.1f} pp, p = {t['p']:.4g}")
    L += ["", "## RQ4 effort per condition", "",
          "| condition | chains | safe | mean iterations | tokens/chain | USD/chain | tokens/SAFE_FIX | USD/SAFE_FIX |",
          "|---|---|---|---|---|---|---|---|"]
    for c, e in res["rq4_effort"].items():
        f = lambda v, n=0: "-" if v is None else f"{v:,.{n}f}"  # noqa: E731
        L.append(f"| {c} | {e['chains']} | {e['safe']} | {e['mean_iterations']:.2f} | {f(e['tokens_per_chain'])} | "
                 f"{f(e['usd_per_chain'], 3)} | {f(e['tokens_per_safe_fix'])} | {f(e['usd_per_safe_fix'], 3)} |")
    return "\n".join(L) + "\n"


def main(path: Path) -> None:
    rows = load(path)
    results = {}
    for w, label in (("W0", "W0 (primary)"), ("W1", "W1 (secondary)")):
        rs = [r for r in rows if r["wording"] == w]
        results[w] = analyse(rs)
        (OUT / f"p7-results-{w}.json").write_text(json.dumps(results[w], indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)), encoding="utf-8", newline="\n")
        (OUT / f"p7-results-{w}.md").write_text(markdown(results[w], label), encoding="utf-8", newline="\n")
    L = ["# P7 — wording W0 vs W1 (descriptive)", "", "| condition | W0 SAFE_FIX | W1 SAFE_FIX |", "|---|---|---|"]
    for c in CONDITIONS:
        L.append(f"| {c} | {pct(results['W0']['by_condition'][c]['safe'])} | {pct(results['W1']['by_condition'][c]['safe'])} |")
    (OUT / "p7-results-wording.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print((OUT / "p7-results-W0.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV)
