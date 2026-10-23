from harness.cases import v4_flags


def l7(static_ok=False, skipped=False, probe_ok=True, runtime_ok=False):
    static = {"ok": True, "skipped": True} if skipped else {"ok": static_ok}
    return {"static": static, "runtime": {"ok": probe_ok}, "runtime_ok": runtime_ok}


def test_flags_when_both_parts_see_the_violation():
    assert v4_flags(l7())


def test_probe_without_data_never_counts_as_flagged():  # the run-as-root bug (D-021)
    assert not v4_flags(l7(probe_ok=False))


def test_type_without_static_policy_needs_runtime_only():  # the netpol bug (D-021)
    assert v4_flags(l7(skipped=True))
    assert not v4_flags(l7(skipped=True, runtime_ok=True))


def test_not_flagged_if_static_passes_or_runtime_passes():
    assert not v4_flags(l7(static_ok=True))
    assert not v4_flags(l7(runtime_ok=True))
    assert not v4_flags({})
