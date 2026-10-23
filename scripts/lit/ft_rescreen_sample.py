"""Blind second screening of full-text decisions (protocol screening step 2, applied to the full-text stage).

Draws a 20% random sample (seed 20261023, drawn once; the file is never redrawn) of the records whose full text was
read and decided, and writes docs/lit-review/ft-rescreen-sample.csv with only rec_id, title and the path of the
extracted full text (no decisions). The second screener writes ft-rescreen-second.txt ("<rec_id> <include|exclude>
<criterion> <reason>"); `ft_rescreen_sample.py --agree` compares it with fulltext-extraction.tsv (include/exclude level
and Cohen's kappa) and lists disagreements.
Usage: uv run python scripts/lit/ft_rescreen_sample.py [--agree]
"""

import csv
import random
import re
import sys
from collections import Counter
from pathlib import Path

LR = Path(__file__).resolve().parents[2] / "docs" / "lit-review"
SAMPLE = LR / "ft-rescreen-sample.csv"
SECOND = LR / "ft-rescreen-second.txt"


def first_decisions() -> dict:
    with (LR / "fulltext-extraction.tsv").open(encoding="utf-8") as f:
        return {r["rec_id"]: ("include" if r["ft_decision"].startswith("include") else "exclude")
                for r in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)}


def draw() -> None:
    if SAMPLE.exists():
        print("sample exists, not redrawn:", SAMPLE.name)
        return
    dec = first_decisions()
    scr = {r["rec_id"]: r for r in csv.DictReader((LR / "screening.csv").open(encoding="utf-8"))}
    man = {r["rec_id"]: r for r in csv.DictReader((LR / "fulltext-manifest.csv").open(encoding="utf-8"))}
    # only records whose text is on disk can be re-read by a second screener
    pool = sorted(i for i in dec if (LR / "fulltext" / f"{i}.txt").exists() and man.get(i, {}).get("status") == "ok")
    sample = sorted(random.Random(20261023).sample(pool, round(0.2 * len(dec))))
    with SAMPLE.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["rec_id", "title", "fulltext_path"])
        for i in sample:
            w.writerow([i, scr[i]["title"], str(LR / "fulltext" / f"{i}.txt")])
    print(f"pool {len(pool)} (of {len(dec)} decided); sample {len(sample)} -> {SAMPLE.name}")


def agree() -> None:
    dec = first_decisions()
    second = {}
    for line in SECOND.read_text(encoding="utf-8").splitlines():
        m = re.match(r"(R\d{4})\s+(include|exclude)\b(.*)", line.strip())
        if m:
            second[m.group(1)] = (m.group(2), m.group(3).strip())
    ids = sorted(second)
    pairs = [(dec[i], second[i][0]) for i in ids]
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    kappa = 1.0 if pe == 1 else (po - pe) / (1 - pe)
    print(f"full-text second screening: n={n}, agreement {po:.1%}, kappa {kappa:.2f}")
    for i in ids:
        if dec[i] != second[i][0]:
            print(f"  DISAGREE {i}: first {dec[i]} | second {second[i][0]} {second[i][1][:150]}")


if __name__ == "__main__":
    agree() if "--agree" in sys.argv else draw()
