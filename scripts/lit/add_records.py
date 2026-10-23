"""Add the hits of a later search run to docs/lit-review/records.csv WITHOUT renumbering existing records.

Hits matching an existing record (same DOI, arXiv id or normalised title, as in dedupe.py) only add their source tag;
new records are appended as R0517, R0518, ... (sorted by year, title) and tagged with the run label, so screening
decisions already made stay attached to their ids.
Usage: uv run python scripts/lit/add_records.py <run label> <hits.jsonl> [<hits.jsonl> ...]
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dedupe import OUT, arxiv_id, norm_title  # noqa: E402

FIELDS = ["rec_id", "year", "title", "venue", "type", "doi", "arxiv", "sources", "abstract", "added_in"]


def keys_of(doi: str, arxiv: str, title: str) -> list[str]:
    return [k for k in (f"doi:{doi.lower()}" if doi else None, f"arxiv:{arxiv}" if arxiv else None,
                        f"title:{norm_title(title)}" if norm_title(title) else None) if k]


def main(label: str, paths: list[str]) -> None:
    rows = list(csv.DictReader(OUT.open(encoding="utf-8")))
    for r in rows:
        r.setdefault("added_in", "")
        r["added_in"] = r["added_in"] or "v1"
    index = {k: i for i, r in enumerate(rows) for k in keys_of(r["doi"], r["arxiv"], r["title"])}
    new: list[dict] = []
    new_index: dict[str, int] = {}
    hits = [json.loads(l) for p in paths for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]
    for h in hits:
        ks = keys_of(h.get("doi") or "", arxiv_id(h) or "", h["title"])
        old = next((index[k] for k in ks if k in index), None)
        if old is not None:
            srcs = set(rows[old]["sources"].split("+")) | {h["source"]}
            rows[old]["sources"] = "+".join(sorted(srcs))
            continue
        idx = next((new_index[k] for k in ks if k in new_index), None)
        if idx is None:
            idx = len(new)
            new.append({"year": (h.get("date") or "")[:4], "title": h["title"], "venue": h.get("venue") or "",
                        "type": h.get("type") or "", "doi": h.get("doi") or "", "arxiv": arxiv_id(h) or "",
                        "sources": set(), "abstract": h.get("abstract") or "", "added_in": label})
        r = new[idx]
        r["sources"].add(h["source"])
        if len(h.get("abstract") or "") > len(r["abstract"]):
            r["abstract"] = h["abstract"]
        for k in ks:
            new_index[k] = idx
    new.sort(key=lambda r: (r["year"], norm_title(r["title"])))
    start = len(rows) + 1
    for i, r in enumerate(new):
        rows.append({**r, "rec_id": f"R{start + i:04d}", "sources": "+".join(sorted(r["sources"]))})
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"{label}: hits {len(hits)} -> new records {len(new)} (R{start:04d}-R{start + len(new) - 1:04d}); total {len(rows)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
