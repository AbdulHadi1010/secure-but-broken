"""Stop rules and feedback routing of run_chain, with Bedrock and the cluster replaced by fakes."""

import json

import pytest

import harness.orchestrate.loop as loop

CASE = "privileged-frontend"


class FakeBedrock:
    def __init__(self):
        self.calls = []


def _fake_converse(case_yaml):
    def converse(br, model_id, system, messages, temperature, max_tokens=16000):
        br.calls.append({"model": model_id, "n_messages": len(messages), "last": messages[-1]["text"][:80]})
        text = "moderator says nothing useful" if model_id == loop.MODELS["moderator"]["model_id"] else f"```yaml\n{case_yaml}\n```"
        return {"text": text, "input_tokens": 10, "output_tokens": 5, "stop_reason": "end_turn", "wall_s": 0.1,
                "temperature_sent": temperature, "reasoning": None}
    return converse


def _gates(l1, l2, rest):
    g = {"parsed": True, "l1": l1, "l2": l2, "l3": rest, "l4": rest, "l5": rest, "l6": rest, "l7": rest}
    return g


@pytest.fixture
def chain(monkeypatch, tmp_path):
    case_yaml = (loop.CASES / CASE / "manifests.yaml").read_text(encoding="utf-8")
    br = FakeBedrock()
    monkeypatch.setattr(loop.bedrock, "client", lambda profile=None: br)
    monkeypatch.setattr(loop.bedrock, "converse", _fake_converse(case_yaml))
    monkeypatch.setattr(loop, "case_findings", lambda d, m: [{"tool": "checkov", "rule": "CKV_K8S_16", "title": "t",
                                                              "kind": "Deployment", "name": "frontend"}])
    monkeypatch.setattr(loop.kind, "versions", lambda: {})
    monkeypatch.setattr(loop.kind, "ROOT", tmp_path)
    monkeypatch.setattr(loop, "_git", lambda: "test")
    script = []

    def fake_attempt(docs, meta, out_dir):
        verdict, gates = script.pop(0)
        (out_dir / "repair.yaml").write_text(case_yaml, encoding="utf-8")
        rec = {"verdict": verdict, "gates": gates, "static": {"remaining_target_findings": ["checkov:CKV_K8S_16:x"],
                                                               "findings_beyond_gold": []}}
        (out_dir / "attempt.json").write_text(json.dumps(rec), encoding="utf-8")
        return rec

    monkeypatch.setattr(loop, "run_attempt", fake_attempt)
    return br, script


def test_c0_single_iteration(chain):
    br, script = chain
    script += [("NOT_FIXED", _gates(False, False, None))]
    s = loop.run_chain(CASE, "deepseek-v3-2", "C0", upload=False)
    assert s["n_iterations"] == 1 and len(br.calls) == 1


def test_c1_stops_when_scanner_clean_even_if_breaking(chain):
    br, script = chain
    script += [("NOT_FIXED", _gates(False, False, None)), ("BREAKING_FIX", _gates(True, True, False))]
    s = loop.run_chain(CASE, "deepseek-v3-2", "C1", upload=False)
    assert s["n_iterations"] == 2 and s["final_verdict"] == "BREAKING_FIX"
    assert "The scanner still reports" in br.calls[1]["last"]


def test_c2_template_continues_past_scanner_clean_until_safe(chain):
    br, script = chain
    script += [("BREAKING_FIX", _gates(True, True, False)), ("SAFE_FIX", _gates(True, True, True))]
    s = loop.run_chain(CASE, "deepseek-v3-2", "C2-template", upload=False)
    assert s["n_iterations"] == 2 and s["final_verdict"] == "SAFE_FIX"
    assert br.calls[1]["last"].startswith("What failed")


def test_c2_llm_calls_moderator_and_falls_back(chain):
    br, script = chain
    script += [("BREAKING_FIX", _gates(True, True, False))] * 5
    s = loop.run_chain(CASE, "deepseek-v3-2", "C2-LLM", upload=False)
    assert s["n_iterations"] == 5
    mod_calls = [c for c in br.calls if c["model"] == loop.MODELS["moderator"]["model_id"]]
    assert len(mod_calls) == 4 * 3  # 4 feedback rounds x (1 try + 2 regenerations), ungrounded fake -> fallback
    assert {it.get("feedback_source") for it in s["iterations"][:-1]} == {"template_fallback"}
