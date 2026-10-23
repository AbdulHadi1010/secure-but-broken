"""Inter-screener agreement on the blind re-screening samples (protocol step 2).

Compares the first screener's decisions (docs/lit-review/ta_decisions.txt) with the second screener's
(rescreen-second-screener*.txt) on the sampled records. Two levels:
  - stage: forwarded to full text (I or ?) vs excluded (any X)  <- the decision that matters for the review
  - code:  exact same code
Reports raw agreement and Cohen's kappa, and lists every disagreement (to be resolved and logged).
Usage: uv run python scripts/lit/agreement.py
"""

import re
import sys
from collections import Counter
from pathlib import Path

LR = Path(__file__).resolve().parents[2] / "docs" / "lit-review"
PAIRS = [("rescreen-second-screener.txt", "R0001-R0720"), ("rescreen-second-screener-ieee.txt", "R0721-R0847"),
         ("rescreen-second-screener-acm.txt", "R0848-R0859"),
         ("rescreen-second-screener-snowball.txt", "R0860-R0865")]


def read(path: Path) -> dict:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"(R\d{4}) (\S+) ?(.*)", line)
        if m:
            out[m.group(1)] = (m.group(2), m.group(3))
    return out


def kappa(pairs):
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return po, (1.0 if pe == 1 else (po - pe) / (1 - pe))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    first = read(LR / "ta_decisions.txt")
    stage = lambda c: "full-text" if c in ("I", "?") else "excluded"  # noqa: E731
    allpairs = []
    for name, block in PAIRS:
        p = LR / name
        if not p.exists():
            print(f"{block}: {name} not available yet")
            continue
        second = read(p)
        ids = sorted(second)
        allpairs += [(first[i][0], second[i][0], i) for i in ids]
        po_s, k_s = kappa([(stage(first[i][0]), stage(second[i][0])) for i in ids])
        po_c, k_c = kappa([(first[i][0], second[i][0]) for i in ids])
        print(f"{block}: n={len(ids)} | stage agreement {po_s:.1%}, kappa {k_s:.2f} | exact code agreement {po_c:.1%}, kappa {k_c:.2f}")
        for i in ids:
            if stage(first[i][0]) != stage(second[i][0]):
                print(f"  STAGE DISAGREEMENT {i}: first {first[i][0]} ({first[i][1]}) | second {second[i][0]} ({second[i][1]})")
    if allpairs:
        po_s, k_s = kappa([(stage(a), stage(b)) for a, b, _ in allpairs])
        print(f"ALL: n={len(allpairs)} | stage agreement {po_s:.1%}, kappa {k_s:.2f}")


if __name__ == "__main__":
    main()
