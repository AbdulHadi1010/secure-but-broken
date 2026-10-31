"""Find and download an open full text for every record forwarded to full-text screening.

Order of sources: (1) arXiv PDF (record has an arXiv id, or OpenAlex knows one), (2) OpenAlex open-access PDF
locations (best_oa_location, then other oa locations). Paywalled records without an open copy are listed as
"no open full text" - never guessed.
PDFs go to docs/lit-review/fulltext/<rec_id>.pdf (git-ignored), extracted text to <rec_id>.txt;
docs/lit-review/fulltext-manifest.csv records rec_id, source, url, sha256, pages, chars, status.
Usage: uv run --group analysis python scripts/lit/fetch_fulltext.py
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import search  # noqa: E402  (reuses the HTTP helper with the CA bundle and polite User-Agent)

ROOT = Path(__file__).resolve().parents[2]
LR = ROOT / "docs" / "lit-review"
FT = LR / "fulltext"
MANIFEST = LR / "fulltext-manifest.csv"


def openalex_lookup(rec: dict) -> dict:
    if rec["doi"]:
        url = "https://api.openalex.org/works/doi:" + urllib.parse.quote(rec["doi"])
    else:
        url = "https://api.openalex.org/works?" + urllib.parse.urlencode({"search": rec["title"][:200], "per-page": 1})
    try:
        d = json.loads(search._get(url))
    except Exception:  # noqa: BLE001
        return {}
    return d["results"][0] if "results" in d and d["results"] else (d if "id" in d else {})


def candidates(rec: dict) -> list[tuple[str, str]]:
    out = []
    if rec["arxiv"]:
        out.append(("arxiv", f"https://arxiv.org/pdf/{rec['arxiv']}"))
    w = openalex_lookup(rec)
    for loc in [w.get("best_oa_location") or {}] + (w.get("locations") or []):
        pdf = (loc or {}).get("pdf_url")
        src = ((loc or {}).get("source") or {}).get("display_name") or "oa"
        if pdf and ("arxiv.org" in pdf or (loc or {}).get("is_oa")):
            if "arxiv.org" in pdf and not rec["arxiv"]:
                out.insert(0, ("arxiv", pdf.replace("/abs/", "/pdf/")))
            elif (src, pdf) not in out:
                out.append((src, pdf))
    seen, uniq = set(), []
    for s, u in out:
        if u not in seen:
            seen.add(u)
            uniq.append((s, u))
    return uniq


def download(url: str) -> bytes:
    """PDF download: two quick attempts (the API helper's five slow retries are meant for API calls)."""
    import urllib.request

    last = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": search.UA})
            with urllib.request.urlopen(req, timeout=60, context=search.CTX) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2)
    raise last


def extract(pdf_bytes: bytes) -> tuple[int, str]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    return len(reader.pages), "\n".join((p.extract_text() or "") for p in reader.pages)


def main() -> None:
    FT.mkdir(parents=True, exist_ok=True)
    rows = [r for r in csv.DictReader((LR / "screening.csv").open(encoding="utf-8")) if r["ta_stage"] == "full-text"]
    prev = {r["rec_id"]: r for r in csv.DictReader(MANIFEST.open(encoding="utf-8"))} if MANIFEST.exists() else {}
    only = set(sys.argv[1].split(",")) if len(sys.argv) > 1 else None  # optional: fetch only these records
    out = []
    for i, rec in enumerate(rows, 1):
        old = prev.get(rec["rec_id"])
        if only is not None and rec["rec_id"] not in only and old:
            out.append(old)  # keep the earlier result (ok or with its recorded reason)
            continue
        if old and old["status"] == "ok":  # includes copies read in the browser (no local .txt)
            out.append(old)
            continue
        row = {"rec_id": rec["rec_id"], "source": "", "url": "", "sha256": "", "pages": "", "chars": "",
               "status": "no open full text"}
        for src, url in candidates(rec):
            try:
                data = download(url)
            except Exception as e:  # noqa: BLE001
                row["status"] = f"download failed: {type(e).__name__} {str(e)[:60]}"
                continue
            if not data.startswith(b"%PDF"):
                row["status"] = "not a PDF at open location"
                continue
            try:
                pages, text = extract(data)
            except Exception as e:  # noqa: BLE001
                row["status"] = f"pdf unreadable: {type(e).__name__}"
                continue
            (FT / f"{rec['rec_id']}.pdf").write_bytes(data)
            (FT / f"{rec['rec_id']}.txt").write_text(text, encoding="utf-8", newline="\n")
            row.update(source=src, url=url, sha256=hashlib.sha256(data).hexdigest(), pages=pages, chars=len(text),
                       status="ok")
            break
        out.append(row)
        print(f"{i}/{len(rows)} {rec['rec_id']} {row['status']} {row['source']}", flush=True)
        time.sleep(1)
    with MANIFEST.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["rec_id", "source", "url", "sha256", "pages", "chars", "status"],
                           lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    ok = sum(r["status"] == "ok" for r in out)
    print(f"full texts: {ok}/{len(out)} ok")


if __name__ == "__main__":
    main()
