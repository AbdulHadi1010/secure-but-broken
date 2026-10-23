"""One round of backward and forward snowballing on the included studies (protocol screening step 3), via OpenAlex.

For every included record (fulltext-extraction.tsv, ft_decision = include): find its OpenAlex work (DOI, else arXiv
DOI, else title match), take its referenced works (backward) and the works citing it (forward). Candidates are kept
when (a) published 2023-01-01 .. 2026-10-31 (the search period) and (b) title+abstract match the search string's
three keyword groups (LLM AND IaC/config AND task), the same groups as the database searches (v1.2). The kept hits
go to raw/snowball-<date>.jsonl with source "snowball-backward" / "snowball-forward" and the seed record id; they
are then merged with add_records.py and screened like any other record. Seeds not found in OpenAlex are listed.
Usage: uv run python scripts/lit/snowball.py
"""

from __future__ import annotations

import csv
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import search  # noqa: E402

LR = Path(__file__).resolve().parents[2] / "docs" / "lit-review"
START, END = "2023-01-01", "2026-10-31"
LLM = r"(large language model|language model|foundation model|\bLLMs?\b|\bGPT|code model|generative AI)"
IAC = (r"(infrastructure[- ]as[- ]code|\bIaC\b|kubernetes|terraform|\bhelm\b|cloud configuration|misconfiguration"
       r"|ansible|cloudformation|pulumi|puppet|\bchef\b|dockerfile|docker compose|\bk8s\b)")
TASK = r"(repair|fix|remediat|harden|generat|self[- ]heal)"


def get(url: str) -> dict:
    return json.loads(search._get(url))


def abstract(w: dict) -> str:
    inv = w.get("abstract_inverted_index") or {}
    return " ".join(wd for _, wd in sorted((i, wd) for wd, idx in inv.items() for i in idx))


def relevant(w: dict) -> bool:
    d = w.get("publication_date") or ""
    if not (START <= d <= END):
        return False
    text = (w.get("title") or "") + " " + abstract(w)
    return all(re.search(p, text, re.I) for p in (LLM, IAC, TASK))


def find_seed(rec: dict) -> dict:
    for doi in [rec["doi"]] + ([f"10.48550/arxiv.{rec['arxiv']}"] if rec["arxiv"] else []):
        if doi:
            try:
                return get("https://api.openalex.org/works/doi:" + urllib.parse.quote(doi))
            except Exception:  # noqa: BLE001
                pass
    d = get("https://api.openalex.org/works?" + urllib.parse.urlencode({"search": rec["title"][:200], "per-page": 1}))
    w = (d.get("results") or [{}])[0]
    norm = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())  # noqa: E731
    return w if w and norm(w.get("title"))[:60] == norm(rec["title"])[:60] else {}


def hit(w: dict, source: str, seed: str) -> dict:
    loc = w.get("primary_location") or {}
    return {"source": source, "id": w["id"].rsplit("/", 1)[-1], "seed": seed, "title": w.get("title") or "",
            "abstract": abstract(w), "date": w.get("publication_date"),
            "authors": [a["author"]["display_name"] for a in w.get("authorships", [])],
            "doi": (w.get("doi") or "").replace("https://doi.org/", "") or None,
            "venue": (loc.get("source") or {}).get("display_name"), "type": w.get("type")}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    recs = {r["rec_id"]: r for r in csv.DictReader((LR / "screening.csv").open(encoding="utf-8"))}
    with (LR / "fulltext-extraction.tsv").open(encoding="utf-8") as f:
        seeds = [r["rec_id"] for r in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
                 if r["ft_decision"].startswith("include")]
    out, missing, n_back, n_fwd = {}, [], 0, 0
    for sid in seeds:
        w = find_seed(recs[sid])
        if not w.get("id"):
            missing.append(sid)
            continue
        wid = w["id"].rsplit("/", 1)[-1]
        refs = w.get("referenced_works") or []
        for i in range(0, len(refs), 50):  # backward: fetch referenced works in batches
            ids = "|".join(r.rsplit("/", 1)[-1] for r in refs[i:i + 50])
            for rw in get("https://api.openalex.org/works?" + urllib.parse.urlencode(
                    {"filter": f"openalex_id:{ids}", "per-page": 50})).get("results", []):
                n_back += 1
                if relevant(rw):
                    out.setdefault(rw["id"], hit(rw, "snowball-backward", sid))
        page = 1
        while True:  # forward: works citing the seed
            d = get("https://api.openalex.org/works?" + urllib.parse.urlencode(
                {"filter": f"cites:{wid}", "per-page": 200, "page": page}))
            for cw in d.get("results", []):
                n_fwd += 1
                if relevant(cw):
                    out.setdefault(cw["id"], hit(cw, "snowball-forward", sid))
            if len(d.get("results", [])) < 200:
                break
            page += 1
        time.sleep(0.3)
    path = LR / "raw" / f"snowball-{time.strftime('%Y%m%d')}.jsonl"
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for h in out.values():
            f.write(json.dumps(h, ensure_ascii=False) + "\n")
    print(f"seeds {len(seeds)}, not in OpenAlex {len(missing)} {missing}")
    print(f"examined: {n_back} references, {n_fwd} citing works; kept after date+keyword filter: {len(out)} -> {path.name}")


if __name__ == "__main__":
    main()
