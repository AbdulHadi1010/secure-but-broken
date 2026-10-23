"""Read/write docs/lit-review/fulltext-extraction.tsv safely.

The file is plain tab-separated text written with printf; evidence cells start with quotation marks, so csv quoting
must be off (QUOTE_NONE) or the reader would merge cells. Fields never contain tabs or newlines.
"""

import csv
from pathlib import Path

PATH = Path(__file__).resolve().parents[2] / "docs" / "lit-review" / "fulltext-extraction.tsv"


def read() -> list[dict]:
    with PATH.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE))


def write(rows: list[dict]) -> None:
    fields = list(rows[0].keys())
    with PATH.open("w", encoding="utf-8", newline="") as f:
        f.write("\t".join(fields) + "\n")
        for r in rows:
            f.write("\t".join(r[k] for k in fields) + "\n")


def set_duplicate(keep: str, drop: str, keep_reason: str, drop_reason: str) -> None:
    """Move the extracted data to the record that is kept (E3: keep the latest version) and mark the other."""
    rows = read()
    a = next(r for r in rows if r["rec_id"] == drop)
    b = next(r for r in rows if r["rec_id"] == keep)
    if not b["ft_decision"].startswith("include"):
        b.update({k: v for k, v in a.items() if k != "rec_id"})
    b["ft_decision"], b["ft_reason"] = "include", keep_reason
    a["ft_decision"], a["ft_reason"] = drop_reason, f"same study as {keep}"
    write(rows)


if __name__ == "__main__":
    set_duplicate("R0530", "R0544",
                  "large usage study of an LLM Ansible code-completion service; peer-reviewed ASE 2024 version "
                  "(latest, kept per E3); R0544 is its earlier arXiv version",
                  "exclude (E3 duplicate: earlier arXiv version of R0530, ASE 2024)")
    print("ok")
