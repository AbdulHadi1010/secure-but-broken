"""PRISMA 2020-style flow diagram for the literature review, drawn from the data files (no hand-typed numbers).

Counts: records per database = records whose 'sources' contain that database (all string versions merged); duplicates
removed = sum over databases - unique records from databases; snowballing records = added_in 'snowball'; title/abstract
exclusions from screening.csv; full-text retrieval from fulltext-manifest.csv; full-text exclusions from
fulltext-extraction.tsv (codes mapped to the protocol criteria as in prisma.py).
Writes analysis/figures/prisma.{png,pdf} and docs/lit-review/prisma-counts.json.
Usage: uv run --group analysis python scripts/lit/prisma_figure.py
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
LR = ROOT / "docs" / "lit-review"
FIG = ROOT / "analysis" / "figures"
SURFACE, INK, INK2, EDGE = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984"
DBS = [("arxiv", "arXiv"), ("openalex", "OpenAlex"), ("ieee", "IEEE Xplore"), ("acm", "ACM DL")]
TA_LABEL = {"X1": "not an LLM producing/repairing config", "X2": "LLM only detects/explains",
            "X3": "no empirical evaluation", "X4": "application code", "X5": "not English", "X6": "not a paper"}
FT_LABEL = {"IC2": "no empirical evaluation", "IC1": "not an LLM producing/repairing config",
            "E3": "duplicate version (latest kept)", "E1": "LLM only detects/explains"}


def counts() -> dict:
    recs = list(csv.DictReader((LR / "records.csv").open(encoding="utf-8")))
    db_recs = [r for r in recs if r["added_in"] != "snowball"]
    per_db = {lab: sum(key in r["sources"].split("+") for r in db_recs) for key, lab in DBS}
    scr = list(csv.DictReader((LR / "screening.csv").open(encoding="utf-8")))
    ta = Counter(r["ta_code"] for r in scr if r["ta_stage"] != "full-text")
    sought = [r["rec_id"] for r in scr if r["ta_stage"] == "full-text"]
    man = {r["rec_id"]: r for r in csv.DictReader((LR / "fulltext-manifest.csv").open(encoding="utf-8"))}
    got = [i for i in sought if man.get(i, {}).get("status") == "ok"]
    with (LR / "fulltext-extraction.tsv").open(encoding="utf-8") as f:
        ext = [r for r in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE) if r["rec_id"] in set(got)]
    alias = {"X1": "IC1", "X3": "IC2"}
    ft = Counter()
    for r in ext:
        if not r["ft_decision"].startswith("include"):
            m = re.search(r"(?<![A-Za-z])(X[0-9]|IC[0-9]|E[0-9])(?![0-9])", r["ft_decision"] + " " + r["ft_reason"])
            ft[alias.get(m.group(1), m.group(1)) if m else "?"] += 1
    return {"per_database": per_db, "db_sum": sum(per_db.values()), "unique_db": len(db_recs),
            "duplicates_removed": sum(per_db.values()) - len(db_recs),
            "snowballing": sum(r["added_in"] == "snowball" for r in recs), "screened": len(scr),
            "ta_excluded": dict(ta), "ta_excluded_total": sum(ta.values()), "sought": len(sought),
            "not_retrieved": len(sought) - len(got), "assessed": len(got), "decided": len(ext),
            "ft_excluded": dict(ft), "ft_excluded_total": sum(ft.values()),
            "included": sum(r["ft_decision"].startswith("include") for r in ext)}


def box(ax, x, y, w, h, text, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.01,rounding_size=0.012", fc="white", ec=EDGE, lw=0.8))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=7.4, color=INK,
            fontweight="bold" if bold else "normal", linespacing=1.35, wrap=True)


def arrow(ax, x1, y1, x2, y2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops={"arrowstyle": "-|>", "color": INK2, "lw": 0.8})


def main() -> None:
    c = counts()
    (LR / "prisma-counts.json").write_text(json.dumps(c, indent=2) + "\n", encoding="utf-8")
    fig, ax = plt.subplots(figsize=(7.2, 7.6))
    fig.patch.set_facecolor(SURFACE)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    L, W, R, RW, H = 0.03, 0.46, 0.55, 0.43, 0.105
    dbline = "\n".join(f"{k}: {v}" for k, v in c["per_database"].items())
    box(ax, L, 0.86, W, 0.12, f"Records from databases ({c['db_sum']})\n{dbline}", bold=False)
    box(ax, R, 0.86, RW, 0.12, f"Duplicates removed: {c['duplicates_removed']}\n(one record per study across databases\nand search-string versions v1-v1.2)")
    box(ax, R, 0.73, RW, 0.09, f"Records from snowballing: {c['snowballing']}\n(backward + forward, one round)")
    box(ax, L, 0.55, W, H, f"Records screened (title/abstract)\n{c['screened']} ({c['unique_db']} + {c['snowballing']})")
    ta = "\n".join(f"{k} {TA_LABEL.get(k, k)}: {v}" for k, v in sorted(c["ta_excluded"].items()))
    box(ax, R, 0.475, RW, 0.215, f"Excluded: {c['ta_excluded_total']}\n{ta}")
    box(ax, L, 0.38, W, H, f"Full texts sought\n{c['sought']}")
    box(ax, R, 0.36, RW, 0.08, f"Not retrievable: {c['not_retrieved']}\n(paywalled or blocked; listed by name)")
    box(ax, L, 0.21, W, H, f"Full texts assessed\n{c['assessed']}")
    ft = "\n".join(f"{k} {FT_LABEL.get(k, k)}: {v}" for k, v in sorted(c["ft_excluded"].items()))
    box(ax, R, 0.15, RW, 0.16, f"Excluded: {c['ft_excluded_total']}\n{ft}")
    box(ax, L, 0.03, W, H, f"Studies included\n{c['included']}", bold=True)
    cx = L + W / 2
    arrow(ax, L + W, 0.92, R, 0.92)
    arrow(ax, cx, 0.86, cx, 0.55 + H)
    arrow(ax, R, 0.775, L + W, 0.55 + H - 0.01)
    arrow(ax, L + W, 0.59, R, 0.57)
    arrow(ax, cx, 0.55, cx, 0.38 + H)
    arrow(ax, L + W, 0.43, R, 0.40)
    arrow(ax, cx, 0.38, cx, 0.21 + H)
    arrow(ax, L + W, 0.26, R, 0.23)
    arrow(ax, cx, 0.21, cx, 0.03 + H)
    FIG.mkdir(exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(FIG / f"prisma.{ext}", dpi=300, bbox_inches="tight")
    print(json.dumps(c))


if __name__ == "__main__":
    main()
