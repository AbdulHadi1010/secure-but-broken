"""Export the study's run artifacts from the S3 bucket for the archived replication package (Zenodo).

  --measure            list every object (read-only) and print object count and size per top-level prefix
  --download <folder>  download the prefixes in KEEP into a new folder, then replace account-identifying values with the
                       same placeholders as make_public_snapshot.py and scan the result for credentials
Needs AWS_PROFILE=secure-but-broken with a valid SSO session. Read-only on AWS: it never writes, deletes or changes
any object.
Usage: uv run python scripts/release/export_run_data.py --measure
       uv run python scripts/release/export_run_data.py --download <new folder>
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_public_snapshot import DANGER, REPLACE  # noqa: E402

BUCKET = "sbb-artifacts-<AWS_ACCOUNT_ID>"
KEEP = ("chains/", "baseline/", "cases/", "pilot/", "p8/", "validation/")  # top-level prefixes in the package


def objects(s3):
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET):
        yield from page.get("Contents", [])


def measure(s3) -> None:
    size, count = defaultdict(int), defaultdict(int)
    for o in objects(s3):
        top = o["Key"].split("/", 1)[0] + "/"
        size[top] += o["Size"]
        count[top] += 1
    for top in sorted(size, key=lambda k: -size[k]):
        print(f"{top:<28} {count[top]:>8} objects {size[top] / 1e9:8.3f} GB {'(kept)' if top in KEEP else ''}")
    kept = sum(v for k, v in size.items() if k in KEEP)
    print(f"total {sum(size.values()) / 1e9:.3f} GB; kept for the package {kept / 1e9:.3f} GB")


def download(s3, out: str) -> None:
    dest = Path(out)
    if dest.exists():
        raise SystemExit(f"{dest} exists; choose a new folder")
    n = bad = 0
    for o in objects(s3):
        if not o["Key"].startswith(KEEP) or o["Key"].endswith("/"):
            continue
        body = s3.get_object(Bucket=BUCKET, Key=o["Key"])["Body"].read()
        target = dest / o["Key"]
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            text = body.decode("utf-8")
            for pat, ph in REPLACE:
                text = pat.sub(ph, text)
            if DANGER.search(text):
                bad += 1
                print("credential-like content, NOT exported:", o["Key"])
                continue
            target.write_text(text, encoding="utf-8", newline="")
        except UnicodeDecodeError:
            target.write_bytes(body)
        n += 1
    print(f"exported {n} objects to {dest}; withheld {bad}")


if __name__ == "__main__":
    s3 = boto3.Session(profile_name="secure-but-broken").client("s3")
    if sys.argv[1:2] == ["--measure"]:
        measure(s3)
    elif sys.argv[1:2] == ["--download"]:
        download(s3, sys.argv[2])
    else:
        raise SystemExit(__doc__)
