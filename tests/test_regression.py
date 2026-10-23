"""D-030 (F13): a repair must not weaken security controls outside its target."""
import copy

import yaml

from harness.cases import CASES
from harness.checks.intent import protected_services, regression_static
from harness.gold import OUT as GOLD


def _load(p):
    return [d for d in yaml.safe_load_all(p.read_text(encoding="utf-8")) if d]


def test_protected_services_derived_from_gold():
    prot = protected_services(_load(GOLD))
    assert "frontend" not in prot  # gold admits all ingress to the frontend
    assert prot["cartservice"] == 7070 and prot["redis-cart"] == 6379
    assert len(prot) == 10


def test_deleting_deny_all_is_a_regression():  # exactly what the C2-template "safe" repair did
    case = _load(CASES / "netpol-cartservice" / "manifests.yaml")
    repair = [d for d in case if d["metadata"]["name"] != "deny-all"]
    assert regression_static(repair, case) == ["NetworkPolicy 'deny-all' was removed"]


def test_keeping_or_widening_deny_all_is_fine_narrowing_is_not():
    case = _load(CASES / "netpol-cartservice" / "manifests.yaml")
    assert regression_static(case, case) == []
    widened = copy.deepcopy(case)
    next(d for d in widened if d["metadata"]["name"] == "deny-all")["spec"]["podSelector"] = {}
    assert regression_static(widened, case) == []
    narrowed = copy.deepcopy(case)
    next(d for d in narrowed if d["metadata"]["name"] == "deny-all")["spec"]["podSelector"] = {
        "matchLabels": {"app": "frontend"}}
    assert regression_static(narrowed, case) == ["NetworkPolicy 'deny-all' now selects different pods"]


def test_dropping_policy_types_is_a_regression():
    case = _load(CASES / "privileged-frontend" / "manifests.yaml")
    rep = copy.deepcopy(case)
    np = next(d for d in rep if d.get("kind") == "NetworkPolicy" and d["metadata"]["name"] == "cartservice")
    np["spec"]["policyTypes"] = ["Ingress"]
    assert regression_static(rep, case) == ["NetworkPolicy 'cartservice' dropped policy types"]
