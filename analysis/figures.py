"""Paper figures for P7 (PNG 300 dpi + PDF) in analysis/figures/. Every number is computed from the chain table with
the same definitions as analysis/p7_analysis.py (imported), so figures and tables cannot disagree.
Colours: dataviz reference palette (validated: first three categorical slots pass all-pairs CVD/normal-vision; aqua
is < 3:1 on the surface, so every series also has a distinct marker and a direct label or legend).
Usage: uv run --group analysis python analysis/figures.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis.p7_analysis import DEFAULT_CSV, TYPES, load, newcombe_diff, paired, prop  # noqa: E402

FIG = ROOT / "analysis" / "figures"
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
MODELS = [("kimi-k3", "Kimi K3", "#2a78d6", "o"), ("glm-5", "GLM-5", "#eb6834", "s"),
          ("deepseek-v3-2", "DeepSeek V3.2", "#1baf7a", "D")]
CONDS = [("C0", "C0 one-shot"), ("C1", "C1 scanner"), ("C2-LLM", "C2 LLM"), ("C2-template", "C2 template")]
VERDICTS = [("SAFE_FIX", "Safe", "#0ca30c", 0.55), ("BREAKING_FIX", "Breaking", "#ec835a", 0.9),
            ("DECEPTIVE_FIX", "Deceptive", "#d03b3b", 0.75), ("BREAKING_AND_DECEPTIVE", "Breaking and deceptive", "#d03b3b", 1.0),
            ("NOT_FIXED", "Not fixed", "#b5b3ad", 1.0), ("INVALID_OUTPUT", "Invalid output", "#d9d8d3", 1.0)]
TYPE_LABEL = {"privileged": "privileged", "allow-privilege-escalation": "allowPrivilegeEscalation",
              "added-capabilities": "added capabilities", "run-as-root": "run as root", "missing-limits": "missing limits",
              "netpol": "NetworkPolicy"}

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE})


def save(fig, name):
    FIG.mkdir(exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(FIG / f"{name}.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)


def fig1_scanner_view(rows):
    """C0 (one-shot), W0: what each model's final verdicts are, i.e. what a scanner-only evaluation hides."""
    c0 = [r for r in rows if r["condition"] == "C0" and r["wording"] == "W0"]
    groups = [(lab, [r for r in c0 if r["model"] == m]) for m, lab, _, _ in MODELS] + [("All models", c0)]
    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    for y, (lab, rs) in enumerate(reversed(groups)):
        left = 0
        for v, vlab, col, a in VERDICTS:
            n = sum(r["final_verdict"] == v for r in rs)
            if n:
                w = 100 * n / len(rs)
                ax.barh(y, w, left=left, color=col, alpha=a, edgecolor=SURFACE, linewidth=1.5, height=0.62,
                        hatch="////" if v == "BREAKING_AND_DECEPTIVE" else None)
                if w >= 4:
                    ax.text(left + w / 2, y, str(n), ha="center", va="center", color=INK, fontsize=8)
                left += w
        clean = sum(r["clean"] for r in rs)
        ax.text(101, y, f"scanner-clean {clean}/{len(rs)}", va="center", color=INK2, fontsize=8)
    ax.set_yticks(range(len(groups)), [g[0] for g in reversed(groups)])
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of one-shot (C0) repairs, wording W0 (%)")
    ax.set_title("Scanner-clean is not the same as safe: one-shot repairs by final verdict", loc="left", color=INK, fontsize=10)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c, alpha=a, hatch="////" if v == "BREAKING_AND_DECEPTIVE" else None)
               for v, _, c, a in VERDICTS]
    ax.legend(handles, [l for _, l, _, _ in VERDICTS], ncol=6, frameon=False, fontsize=7, loc="upper center",
              bbox_to_anchor=(0.45, -0.32))
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    save(fig, "fig1_scanner_clean_vs_safe")


