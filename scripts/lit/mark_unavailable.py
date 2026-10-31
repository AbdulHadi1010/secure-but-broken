"""Record, for every full-text record still without a readable copy, WHY it is not accessible (manifest 'status').

Reasons were established by checking each record (IEEE Xplore access type via its search service, publisher pages
in Abdul's browser session). These records are excluded as "no full text" (exclusion criterion 3) and listed by name.
Usage: uv run python scripts/lit/mark_unavailable.py
"""

import csv
from pathlib import Path

LR = Path(__file__).resolve().parents[2] / "docs" / "lit-review"
REASONS = {
    "IEEE": "no full text: IEEE Xplore paywalled (accessType locked, checked 2026-10-17)",
    "R0001": "no full text: SciTePress download behind a CAPTCHA (not attempted)",
    "R0182": "no full text: VU Research Portal returns 403 for the thesis PDF",
    "R0665": "open copy exists (MDPI) but the browser blocked the download; Abdul can download it by hand",
    "R0406": "open copy exists (OJS journal) but the browser blocked the download; Abdul can download it by hand",
    "R0015": "open copy exists (ISJEM) but the download is a scripted button the browser blocked",
    "R0069": "no open copy found (journal site without PDF link in OpenAlex; not reached)",
    "R0149": "no full text: IEEE DataPort entry requires an IEEE account",
    "R0332": "no full text: ResearchGate only (login required)",
    "R0229": "no full text: Elsevier (Journal of Network and Computer Applications) paywalled",
    "R0055": "no full text: Springer chapter paywalled",
    "R0219": "no full text: Springer chapter paywalled",
    "R0447": "no full text: Springer chapter paywalled",
    "R0475": "no full text: Springer chapter paywalled",
}


def main() -> None:
    scr = {r["rec_id"]: r for r in csv.DictReader((LR / "screening.csv").open(encoding="utf-8"))}
    p = LR / "fulltext-manifest.csv"
    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    n = 0
    for r in rows:
        if r["status"] == "ok":
            continue
        doi = scr[r["rec_id"]]["doi"]
        reason = REASONS.get(r["rec_id"]) or (REASONS["IEEE"] if doi.startswith("10.1109/") else None)
        if reason:
            r["status"] = reason
            n += 1
        else:
            print("no reason recorded for", r["rec_id"], doi)
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print("reasons set:", n)


if __name__ == "__main__":
    main()
