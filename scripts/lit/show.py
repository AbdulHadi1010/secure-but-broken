"""Print a slice of docs/lit-review/records.csv for screening (UTF-8 safe).
Usage: uv run python scripts/lit/show.py <from> <to> [abstract_chars]"""

import csv
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
rs = list(csv.DictReader((Path(__file__).resolve().parents[2] / "docs/lit-review/records.csv").open(encoding="utf-8")))
a, b = int(sys.argv[1]), int(sys.argv[2])
n = int(sys.argv[3]) if len(sys.argv) > 3 else 220
for r in rs[a:b]:
    print(r["rec_id"], r["year"], "|", r["title"][:115], "||", " ".join(r["abstract"].split())[:n])
