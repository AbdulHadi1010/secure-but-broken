from harness.gold import build, harden
from harness.injectors import REGISTRY, find_deployment, main_container


def test_privileged_injects_exactly_one_container_change():
    gold = harden(build())
    case = REGISTRY["privileged"].inject(gold, "frontend")
    sc = main_container(find_deployment(case, "frontend"))["securityContext"]
    assert sc["privileged"] is True
    assert "allowPrivilegeEscalation" not in sc  # API forbids privileged + APE false (D-016)
    # nothing else changed: every other object identical to gold
    others = [(g, c) for g, c in zip(gold, case) if g["metadata"]["name"] != "frontend" or g["kind"] != "Deployment"]
    assert all(g == c for g, c in others)
    assert main_container(find_deployment(gold, "frontend"))["securityContext"]["privileged"] is False  # gold untouched


def test_registry_specs_complete():
    for spec in REGISTRY.values():
        assert spec.fix_class in {"a", "b", "c"}
        assert spec.target_rules and spec.reference_fix
