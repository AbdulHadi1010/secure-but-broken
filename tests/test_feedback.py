from harness.moderator.feedback import (c1_message, c2_llm, c2_template, evidence_items, gold_diff_tokens,
                                        grounding_check, leakage_check)

REC_BREAKING = {
    "static": {"remaining_target_findings": [], "findings_beyond_gold": []},
    "gates": {"parsed": True, "l1": True, "l2": True, "l3": True, "l4": False, "l5": None, "l6": None, "l7": None},
    "evidence": {"pods": [{"name": "cartservice-1", "phase": "Running", "ready": False, "restarts": 4}],
                 "warning_events": ["cartservice-1  BackOff  Back-off restarting failed container"],
                 "log_tails": {"cartservice-1": "starting\nOOMKilled"}},
}
GOLD = "        memory: 128Mi\n        runAsUser: 10001\n"
CASE = "        memory: 8Mi\n"


def test_c1_silent_when_scanner_clean():
    assert c1_message(REC_BREAKING) is None
    rec = {"static": {"remaining_target_findings": ["checkov:CKV_K8S_16:Deployment/frontend"], "findings_beyond_gold": []}}
    assert "CKV_K8S_16" in c1_message(rec)


def test_template_has_sections_and_evidence_and_no_leak():
    msg = c2_template(REC_BREAKING)
    assert all(s in msg for s in ("What failed", "Evidence", "Constraints still required"))
    assert "[E1]" in msg and "BackOff" in msg
    assert leakage_check(msg, gold_diff_tokens(GOLD, CASE)) == []


def test_leakage_catches_yaml_codeblock_and_gold_values():
    toks = gold_diff_tokens(GOLD, CASE)
    assert "128Mi" in toks and "10001" in toks
    assert leakage_check("What failed\n- x [E1]\nTry ```yaml\nfoo: bar```", toks)
    assert leakage_check("What failed\n- set the memory to 128Mi [E1]", toks)
    assert leakage_check("What failed\n- use user 10001 [E1]", toks)
    assert leakage_check("What failed\n- runAsUser: 0 is wrong [E1]", set())


def test_grounding_requires_citations_to_known_evidence():
    ids = {i for i, _ in evidence_items(REC_BREAKING)}
    good = "What failed\n- pods restart repeatedly [E1]\nEvidence\n[E1] x\nConstraints still required\n- keep secure"
    assert grounding_check(good, ids) == []
    assert grounding_check(good.replace("[E1]\nEvidence", "\nEvidence"), ids)
    assert grounding_check(good.replace("[E1]\nEvidence", "[E99]\nEvidence"), ids)


def test_grouped_citations_count_as_cited():  # D-028: moderator wrote [E1, E2, E3]
    ids = {"E1", "E2", "E3"}
    msg = "What failed\n- journeys fail [E1, E2]\n- load fails [E3]\nEvidence\nx\nConstraints still required\n- y"
    assert grounding_check(msg, ids) == []
    assert grounding_check(msg.replace("[E3]", "[E3, E9]"), ids)


def test_error_lines_from_healthy_pods_reach_the_evidence():  # D-028: the DNS cause hid in Ready pods' logs
    rec = {"gates": {"l4": True, "l5": False, "l6": False},
           "evidence": {"pods": [], "warning_events": [], "log_tails": {},
                        "error_lines": {"cartservice-1": ["dial tcp: lookup redis-cart: i/o timeout"]}},
           "functional": {"checks": {"index 200": {"passes": 0, "fails": 1}}},
           "load": {"error_rate": 0.92, "p95_ms": 2.0, "band": {"error_rate_max": 0.01, "p95_ms_max": 14.5}}}
    text = " ".join(t for _, t in evidence_items(rec))
    assert "lookup redis-cart" in text
    assert "'index' did not return HTTP 200" in text
    assert "must be at most 14.5 ms" in text and "92.0% of requests failed" in text


def test_llm_falls_back_to_template_after_three_bad_tries():
    calls = []
    out = c2_llm(REC_BREAKING, "manifest", gold_diff_tokens(GOLD, CASE),
                 lambda s, u: calls.append(1) or "set memory: 128Mi")
    assert out["source"] == "template_fallback" and len(calls) == 3 and len(out["tries"]) == 3


def test_regression_failures_are_evidence():
    """D-034: an L7 failure caused only by no-regression must not produce an empty Evidence section."""
    rec = {"verdict": "DECEPTIVE_FIX", "gates": {"parsed": True, "l1": True, "l2": True, "l3": True, "l4": True,
                                                 "l5": True, "l6": True, "l7": False},
           "intent": {"pass": False, "static": {"ok": True, "skipped": True}, "runtime_ok": True,
                      "runtime": {"ok": True, "result": "BLOCKED"},
                      "regression": {"ok": False, "policy_failures_other_workloads": [],
                                     "netpol_problems": ["NetworkPolicy 'deny-all' was removed"],
                                     "opened_to_outside": ["redis-cart"], "probe_unknown": []}}}
    texts = [t for _, t in evidence_items(rec)]
    assert any("'deny-all' was removed" in t for t in texts)
    assert any("redis-cart is now reachable" in t for t in texts)
    assert "[E1]" in c2_template(rec) or "E1" in c2_template(rec)
