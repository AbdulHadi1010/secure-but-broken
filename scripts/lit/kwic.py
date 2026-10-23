"""Keyword-in-context search in one extracted full text (reading aid for full-text screening).
Usage: uv run python scripts/lit/kwic.py R0123 "regex" [max_hits] [width]
"""

import re
import sys
from pathlib import Path

LR = Path(__file__).resolve().parents[2] / "docs" / "lit-review"


def main(rec_id: str, pat: str, k: int = 12, w: int = 200) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    flat = " ".join((LR / "fulltext" / f"{rec_id}.txt").read_text(encoding="utf-8").split())
    last = -10_000
    shown = 0
    for m in re.finditer(pat, flat, re.I):
        if m.start() - last < w:
            continue
        last = m.start()
        print("·", flat[max(0, m.start() - w): m.start() + w])
        shown += 1
        if shown >= k:
            break
    print(f"[{shown} shown]")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], *(int(a) for a in sys.argv[3:5]))
