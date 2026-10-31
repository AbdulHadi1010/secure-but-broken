"""Snowballing, second source: Semantic Scholar references and citations of the included studies.

OpenAlex lists few references for arXiv papers (549 for 92 seeds), so the same round is repeated with Semantic
Scholar's graph API (references + citations per seed), with the same period and keyword filter as snowball.py.
Abstracts of kept candidates are taken from Semantic Scholar. Writes raw/snowball-s2-<date>.jsonl.
Usage: uv run python scripts/lit/snowball_s2.py   (slow without an API key: the public rate limit applies)
"""

from __future__ import annotations

import csv
import json
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import search  # noqa: E402
import snowball as sb  # noqa: E402

API = "https://api.semanticscholar.org/graph/v1/paper/"
FIELDS = "title,abstract,year,publicationDate,externalIds,venue,publicationTypes,authors"


def s2(url: str) -> dict:
    for attempt in range(6):
        try:
            return json.loads(search._get(url))
        except Exception as e:  # noqa: BLE001
            if "404" in str(e):
                return {}
            time.sleep(5 * (attempt + 1))
    return {}


def seed_id(rec: dict) -> str:
    """First identifier Semantic Scholar resolves: DOI, then arXiv id, then a title match (checked)."""
    for pid in (["DOI:" + rec["doi"]] if rec["doi"] else []) + (["ARXIV:" + rec["arxiv"]] if rec["arxiv"] else []):
        d = s2(API + urllib.parse.quote(pid, safe=":") + "?fields=title")
        if d.get("paperId"):
            return d["paperId"]
    d = s2(API + "search/match?" + urllib.parse.urlencode({"query": rec["title"][:250], "fields": "title"}))
    m = (d.get("data") or [{}])[0]
    norm = lambda s: sb.re.sub(r"[^a-z0-9]", "", (s or "").lower())  # noqa: E731
    return m.get("paperId", "") if norm(m.get("title"))[:50] == norm(rec["title"])[:50] else ""


def keep(p: dict) -> bool:
    date = p.get("publicationDate") or (f"{p['year']}-06-30" if p.get("year") else "")
    if not (sb.START <= date <= sb.END):
        return False
    text = (p.get("title") or "") + " " + (p.get("abstract") or "")
    return all(sb.re.search(x, text, sb.re.I) for x in (sb.LLM, sb.IAC, sb.TASK))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    recs = {r["rec_id"]: r for r in csv.DictReader((sb.LR / "screening.csv").open(encoding="utf-8"))}
    with (sb.LR / "fulltext-extraction.tsv").open(encoding="utf-8") as f:
        seeds = [r["rec_id"] for r in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
                 if r["ft_decision"].startswith("include")]
    if len(sys.argv) > 1:  # re-run only these seeds (e.g. ones the rate limit left empty); output gets a suffix
        seeds = [s for s in seeds if s in set(sys.argv[1].split(","))]
    out, missing, n = {}, [], {"references": 0, "citations": 0}
    for sid in seeds:
        pid = seed_id(recs[sid])
        if not pid:
            missing.append(sid)
            continue
        for kind, key in (("references", "citedPaper"), ("citations", "citingPaper")):
            off = 0
            while True:
                d = s2(API + urllib.parse.quote(pid, safe=":") + f"/{kind}?" + urllib.parse.urlencode(
                    {"fields": FIELDS, "limit": 500, "offset": off}))
                rows = d.get("data") or []
                if not rows and off == 0 and not d:
                    missing.append(f"{sid}:{kind}")
                for row in rows:
                    p = row.get(key) or {}
                    n[kind] += 1
                    if p.get("title") and keep(p):
                        ext = p.get("externalIds") or {}
                        out.setdefault(p.get("paperId"), {
                            "source": "snowball-backward" if kind == "references" else "snowball-forward",
                            "id": p.get("paperId"), "seed": sid, "title": p["title"], "abstract": p.get("abstract") or "",
                            "date": p.get("publicationDate") or str(p.get("year") or ""),
                            "authors": [a.get("name") for a in p.get("authors") or []],
                            # add_records/dedupe read arXiv ids from the arXiv DOI
                            "doi": ext.get("DOI") or (f"10.48550/arxiv.{ext['ArXiv']}" if ext.get("ArXiv") else None),
                            "venue": p.get("venue"),
                            "type": ",".join(p.get("publicationTypes") or [])})
                if d.get("next") is None:
                    break
                off = d["next"]
            time.sleep(1.2)
        print(sid, n, len(out), flush=True)
    suffix = "-rerun" if len(sys.argv) > 1 else ""
    path = sb.LR / "raw" / f"snowball-s2-{time.strftime('%Y%m%d')}{suffix}.jsonl"
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for h in out.values():
            f.write(json.dumps(h, ensure_ascii=False) + "\n")
    print(f"seeds {len(seeds)}; not found {len(missing)} {missing}")
    print(f"examined {n['references']} references, {n['citations']} citations; kept {len(out)} -> {path.name}")


if __name__ == "__main__":
    main()
