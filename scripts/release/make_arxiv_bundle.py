"""Build an arXiv source bundle from paper/ (after scripts/build_paper.ps1 has produced main.bbl).

Copies main.tex and its generated inputs, the compiled bibliography (main.bbl; arXiv does not run BibTeX) and the
figures used (from analysis/figures/) into one flat folder, points \\graphicspath at it, removes LaTeX comments (arXiv
publishes the sources), and writes arxiv-<date>.tar.gz next to the folder. Compile-test the folder before uploading.
Usage: uv run python scripts/release/make_arxiv_bundle.py <new output folder>
"""

from __future__ import annotations

import re
import shutil
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAPER, FIG = ROOT / "paper", ROOT / "analysis" / "figures"
INPUTS = ["main.tex", "numbers.tex", "lit_numbers.tex", "gap_table.tex", "main.bbl"]


def strip_comments(tex: str) -> str:
    out = []
    for line in tex.splitlines():
        if line.lstrip().startswith("%"):
            continue
        line = re.sub(r"(?<!\\)%.*$", "", line)  # unescaped % to end of line
        out.append(line.rstrip())
    return "\n".join(out) + "\n"


def main(out: str) -> None:
    dest = Path(out)
    if dest.exists():
        raise SystemExit(f"{dest} exists; choose a new folder")
    if not (PAPER / "main.bbl").exists():
        raise SystemExit("paper/main.bbl missing: run scripts/build_paper.ps1 first")
    dest.mkdir(parents=True)
    for name in INPUTS:
        text = (PAPER / name).read_text(encoding="utf-8")
        if name.endswith(".tex"):
            text = strip_comments(text)
        if name == "main.tex":
            text = text.replace(r"\graphicspath{{../analysis/figures/}}", r"\graphicspath{{./}}")
        (dest / name).write_text(text, encoding="utf-8", newline="\n")
    figs = sorted(set(re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", (PAPER / "main.tex").read_text(encoding="utf-8"))))
    for f in figs:
        shutil.copy2(FIG / f, dest / Path(f).name)
    tgz = dest.parent / f"arxiv-{time.strftime('%Y%m%d')}.tar.gz"
    with tarfile.open(tgz, "w:gz") as tf:
        for p in sorted(dest.iterdir()):
            tf.add(p, arcname=p.name)
    print(f"{len(INPUTS)} sources + {len(figs)} figures -> {dest} and {tgz.name}")


if __name__ == "__main__":
    main(sys.argv[1])
