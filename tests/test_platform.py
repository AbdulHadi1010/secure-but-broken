"""P8 (D-038): the EKS mode sends kubectl to the P8 context and turns 'fresh cluster' into a namespace clean slate."""

import importlib

import harness.deploy.kind as kind


def _reload(monkeypatch, platform, ctx=""):
    monkeypatch.setenv("SBB_PLATFORM", platform)
    monkeypatch.setenv("SBB_KUBE_CONTEXT", ctx)
    return importlib.reload(kind)


def test_kind_default_context(monkeypatch):
    k = _reload(monkeypatch, "kind")
    assert k.context("sbb-att-1234") == "kind-sbb-att-1234"


def test_eks_context_and_clean_slate(monkeypatch):
    k = _reload(monkeypatch, "eks", "arn:aws:eks:us-east-1:1:cluster/sbb-p8")
    calls = []

    class R:
        returncode, stdout, stderr = 0, "namespace/default\nnamespace/kube-system\n", ""

    monkeypatch.setattr(k, "run", lambda *a, **kw: calls.append(a) or R())
    assert k.context("anything") == "arn:aws:eks:us-east-1:1:cluster/sbb-p8"
    k.create_cluster("sbb-att-1")
    deleted = [c[5] for c in calls if c[3:5] == ("delete", "namespace")]
    assert deleted == list(k.RUN_NAMESPACES)
    assert not any(c[0] == "kind" for c in calls)
    k.ensure_caches()  # no docker on EKS
    assert not any(c[0] == "docker" for c in calls)


def test_eks_clean_slate_fails_loudly(monkeypatch):
    k = _reload(monkeypatch, "eks", "ctx")

    class R:
        returncode, stdout, stderr = 0, "namespace/boutique\n", ""

    monkeypatch.setattr(k, "run", lambda *a, **kw: R())
    import pytest

    with pytest.raises(RuntimeError):
        k.eks_reset()


def teardown_module():
    import os

    os.environ.pop("SBB_PLATFORM", None)
    os.environ.pop("SBB_KUBE_CONTEXT", None)
    importlib.reload(kind)
