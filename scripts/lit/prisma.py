"""PRISMA-style counts for the literature review, computed from the files (never typed by hand).

Reads raw/*.jsonl (hits per source and string version), records.csv (unique records), screening.csv (title/abstract
decisions), fulltext-manifest.csv (retrieval) and fulltext-extraction.tsv (full-text decisions).
Usage: uv run python scripts/lit/prisma.py
"""

import csv
import re
import sys
from collections import Counter
from pathlib import Path

LR = Path(__file__).resolve().parents[2] / "docs" / "lit-review"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    print("Identification (hits per raw file):")
    total = 0
    for p in sorted((LR / "raw").glob("*.jsonl")):
        n = sum(1 for line in p.open(encoding="utf-8") if line.strip())
        total += n
        print(f"  {p.name}: {n}")
    print(f"  total hits (overlapping string versions included): {total}")
    recs = list(csv.DictReader((LR / "records.csv").open(encoding="utf-8")))
    print(f"Unique records after de-duplication: {len(recs)}")
    scr = list(csv.DictReader((LR / "screening.csv").open(encoding="utf-8")))
    c = Counter(r["ta_code"] for r in scr)
    ft = [r for r in scr if r["ta_stage"] == "full-text"]
    print(f"Title/abstract: excluded {len(scr) - len(ft)} {dict(sorted((k, v) for k, v in c.items() if k not in 'I?'))};"
          f" to full text {len(ft)} (I {c['I']}, ? {c['?']})")
    man = {r["rec_id"]: r for r in csv.DictReader((LR / "fulltext-manifest.csv").open(encoding="utf-8"))}
    ok = [i for i in man if man[i]["status"] == "ok"]
    print(f"Full text retrieved: {len(ok)}; not accessible: {len(man) - len(ok)}")
    print("  retrieved by source:", dict(Counter(man[i]["source"].split(" (")[0] for i in ok)))
    ext = list(csv.DictReader((LR / "fulltext-extraction.tsv").open(encoding="utf-8"), delimiter="\t",
                                quoting=csv.QUOTE_NONE))

    # Full-text exclusions are reported against the protocol criteria; the screening shorthand X1 = inclusion
    # criterion 1 not met (IC1), X3 = no empirical evaluation (IC2).
    alias = {"X1": "IC1", "X3": "IC2"}

    def code(r: dict) -> str:
        if r["ft_decision"].startswith("include"):
            return "include"
        m = re.search(r"(?<![A-Za-z])(X[0-9]|IC[0-9]|E[0-9])(?![0-9])", r["ft_decision"] + " " + r["ft_reason"])
        return "exclude " + (alias.get(m.group(1), m.group(1)) if m else "?")

    dec = Counter(code(r) for r in ext)
    print(f"Full-text decisions: {len(ext)} of {len(ok)} retrieved; {dict(dec)}")
    missing = sorted(set(ok) - {r["rec_id"] for r in ext})
    if missing:
        print("  retrieved but not yet decided:", " ".join(missing))


if __name__ == "__main__":
    main()
