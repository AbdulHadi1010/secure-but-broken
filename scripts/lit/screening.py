"""Build docs/lit-review/screening.csv (record + title/abstract decision) and the blind 20% re-screening sample.

  uv run python scripts/lit/screening.py
Outputs:
  docs/lit-review/screening.csv          every record with ta_code / ta_stage / ta_note
  docs/lit-review/rescreen-sample.csv    20% random sample (seed 20261017), WITHOUT the decisions, for Abdul (protocol step 2)
  prints the PRISMA counts so far
"""

import csv
import random
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LR = ROOT / "docs" / "lit-review"
STAGE = {"I": "full-text", "?": "full-text"}


def main() -> None:
    records = list(csv.DictReader((LR / "records.csv").open(encoding="utf-8")))
    dec = {}
    for line in (LR / "ta_decisions.txt").read_text(encoding="utf-8").splitlines():
        m = re.match(r"(R\d{4}) (\S+) (.*)", line)
        if m:
            if m.group(1) in dec:
                raise SystemExit(f"duplicate decision {m.group(1)}")
            dec[m.group(1)] = (m.group(2), m.group(3))
    missing = [r["rec_id"] for r in records if r["rec_id"] not in dec]
    if missing:
        raise SystemExit(f"records without decision: {missing[:10]}")
    rows = [{**r, "ta_code": dec[r["rec_id"]][0], "ta_stage": STAGE.get(dec[r["rec_id"]][0], "excluded"),
             "ta_note": dec[r["rec_id"]][1]} for r in records]
    fields = list(rows[0].keys())
    with (LR / "screening.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    # Re-screening samples are drawn ONCE per block of records and never redrawn (a redraw would discard work already
    # done by the second screener): block 1 = R0001-R0720 (search strings v1-v1.2), block 2 = R0721-R0847 (IEEE), block 3 = R0848-R0859 (ACM), block 4 = R0860-R0865 (snowballing).
    blocks = [("rescreen-sample.csv", 1, 720), ("rescreen-sample-ieee.csv", 721, 847), ("rescreen-sample-acm.csv", 848, 859),
              ("rescreen-sample-snowball.csv", 860, 865)]
    sizes = []
    for name, lo, hi in blocks:
        path = LR / name
        if not path.exists():
            pool = [r for r in rows if lo <= int(r["rec_id"][1:]) <= hi]
            sample = random.Random(20261017).sample(pool, round(0.2 * len(pool)))
            with path.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["rec_id", "year", "title", "abstract", "your_decision", "your_reason"],
                                   lineterminator="\n")
                w.writeheader()
                for r in sorted(sample, key=lambda r: r["rec_id"]):
                    w.writerow({"rec_id": r["rec_id"], "year": r["year"], "title": r["title"], "abstract": r["abstract"],
                                "your_decision": "", "your_reason": ""})
        sizes.append(sum(1 for _ in csv.DictReader(path.open(encoding="utf-8"))))
    c = Counter(r["ta_code"] for r in rows)
    print(f"records {len(rows)} | to full text {sum(c[k] for k in STAGE)} (I {c['I']}, ? {c['?']}) | "
          f"excluded {sum(v for k, v in c.items() if k not in STAGE)} {dict(sorted((k, v) for k, v in c.items() if k not in STAGE))}"
          f" | re-screen samples {sizes}")


if __name__ == "__main__":
    main()
