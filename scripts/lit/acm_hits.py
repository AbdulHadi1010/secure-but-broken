"""Turn the ACM Digital Library result list (DOIs) into hit records, with metadata from OpenAlex.

The ACM search was run by Claude in Abdul's own Chrome via the Claude in Chrome extension, after Abdul passed ACM's
bot check and signed in himself (the automated browser pane could not get past the check; it was not bypassed). Its result page gives
truncated abstracts, so only the DOIs are taken from ACM (raw/acm-v1.2-20261017-dois.txt) and each DOI's title,
date, venue, type and full abstract are read from OpenAlex. A DOI unknown to OpenAlex is kept with the title ACM
showed (raw/acm-v1.2-20261017-titles.tsv), so no hit is dropped.
Writes raw/acm-v1.2-20261017.jsonl (source "acm").
Usage: uv run python scripts/lit/acm_hits.py
"""

import csv
import json
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import search  # noqa: E402

RAW = Path(__file__).resolve().parents[2] / "docs" / "lit-review" / "raw"


def main() -> None:
    dois = [d.strip() for d in (RAW / "acm-v1.2-20261017-dois.txt").read_text(encoding="utf-8").splitlines() if d.strip()]
    tpath = RAW / "acm-v1.2-20261017-titles.tsv"
    acm_titles = {r["doi"].lower(): r["title"] for r in csv.DictReader(tpath.open(encoding="utf-8"), delimiter="\t")} \
        if tpath.exists() else {}
    hits, missing = [], []
    for d in dois:
        try:
            w = json.loads(search._get("https://api.openalex.org/works/doi:" + urllib.parse.quote(d)))
        except Exception:  # noqa: BLE001
            w = {}
        if not w.get("id"):
            missing.append(d)
            hits.append({"source": "acm", "id": d, "title": acm_titles.get(d.lower(), ""), "abstract": "", "date": "",
                         "authors": [], "doi": d, "venue": "", "type": ""})
            continue
        inv = w.get("abstract_inverted_index") or {}
        words = sorted((i, wd) for wd, idx in inv.items() for i in idx)
        loc = w.get("primary_location") or {}
        hits.append({"source": "acm", "id": d, "title": w.get("title") or acm_titles.get(d.lower(), ""),
                     "abstract": " ".join(wd for _, wd in words), "date": w.get("publication_date") or "",
                     "authors": [a["author"]["display_name"] for a in w.get("authorships", [])], "doi": d,
                     "venue": (loc.get("source") or {}).get("display_name") or "", "type": w.get("type") or ""})
        time.sleep(0.2)
    with (RAW / "acm-v1.2-20261017.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for h in hits:
            f.write(json.dumps(h, ensure_ascii=False) + "\n")
    print(f"ACM hits {len(hits)}; not in OpenAlex: {len(missing)} {missing}")
    print("without title:", [h["doi"] for h in hits if not h["title"]])


if __name__ == "__main__":
    main()
