from harness.gold import build, pin_image, _containers

import pytest


def test_every_image_pinned_by_digest():
    docs = build()
    images = [c["image"] for d in docs for c in _containers(d)]
    assert images, "no containers found"
    assert all("@sha256:" in i for i in images)


def test_loadgenerator_dropped():
    names = {d["metadata"]["name"] for d in build()}
    assert "loadgenerator" not in names
    assert {"frontend", "cartservice", "redis-cart", "checkoutservice"} <= names


def test_hardening_applied_to_every_workload():
    from harness.gold import harden, NAMESPACE, UID

    docs = harden(build())
    assert docs[0]["kind"] == "Namespace"
    assert all(d["metadata"].get("namespace") == NAMESPACE for d in docs[1:])
    assert "frontend-external" not in {d["metadata"]["name"] for d in docs}
    deps = [d for d in docs if d["kind"] == "Deployment"]
    pols = {d["spec"]["podSelector"].get("matchLabels", {}).get("app") for d in docs if d["kind"] == "NetworkPolicy"}
    for d in deps:
        pod = d["spec"]["template"]["spec"]
        assert pod["automountServiceAccountToken"] is False
        assert pod["securityContext"]["runAsUser"] == UID
        assert pod["securityContext"]["seccompProfile"]["type"] == "RuntimeDefault"
        assert d["spec"]["selector"]["matchLabels"]["app"] in pols  # every workload has its own policy
        c = pod["containers"][0]
        sp = c["startupProbe"]
        assert sp["failureThreshold"] * sp["periodSeconds"] >= 60
        assert {"grpc", "httpGet", "tcpSocket"} & sp.keys() == {"grpc", "httpGet", "tcpSocket"} & c["livenessProbe"].keys()
    assert None in pols  # default deny-all present


def test_unknown_image_rejected():
    with pytest.raises(KeyError):
        pin_image("evil/image:latest", {})
