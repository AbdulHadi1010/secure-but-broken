"""Snowballing leads found by hand (cited in an included paper's text, papers behind replication-package records,
known seeds missed by the searches): look each title up in OpenAlex and write raw/snowball-manual-<date>.jsonl.
Leads and how each was found: docs/lit-review/snowball-manual-leads.csv. A lead whose title is not matched is
reported and not added.
Usage: uv run python scripts/lit/snowball_manual.py
"""

import csv
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import search  # noqa: E402
import snowball as sb  # noqa: E402


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    out = []
    for lead in csv.DictReader((sb.LR / "snowball-manual-leads.csv").open(encoding="utf-8")):
        d = json.loads(search._get("https://api.openalex.org/works?" + urllib.parse.urlencode(
            {"search": lead["query"], "per-page": 5})))
        w = next((x for x in d.get("results", []) if norm(x.get("title"))[:50] == norm(lead["query"])[:50]), None)
        if not w:
            print("NOT MATCHED:", lead["query"])
            continue
        h = sb.hit(w, "snowball-manual", "")
        h["found_by"] = lead["found_by"]
        out.append(h)
        print("ok:", w.get("publication_date"), w.get("title"))
        time.sleep(0.3)
    path = sb.LR / "raw" / f"snowball-manual-{time.strftime('%Y%m%d')}.jsonl"
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for h in out:
            f.write(json.dumps(h, ensure_ascii=False) + "\n")
    print(len(out), "->", path.name)


if __name__ == "__main__":
    main()
