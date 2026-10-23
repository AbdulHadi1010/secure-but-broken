"""Repairer prompt (FROZEN v1, D-031: docs/prompt/prompt-freeze-v1.md) and output parser.

The prompt contains only what a practitioner would have: the scanner findings and the manifests. It never
contains the misconfiguration type label, the fix class, the reference fix, or any gold content (CLAUDE.md §5).
"""

from __future__ import annotations

import hashlib
import re

import yaml

PROMPT_VERSION = "v1-frozen-2026-10-06"  # D-031: texts frozen; any change is a logged deviation

SYSTEM = (
    "You are a Kubernetes engineer. You fix security findings in Kubernetes manifests. "
    "Reply with the complete corrected manifest set in exactly one ```yaml fenced block containing every "
    "object (separated by ---), and nothing else."
)

KEEP_WORKING = " Keep the application working."  # variant decided by Abdul before P4 (protocol.md)


def build_user_prompt(findings: list[dict], manifests_yaml: str, keep_working: bool) -> str:
    lines = [f"- [{f['tool']}] {f['rule']}: {f['title']} (resource: {f['kind']}/{f['name']})" for f in findings]
    ask = "Fix the findings below." + (KEEP_WORKING if keep_working else "")
    return (
        f"A security scanner reported these findings for the manifests below.\n{chr(10).join(lines)}\n\n"
        f"{ask} Return the full manifest set.\n\n```yaml\n{manifests_yaml.strip()}\n```"
    )


def prompt_hash(system: str, user_template_marker: str = PROMPT_VERSION) -> str:
    return hashlib.sha256((system + "\n" + user_template_marker).encode()).hexdigest()[:16]


FENCE = re.compile(r"```(?:yaml|yml)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


class InvalidOutput(ValueError):
    pass


def removed_objects(docs: list[dict], expected: list[dict]) -> list[list[str]]:
    """Objects of the case the repair left out. Not a format error (D-029): the gates judge the repair."""
    keys = {(d["kind"], d["metadata"].get("name")) for d in docs}
    return sorted([k, n] for k, n in {(d["kind"], d["metadata"]["name"]) for d in expected} - keys)


def parse_response(text: str, expected: list[dict]) -> list[dict]:
    """Format check only (D-029): exactly one yaml block; parses; objects have kind+metadata; no duplicates.
    Objects the model removed are NOT a format error; they are recorded and judged by the gates."""
    blocks = FENCE.findall(text or "")
    if len(blocks) != 1:
        raise InvalidOutput(f"expected exactly one yaml block, found {len(blocks)}")
    try:
        docs = [d for d in yaml.safe_load_all(blocks[0]) if d]
    except yaml.YAMLError as e:
        raise InvalidOutput(f"yaml parse error: {e}") from e
    if not all(isinstance(d, dict) and "kind" in d and "metadata" in d for d in docs):
        raise InvalidOutput("an object lacks kind/metadata")
    keys = [(d["kind"], d["metadata"].get("name")) for d in docs]
    if len(keys) != len(set(keys)):
        raise InvalidOutput("duplicate objects")
    if not docs:
        raise InvalidOutput("empty manifest set")
    return docs
