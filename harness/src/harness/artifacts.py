"""Upload run artifacts to the versioned S3 artifacts bucket (source of truth, CLAUDE.md §6)."""

from __future__ import annotations

from pathlib import Path

import boto3

BUCKET = "sbb-artifacts-<AWS_ACCOUNT_ID>"


def upload_dir(local: Path, prefix: str, profile: str | None = None, region: str = "us-east-1") -> list[str]:
    s3 = boto3.Session(profile_name=profile, region_name=region).client("s3")
    keys = []
    for f in sorted(p for p in local.rglob("*") if p.is_file()):
        key = f"{prefix.rstrip('/')}/{f.relative_to(local).as_posix()}"
        s3.upload_file(str(f), BUCKET, key, ExtraArgs={"ContentType": "application/json"} if f.suffix == ".json" else None)
        keys.append(key)
    return keys
