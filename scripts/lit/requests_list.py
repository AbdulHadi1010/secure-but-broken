"""List the full-text records without a readable copy, for requesting PDFs (e.g. via a supervisor's library access).

Writes docs/lit-review/fulltext-requests.csv and .md (save_as name, publisher, year, title, venue, DOI, link, reason);
requests_docx.py turns the CSV into a Word file.
Usage: uv run python scripts/lit/requests_list.py
"""

import csv
from pathlib import Path

LR = Path(__file__).resolve().parents[2] / "docs" / "lit-review"
PUB = {"10.1109": "IEEE", "10.1007": "Springer", "10.1016": "Elsevier"}


def main() -> None:
    man = {r["rec_id"]: r for r in csv.DictReader((LR / "fulltext-manifest.csv").open(encoding="utf-8"))}
    scr = {r["rec_id"]: r for r in csv.DictReader((LR / "screening.csv").open(encoding="utf-8"))}
    rows = []
    for rid, m in man.items():
        if m["status"] == "ok":
            continue
        x = scr[rid]
        pub = PUB.get(x["doi"].split("/")[0], "other")
        rows.append({"save_as": f"{rid}.pdf", "publisher": pub, "year": x["year"], "title": x["title"], "venue": x["venue"],
                     "doi": x["doi"], "link": f"https://doi.org/{x['doi']}" if x["doi"] else "", "why_missing": m["status"]})
    order = ["IEEE", "Springer", "Elsevier", "other"]
    rows.sort(key=lambda r: (order.index(r["publisher"]), r["save_as"]))
    with (LR / "fulltext-requests.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    counts = ", ".join(f"{p} {sum(r['publisher'] == p for r in rows)}" for p in order)
    md = ["# Full texts we could not access", "",
          "Please save each PDF with the file name in the first column (e.g. `R0041.pdf`); that name links the file "
          "to our records.", "", f"{len(rows)} papers: {counts}.", "",
          "| Save as | Publisher | Year | Title | DOI link |", "|---|---|---|---|---|"]
    for r in rows:
        ref = f"[{r['doi']}]({r['link']})" if r["doi"] else f"(no DOI) {r['venue']}"
        md.append(f"| {r['save_as']} | {r['publisher']} | {r['year']} | {r['title'].replace('|', '/')} | {ref} |")
    (LR / "fulltext-requests.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    print(len(rows), counts)


if __name__ == "__main__":
    main()
