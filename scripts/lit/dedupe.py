"""Merge the raw search hits into unique records (docs/lit-review/records.csv), protocol step "after duplicates".

Duplicate = same DOI, same arXiv id (an OpenAlex work whose DOI is 10.48550/arXiv.<id> is the arXiv preprint), or the
same normalised title. The record keeps every source it was found in and the longest abstract.
Usage: uv run python scripts/lit/dedupe.py docs/lit-review/raw/arxiv-20261017.jsonl docs/lit-review/raw/openalex-20261017.jsonl
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "lit-review" / "records.csv"


def norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def arxiv_id(h: dict) -> str | None:
    if h["source"] == "arxiv":
        return re.sub(r"v\d+$", "", h["id"])
    m = re.match(r"10\.48550/arxiv\.(.+)", (h.get("doi") or "").lower())
    return m.group(1) if m else None


def main(paths: list[str]) -> None:
    hits = [json.loads(l) for p in paths for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]
    records: list[dict] = []
    keys: dict[str, int] = {}
    for h in hits:
        ks = [k for k in (f"doi:{(h.get('doi') or '').lower()}" if h.get("doi") else None,
                          f"arxiv:{arxiv_id(h)}" if arxiv_id(h) else None,
                          f"title:{norm_title(h['title'])}" if norm_title(h["title"]) else None) if k]
        idx = next((keys[k] for k in ks if k in keys), None)
        if idx is None:
            idx = len(records)
            records.append({"title": h["title"], "abstract": h.get("abstract") or "", "year": (h.get("date") or "")[:4],
                            "doi": h.get("doi") or "", "arxiv": arxiv_id(h) or "", "venue": h.get("venue") or "",
                            "type": h.get("type") or "", "sources": set()})
        r = records[idx]
        r["sources"].add(h["source"])
        if len(h.get("abstract") or "") > len(r["abstract"]):
            r["abstract"] = h["abstract"]
        for f in ("doi", "venue", "type"):
            r[f] = r[f] or (h.get(f) or "")
        r["arxiv"] = r["arxiv"] or (arxiv_id(h) or "")
        for k in ks:
            keys[k] = idx
    records.sort(key=lambda r: (r["year"], norm_title(r["title"])))
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["rec_id", "year", "title", "venue", "type", "doi", "arxiv", "sources",
                                          "abstract"], lineterminator="\n")
        w.writeheader()
        for i, r in enumerate(records, 1):
            w.writerow({**r, "rec_id": f"R{i:04d}", "sources": "+".join(sorted(r["sources"]))})
    print(f"hits {len(hits)} -> unique records {len(records)} -> {OUT}")


if __name__ == "__main__":
    main(sys.argv[1:])
