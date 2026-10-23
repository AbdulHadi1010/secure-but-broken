"""Redact secrets from a Claude Code session export (zip) before it is stored in docs/sessions/.

The strings to remove are read from a file given on the command line (one per line), so they never appear in this
script, in a shell command or in the command log. Every text member of the zip is rewritten with each string replaced
by "[REDACTED]"; the output zip is then re-read and checked to contain none of the strings.
Usage: uv run python scripts/release/redact_session_export.py <export.zip> <secrets file> <output.zip>
"""

import sys
import zipfile
from pathlib import Path


def main(src: str, secrets_file: str, out: str) -> None:
    secrets = [s for s in Path(secrets_file).read_text(encoding="utf-8").splitlines() if s.strip()]
    if not secrets:
        raise SystemExit("no strings to redact")
    if Path(out).exists():
        raise SystemExit(f"{out} exists")
    hits = 0
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info)
            for s in secrets:
                for enc in (s.encode("utf-8"), s.encode("utf-16-le")):
                    hits += data.count(enc)
                    data = data.replace(enc, b"[REDACTED]")
            zout.writestr(info, data)
    with zipfile.ZipFile(out) as z:
        left = sum(z.read(i).count(s.encode("utf-8")) for i in z.infolist() for s in secrets)
    print(f"replaced {hits} occurrence(s); remaining after check: {left}")
    if left:
        raise SystemExit(1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
