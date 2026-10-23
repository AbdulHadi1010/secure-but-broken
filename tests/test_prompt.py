import json
from pathlib import Path

import pytest
import yaml

from harness.repair.prompt import InvalidOutput, build_user_prompt, parse_response

CASE = Path(__file__).resolve().parents[1] / "cases" / "privileged-frontend"


def _case():
    text = (CASE / "manifests.yaml").read_text(encoding="utf-8")
    return text, [d for d in yaml.safe_load_all(text) if d]


def test_prompt_never_contains_type_label_or_reference_fix():
    text, _ = _case()
    meta = json.loads((CASE / "meta.json").read_text(encoding="utf-8"))
    f = [{"tool": "checkov", "rule": "CKV_K8S_16", "title": "Container should not be privileged",
          "kind": "Deployment", "name": "frontend"}]
    p = build_user_prompt(f, text, keep_working=False)
    assert meta["reference_fix"] not in p
    assert "fix_class" not in p and "privileged-frontend" not in p
    assert "Keep the application working" not in p
    assert "Keep the application working" in build_user_prompt(f, text, keep_working=True)


def test_parser_accepts_full_set():
    text, docs = _case()
    assert len(parse_response(f"here:\n```yaml\n{text}\n```", docs)) == len(docs)


def test_missing_object_is_not_a_format_error_but_is_recorded():  # D-029
    from harness.repair.prompt import removed_objects

    text, docs = _case()
    partial = yaml.safe_dump_all(docs[:-1])
    parsed = parse_response(f"```yaml\n{partial}```", docs)
    last = docs[-1]
    assert removed_objects(parsed, docs) == [[last["kind"], last["metadata"]["name"]]]


def test_parser_rejects_two_blocks_garbage_and_empty():
    text, docs = _case()
    with pytest.raises(InvalidOutput):
        parse_response("```yaml\n\n```", docs)
    with pytest.raises(InvalidOutput):
        parse_response(f"```yaml\n{text}```\n```yaml\n{text}```", docs)
    with pytest.raises(InvalidOutput):
        parse_response("```yaml\n: : bad: [\n```", docs)
    with pytest.raises(InvalidOutput):
        parse_response("no code at all", docs)
