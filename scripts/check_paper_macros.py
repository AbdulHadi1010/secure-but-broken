"""Every number macro used in paper/main.tex must be defined in a generated file (paper/numbers.tex for experiment
numbers, paper/lit_numbers.tex for literature-review counts), and every \\cite key must be in paper/references.bib."""

import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
paper = root / "paper"
defined = set()
for name in ("numbers.tex", "lit_numbers.tex"):
    p = paper / name
    if p.exists():
        defined |= set(re.findall(r"\\newcommand\{\\([A-Za-z]+)\}", p.read_text(encoding="utf-8")))
tex = "\n".join(p.read_text(encoding="utf-8") for p in paper.glob("*.tex") if p.name not in ("numbers.tex", "lit_numbers.tex"))
used = set(re.findall(r"\\((?:Wzero|Wone|Peight|Reg|Lit)[A-Za-z]+)", tex))
missing = sorted(used - defined)
bib = (paper / "references.bib").read_text(encoding="utf-8") if (paper / "references.bib").exists() else ""
keys = {k.strip() for grp in re.findall(r"\\cite\{([^}]*)\}", tex) for k in grp.split(",")}
nobib = sorted(k for k in keys if not re.search(r"@\w+\{" + re.escape(k) + ",", bib))
print(f"{len(used)} number macros used, missing: {missing}; {len(keys)} citation keys, not in references.bib: {nobib}")
sys.exit(1 if missing or nobib else 0)
