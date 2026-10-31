"""Import full-text PDFs that were fetched in the browser (ACM/MDPI block scripted downloads) into the review.

Takes PDFs named <rec_id>.pdf or sbb-<rec_id>.pdf from a folder (default: the user's Downloads) and, optionally,
tar archives of such PDFs; checks the record's title words are on the first page (as pass 3 does), extracts text,
copies PDF + text into docs/lit-review/fulltext/ and updates fulltext-manifest.csv with source and sha256.
Usage: uv run --group analysis python scripts/lit/import_browser_pdfs.py <how fetched, e.g. "Abdul's Chrome session"> [folder]
"""

import csv
import hashlib
import re
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_fulltext as f1  # noqa: E402
import fetch_fulltext_pass2 as f2  # noqa: E402
import fetch_fulltext_pass3 as f3  # noqa: E402


def main(label: str, folder: str) -> None:
    src = Path(folder)
    found: dict[str, bytes] = {}
    for t in src.glob("sbb-*.tar"):
        with tarfile.open(t) as tf:
            for mem in tf.getmembers():
                m = re.match(r"(R\d{4})\.pdf$", Path(mem.name).name)
                if m and mem.isfile():
                    found[m.group(1)] = tf.extractfile(mem).read()
    for p in src.glob("*.pdf"):  # loose PDFs are read last, so a corrected re-download replaces an archived copy
        m = re.match(r"(?:sbb-)?(R\d{4})\.pdf$", p.name)
        if m:
            found[m.group(1)] = p.read_bytes()
    recs = {r["rec_id"]: r for r in csv.DictReader((f1.LR / "screening.csv").open(encoding="utf-8"))}
    rows = list(csv.DictReader(f1.MANIFEST.open(encoding="utf-8")))
    byid = {r["rec_id"]: r for r in rows}
    publisher = {"10.1145/": "ACM DL", "10.3390/": "MDPI", "10.1109/": "IEEE Xplore"}
    for rid, data in sorted(found.items()):
        sha = hashlib.sha256(data).hexdigest()
        if byid.get(rid, {}).get("sha256") == sha:  # already imported, keep its row as it is
            continue
        doi = recs[rid]["doi"]
        source = next((v for k, v in publisher.items() if doi.startswith(k)), "publisher") + f" ({label})"
        if not data.startswith(b"%PDF"):
            print(rid, "not a PDF")
            continue
        pages, text = f1.extract(data)
        if not f3.title_on_first_page(text, recs[rid]["title"]):
            print(rid, "title not on first page - not used")
            continue
        (f1.FT / f"{rid}.pdf").write_bytes(data)
        (f1.FT / f"{rid}.txt").write_text(text, encoding="utf-8", newline="\n")
        row = byid.get(rid)
        if row is None:  # record added after the first retrieval run (e.g. the ACM block)
            row = {k: "" for k in f2.FIELDS} | {"rec_id": rid}
            rows.append(row)
            byid[rid] = row
        row.update(source=source, url="https://doi.org/" + doi, sha256=sha,
                   pages=pages, chars=len(text), status="ok")
        print(rid, "ok", pages, "pages")
    with f1.MANIFEST.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=f2.FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else str(Path.home() / "Downloads"))
