"""Safely unpack a ZIP of requested full texts (e.g. from a supervisor) into a new empty folder.

Lists every entry, refuses absolute paths, '..' components and drive letters (zip-slip), extracts only .pdf files
(flattened to their base name) into the target folder, and reports anything skipped. The target folder must not exist
yet. The PDFs are then imported with import_browser_pdfs.py-style title checks by import_requested.py.
Usage: uv run python -I scripts/lit/unpack_requested.py <zip> <new folder>
"""

import sys
import zipfile
from pathlib import Path, PurePosixPath


def main(zpath: str, out: str) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    dest = Path(out)
    if dest.exists():
        raise SystemExit(f"{dest} already exists; choose a new folder")
    z = zipfile.ZipFile(zpath)
    entries = z.infolist()
    unsafe = []
    for i in entries:
        p = PurePosixPath(i.filename.replace("\\", "/"))
        if p.is_absolute() or ".." in p.parts or (p.parts and ":" in p.parts[0]):
            unsafe.append(i.filename)
    print(f"entries: {len(entries)}; unsafe paths: {unsafe}")
    if unsafe:
        raise SystemExit("refusing to extract: unsafe paths")
    dest.mkdir(parents=True)
    pdfs, skipped, seen = 0, [], set()
    for i in entries:
        name = PurePosixPath(i.filename.replace("\\", "/")).name
        if i.is_dir():
            continue
        if not name.lower().endswith(".pdf"):
            skipped.append(i.filename)
            continue
        if name.lower() in seen:
            skipped.append(i.filename + " (duplicate name)")
            continue
        seen.add(name.lower())
        data = z.read(i)
        (dest / name).write_bytes(data)
        pdfs += 1
        print(f"  {len(data):>9}  {i.filename}")
    print(f"extracted {pdfs} PDFs to {dest}; skipped {len(skipped)}: {skipped[:20]}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
