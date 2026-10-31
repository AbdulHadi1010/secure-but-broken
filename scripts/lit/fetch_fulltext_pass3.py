"""Third retrieval pass for records still without a full text after pass 2.

Sources: (0) open URLs found by web search, listed in docs/lit-review/fulltext-manual-urls.csv; (1) Zenodo records API for 10.5281/zenodo.* DOIs (open by design); (2) the DOI landing page's
<meta name="citation_pdf_url"> tag, the standard pointer that publishers and repositories (MDPI, DSpace/EPrints
theses, Springer open access, ...) expose for indexing. Only PDFs whose first page contains most of the record's
title words are accepted, so a different document is never used. Nothing behind a login, paywall or bot check is
attempted. Updates docs/lit-review/fulltext-manifest.csv in place.
Usage: uv run --group analysis python scripts/lit/fetch_fulltext_pass3.py
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_fulltext as f1  # noqa: E402
import fetch_fulltext_pass2 as f2  # noqa: E402
import search  # noqa: E402


def page(url: str) -> tuple[str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": search.UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=60, context=search.CTX) as r:
        return r.geturl(), r.read(2_000_000).decode("utf-8", "replace")


def zenodo(doi: str) -> list[tuple[str, str]]:
    m = re.match(r"10\.5281/zenodo\.(\d+)", doi, re.I)
    if not m:
        return []
    try:
        d = json.loads(search._get(f"https://zenodo.org/api/records/{m.group(1)}"))
    except Exception:  # noqa: BLE001
        return []
    return [("Zenodo", f["links"]["self"]) for f in d.get("files", []) if f.get("key", "").lower().endswith(".pdf")]


def landing_pdf(doi: str) -> list[tuple[str, str]]:
    try:
        final, text = page("https://doi.org/" + doi)
    except Exception:  # noqa: BLE001
        return []
    out = []
    for m in re.finditer(r"<meta[^>]+name=[\"']citation_pdf_url[\"'][^>]*>", text, re.I):
        c = re.search(r"content=[\"']([^\"']+)", m.group(0))
        if c:
            out.append((f"citation_pdf_url ({urllib.parse.urlparse(final).netloc})",
                        urllib.parse.urljoin(final, html.unescape(c.group(1)))))
    return out


def title_on_first_page(text: str, title: str) -> bool:
    words = [w for w in f2.norm(title).split() if len(w) > 3]
    first = f2.norm(text[:4000].replace("-\n", "").replace("\n", " "))
    return bool(words) and sum(w in first for w in words) / len(words) >= 0.8


def main() -> None:
    recs = {r["rec_id"]: r for r in csv.DictReader((f1.LR / "screening.csv").open(encoding="utf-8"))}
    rows = list(csv.DictReader(f1.MANIFEST.open(encoding="utf-8")))
    manual = {}
    mpath = f1.LR / "fulltext-manual-urls.csv"  # open copies located by web search (title-checked like the rest)
    if mpath.exists():
        for m in csv.DictReader(mpath.open(encoding="utf-8")):
            manual.setdefault(m["rec_id"], []).append((f"web search ({urllib.parse.urlparse(m['url']).netloc})",
                                                       m["url"]))
    todo = [r for r in rows if r["status"] != "ok" and (recs[r["rec_id"]]["doi"] or r["rec_id"] in manual)]
    if len(sys.argv) > 1:  # optional: only these records
        todo = [r for r in todo if r["rec_id"] in set(sys.argv[1].split(","))]
    for n, row in enumerate(todo, 1):
        rec = recs[row["rec_id"]]
        cands = manual.get(row["rec_id"], [])
        if rec["doi"]:
            cands += zenodo(rec["doi"]) or landing_pdf(rec["doi"])
        for src, url in cands:
            try:
                data = f1.download(url)
                if not data.startswith(b"%PDF"):
                    continue
                pages, text = f1.extract(data)
            except Exception:  # noqa: BLE001
                continue
            if not title_on_first_page(text, rec["title"]):
                row["status"] = "pass3: PDF found but title not on first page (not used)"
                continue
            (f1.FT / f"{row['rec_id']}.pdf").write_bytes(data)
            (f1.FT / f"{row['rec_id']}.txt").write_text(text, encoding="utf-8", newline="\n")
            row.update(source=src, url=url, sha256=hashlib.sha256(data).hexdigest(), pages=pages, chars=len(text),
                       status="ok")
            break
        print(f"{n}/{len(todo)} {row['rec_id']} {row['status']} {row['source']}", flush=True)
        time.sleep(1)
    with f1.MANIFEST.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=f2.FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"full texts: {sum(r['status'] == 'ok' for r in rows)}/{len(rows)} ok")


if __name__ == "__main__":
    main()
