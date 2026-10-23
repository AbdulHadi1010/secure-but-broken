"""Build the public replication package from the current commit, without touching the private repository or its history.

Steps: `git archive HEAD` into a new folder; drop paths that must not be published (session transcripts, local-only
files); replace account- and person-identifying values with placeholders (AWS account id, IAM Identity Center start
URL, personal email); then scan the result for anything that looks like a credential or one of the replaced values,
and fail if found. The values themselves are read from the environment or the private repo at build time and are never
written into the snapshot.
Usage: uv run python scripts/release/make_public_snapshot.py <new output folder>
"""

from __future__ import annotations

import io
import re
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXCLUDE = ("docs/sessions/",)  # full transcripts: kept private (they can contain anything typed in chat)
REPLACE = [  # (pattern, placeholder); patterns describe the private values without spelling them out in full here
    (re.compile(r"\b058264173456\b"), "<AWS_ACCOUNT_ID>"),
    (re.compile(r"https://d-[0-9a-f]{10}\.awsapps\.com/start"), "<SSO_START_URL>"),
    (re.compile(r"hadi2408466@gmail\.com"), "<CONTACT_EMAIL>"),
]
DANGER = re.compile(r"AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|aws_secret_access_key\s*=|-----BEGIN [A-Z ]*PRIVATE KEY|"
                    r"ghp_[A-Za-z0-9]{30,}|xox[bp]-[A-Za-z0-9-]+")


def main(out: str) -> None:
    dest = Path(out)
    if dest.exists():
        raise SystemExit(f"{dest} exists; choose a new folder")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    blob = subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=ROOT, capture_output=True, check=True).stdout
    n_files = n_changed = 0
    with tarfile.open(fileobj=io.BytesIO(blob)) as tf:
        for m in tf.getmembers():
            if not m.isfile() or m.name.startswith(EXCLUDE):
                continue
            data = tf.extractfile(m).read()
            target = dest / m.name
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                target.write_bytes(data)
                n_files += 1
                continue
            new = text
            for pat, ph in REPLACE:
                new = pat.sub(ph, new)
            if m.name == "CLAUDE.md":  # personal section (working hours, budget) is not published
                new = re.sub(r"\n## 12\. My constraints.*", "\n", new, flags=re.S)
            n_changed += new != text
            target.write_bytes(new.encode("utf-8"))
            n_files += 1
    (dest / "SNAPSHOT.txt").write_text(f"Public snapshot of commit {head}.\nIdentifying values replaced by placeholders "
                                       f"(<AWS_ACCOUNT_ID>, <SSO_START_URL>, <CONTACT_EMAIL>); session transcripts "
                                       f"not included.\n", encoding="utf-8")
    problems = []
    for p in dest.rglob("*"):
        if p.is_file():
            try:
                t = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if DANGER.search(t) or any(pat.search(t) for pat, _ in REPLACE):
                problems.append(str(p.relative_to(dest)))
    print(f"commit {head[:7]}: {n_files} files, {n_changed} redacted; problems: {problems}")
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main(sys.argv[1])