def fig2_safe_by_condition(rows):
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0), sharey=True)
    for ax, w in zip(axes, ("W0", "W1")):
        rw = [r for r in rows if r["wording"] == w]
        for j, (m, lab, col, mk) in enumerate(MODELS):
            xs, ys, lo, hi = [], [], [], []
            for i, (c, _) in enumerate(CONDS):
                p = prop([r for r in rw if r["model"] == m and r["condition"] == c], "safe")
                xs.append(i + (j - 1) * 0.18)
                ys.append(100 * p["p"])
                lo.append(max(0.0, 100 * (p["p"] - p["ci95"][0])))
                hi.append(max(0.0, 100 * (p["ci95"][1] - p["p"])))
            ax.errorbar(xs, ys, yerr=[lo, hi], fmt=mk, color=col, ms=5, lw=1, capsize=0, label=lab)
        allp = [prop([r for r in rw if r["condition"] == c], "safe") for c, _ in CONDS]
        ax.plot(range(4), [100 * p["p"] for p in allp], color=INK, lw=1, ls="--", label="All models")
        ax.set_xticks(range(4), [l.replace(" ", "\n", 1) for _, l in CONDS], fontsize=7.5)
        ax.set_title(f"Wording {w}{' (primary)' if w == 'W0' else ''}", loc="left", color=INK, fontsize=9)
        ax.grid(axis="y", color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("SAFE_FIX (%) with 95% Wilson CI")
    axes[0].set_ylim(65, 101)
    axes[1].legend(frameon=False, fontsize=7.5, loc="lower right")
    fig.suptitle("Runtime feedback (C2) raises the share of safe fixes; the axis starts at 65%", x=0.01, y=1.04, ha="left",
                 color=INK, fontsize=10)
    save(fig, "fig2_safe_by_condition")


def fig3_by_type(rows):
    rw = [r for r in rows if r["wording"] == "W0"]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.6), sharey=True)
    for ax, (flag, title) in zip(axes, (("breaking", "Breaking (RQ1)"), ("deceptive", "Deceptive (RQ2)"))):
        for y, t in enumerate(reversed(TYPES)):
            p = prop([r for r in rw if r["type"] == t], flag, "clean")
            hi_col = "#d03b3b" if t == "netpol" else "#8a8984"
            ax.barh(y, 100 * p["p"], color=hi_col, alpha=0.75, height=0.6)
            ax.errorbar(100 * p["p"], y, xerr=[[max(0.0, 100 * (p["p"] - p["ci95"][0]))], [max(0.0, 100 * (p["ci95"][1] - p["p"]))]],
                        color=INK2, lw=0.8, capsize=0)
            ax.text(100 * p["ci95"][1] + 0.6, y, f"{p['k']}/{p['n']}", va="center", fontsize=7.5, color=INK2)
        ax.set_yticks(range(len(TYPES)), [TYPE_LABEL[t] for t in reversed(TYPES)])
        ax.set_xlim(0, 30)
        ax.set_xlabel("% of scanner-clean repairs (95% CI)")
        ax.set_title(title, loc="left", color=INK, fontsize=9)
        ax.grid(axis="x", color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
    fig.suptitle("Every breaking or deceptive repair was a NetworkPolicy repair (wording W0)", x=0.01, y=1.05, ha="left",
                 color=INK, fontsize=10)
    save(fig, "fig3_breaking_deceptive_by_type")


def fig4_rq4(rows):
    comps = [("C2-LLM", "C1"), ("C2-LLM", "C0"), ("C2-template", "C1"), ("C2-LLM", "C2-template")]
    fig, ax = plt.subplots(figsize=(7.2, 2.8))
    labels = []
    for i, (a, b) in enumerate(comps):
        for j, (w, col, mk) in enumerate((("W0", "#2a78d6", "o"), ("W1", "#eb6834", "s"))):
            t = paired([r for r in rows if r["wording"] == w], a, b)
            y = len(comps) - 1 - i + (0.15 if j == 0 else -0.15)
            ax.errorbar(100 * t["risk_difference"], y, xerr=[[max(0.0, 100 * (t["risk_difference"] - t["rd_ci95"][0]))],
                        [max(0.0, 100 * (t["rd_ci95"][1] - t["risk_difference"]))]], fmt=mk, color=col, ms=5, lw=1, capsize=0,
                        label=w if i == 0 else None)
            ax.text(17.5, y, f"{t['a_only']} vs {t['b_only']} discordant, p={t['p']:.2g}", va="center", fontsize=7,
                    color=INK2)
        labels.append(f"{a} vs {b}" + ("  (secondary)" if (a, b) == ("C2-LLM", "C2-template") else ""))
    ax.axvline(0, color=INK2, lw=0.8)
    ax.set_yticks(range(len(comps)), list(reversed(labels)))
    ax.set_xlim(-10, 17)
    ax.set_xlabel("Difference in SAFE_FIX rate, percentage points (95% Newcombe CI); right = first condition better")
    ax.legend(frameon=False, fontsize=7.5, loc="lower left")
    ax.set_title("Runtime feedback beats the scanner loop; LLM and template feedback do not differ", loc="left",
                 color=INK, fontsize=10)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    save(fig, "fig4_rq4_effects")


def main():
    rows = load(DEFAULT_CSV)
    fig1_scanner_view(rows)
    fig2_safe_by_condition(rows)
    fig3_by_type(rows)
    fig4_rq4(rows)
    print(sorted(p.name for p in FIG.iterdir()))


if __name__ == "__main__":
    main()
