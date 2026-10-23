"""Second retrieval pass for records that fetch_fulltext.py could not get (status != ok in the manifest).

Extra sources, in order: (1) arXiv title search (a preprint version of a paywalled paper), (2) Semantic Scholar
openAccessPdf (by DOI, else by title). A candidate is accepted only when its title matches the record's title
(normalised similarity >= 0.92), so a different paper is never used. Records still without a copy stay listed as
"no open full text" (protocol: excluded as no full text, E3) - never guessed.
Updates docs/lit-review/fulltext-manifest.csv in place (source column says which pass found it).
Usage: uv run --group analysis python scripts/lit/fetch_fulltext_pass2.py
"""

from __future__ import annotations

import csv
import difflib
import hashlib
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_fulltext as f1  # noqa: E402
import search  # noqa: E402

FIELDS = ["rec_id", "source", "url", "sha256", "pages", "chars", "status"]


def norm(t: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", t.lower())).strip()


def same_title(a: str, b: str) -> bool:
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio() >= 0.92


def arxiv_by_title(title: str) -> list[tuple[str, str]]:
    q = " AND ".join(f"ti:{w}" for w in norm(title).split()[:12] if len(w) > 3)
    url = "http://export.arxiv.org/api/query?" + urllib.parse.urlencode({"search_query": q, "max_results": 5})
    try:
        xml = search._get(url).decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return []
    out = []
    for entry in xml.split("<entry>")[1:]:
        t = re.search(r"<title>(.*?)</title>", entry, re.S)
        i = re.search(r"<id>http://arxiv.org/abs/(.*?)</id>", entry)
        if t and i and same_title(" ".join(t.group(1).split()), title):
            out.append(("arxiv (title search)", f"https://arxiv.org/pdf/{i.group(1)}"))
    return out


def s2(rec: dict) -> list[tuple[str, str]]:
    base = "https://api.semanticscholar.org/graph/v1/paper/"
    fields = "title,openAccessPdf,externalIds"
    try:
        if rec["doi"]:
            d = json.loads(search._get(base + "DOI:" + urllib.parse.quote(rec["doi"]) + "?fields=" + fields))
        else:
            r = json.loads(search._get(base + "search/match?" + urllib.parse.urlencode({"query": rec["title"][:250],
                                                                                         "fields": fields})))
            d = (r.get("data") or [{}])[0]
    except Exception:  # noqa: BLE001
        return []
    out = []
    if d.get("title") and not same_title(d["title"], rec["title"]):
        return []
    ax = (d.get("externalIds") or {}).get("ArXiv")
    if ax:
        out.append(("arxiv (via Semantic Scholar)", f"https://arxiv.org/pdf/{ax}"))
    pdf = (d.get("openAccessPdf") or {}).get("url")
    if pdf:
        out.append(("Semantic Scholar openAccessPdf", pdf))
    return out


def main() -> None:
    lr = f1.LR
    recs = {r["rec_id"]: r for r in csv.DictReader((lr / "screening.csv").open(encoding="utf-8"))}
    rows = list(csv.DictReader(f1.MANIFEST.open(encoding="utf-8")))
    todo = [r for r in rows if r["status"] != "ok"]
    for n, row in enumerate(todo, 1):
        rec = recs[row["rec_id"]]
        cands = arxiv_by_title(rec["title"])
        time.sleep(3)  # arXiv API etiquette
        cands += [c for c in s2(rec) if c not in cands]
        time.sleep(1)
        for src, url in cands:
            try:
                data = f1.download(url)
            except Exception as e:  # noqa: BLE001
                row["status"] = f"pass2 download failed: {type(e).__name__}"
                continue
            if not data.startswith(b"%PDF"):
                continue
            try:
                pages, text = f1.extract(data)
            except Exception:  # noqa: BLE001
                continue
            (f1.FT / f"{row['rec_id']}.pdf").write_bytes(data)
            (f1.FT / f"{row['rec_id']}.txt").write_text(text, encoding="utf-8", newline="\n")
            row.update(source=src, url=url, sha256=hashlib.sha256(data).hexdigest(), pages=pages, chars=len(text),
                       status="ok")
            break
        print(f"{n}/{len(todo)} {row['rec_id']} {row['status']} {row['source']}", flush=True)
    with f1.MANIFEST.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"full texts: {sum(r['status'] == 'ok' for r in rows)}/{len(rows)} ok")


if __name__ == "__main__":
    main()
