"""Run Checkov, KICS and kube-score on a manifest file and normalise findings (used by L1, L2, case validation).

A finding is identified as "<tool>:<rule_id>:<Kind>/<name>". Comparing these sets between gold, case and repair
gives L1 (target rules cleared) and L2 (no findings beyond gold).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from harness.deploy.kind import run

CHECKOV = "bridgecrew/checkov@sha256:617c76e3f9b1f7907ebca9abb6b9d746844edcb48e9bd775e4692c69c1c6ac47"  # 3.3.22
KICS = "checkmarx/kics@sha256:3e5a268eb8adda2e5a483c9359ddfc4cd520ab856a7076dc0b1d8784a37e2602"  # 2.1.20
KUBE_SCORE = "zegl/kube-score@sha256:ac4c43ad560af905d66f6bf57b0937c591332e6dbf2167c31193a13b4695ab97"  # 1.20.0
VERSIONS = {"checkov": CHECKOV, "kics": KICS, "kube-score": KUBE_SCORE}


def _checkov(src: Path) -> list[dict]:
    out = run("docker", "run", "--rm", "-v", f"{src.parent}:/src", CHECKOV, "-f", f"/src/{src.name}",
              "--framework", "kubernetes", "-o", "json", "--quiet", "--compact", check=False).stdout
    data = json.loads(out)
    data = data if isinstance(data, list) else [data]
    found = []
    for block in data:
        for f in block["results"]["failed_checks"]:
            # resource looks like "Deployment.boutique.frontend"
            kind, _, name = f["resource"].partition(".")
            name = name.split(".", 1)[-1]
            found.append({"tool": "checkov", "rule": f["check_id"], "kind": kind, "name": name, "title": f["check_name"]})
    return found


def _kics(src: Path) -> list[dict]:
    with tempfile.TemporaryDirectory() as out_dir:
        run("docker", "run", "--rm", "-v", f"{src.parent}:/src", "-v", f"{out_dir}:/out", KICS, "scan",
            "-p", f"/src/{src.name}", "-o", "/out", "--report-formats", "json", "--output-name", "kics",
            "--type", "Kubernetes", "--no-progress", "--ci", check=False)
        data = json.loads((Path(out_dir) / "kics.json").read_text(encoding="utf-8-sig"))
    found = []
    for q in data["queries"]:
        for f in q["files"]:
            found.append({"tool": "kics", "rule": q["query_id"], "kind": f.get("resource_type", ""),
                          "name": f.get("resource_name", ""), "title": q["query_name"], "severity": q["severity"]})
    return found


def _kube_score(src: Path) -> list[dict]:
    out = run("docker", "run", "--rm", "-v", f"{src.parent}:/src", KUBE_SCORE, "score", f"/src/{src.name}",
              "-o", "json", check=False).stdout
    found = []
    for obj in json.loads(out):
        for ch in obj["checks"]:
            if ch.get("skipped") or ch["grade"] > 5:
                continue
            found.append({"tool": "kube-score", "rule": ch["check"]["id"], "kind": obj["type_meta"]["kind"],
                          "name": obj["object_meta"]["name"], "title": ch["check"]["name"]})
    return found


def scan(manifest: Path) -> list[dict]:
    manifest = manifest.resolve()
    return _checkov(manifest) + _kics(manifest) + _kube_score(manifest)


def key(f: dict) -> str:
    return f"{f['tool']}:{f['rule']}:{f['kind']}/{f['name']}"


def keys(findings: list[dict]) -> set[str]:
    return {key(f) for f in findings}
