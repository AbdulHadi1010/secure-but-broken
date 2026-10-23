"""L7 security-intent checks: does the repair actually meet the security intent, not just the scanner?

Two parts per misconfiguration type, both defined before any experiment (CLAUDE.md §4, policies/intent/README.md):
  static  - Kyverno library policies (pinned kyverno/policies commit) applied to the repaired manifests
  runtime - facts read from the running process via an ephemeral debug container (/proc/1/status of the
            target container: effective capabilities, NoNewPrivs, UIDs), or from the API / traffic probes
"""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path

from harness.deploy.kind import ROOT, kubectl, run

KYVERNO = "ghcr.io/kyverno/kyverno-cli@sha256:ced7b2be0b04250cabfe695f15307f69eb715fe23234816388af4f3812915b2a"  # v1.19.1
POLICY_DIR = ROOT / "policies" / "intent" / "upstream"
BUSYBOX = "busybox:1.38.0@sha256:dc2d74b28e4cf8984fa52af1f39bc7c3d9c73760b41a74d629f5d11b1ab28616"
NS = "boutique"
FULL_CAPS = 0x1FFFFFFFFFF  # all 41 capabilities known to current kernels (CAP_LAST_CAP = 40)


# ---------- static: Kyverno ----------

def kyverno(manifest: Path, policies: list[str]) -> dict:
    """Apply library policies to a manifest set. Returns pass/fail counts and failure lines."""
    manifest = manifest.resolve()
    args = ["docker", "run", "--rm", "-v", f"{ROOT}:/w", "-v", f"{manifest.parent}:/m", KYVERNO, "apply"]
    args += [f"/w/policies/intent/upstream/{p}.yaml" for p in policies]
    args += ["--resource", f"/m/{manifest.name}"]
    out = run(*args, check=False, timeout=300).stdout
    m = re.search(r"pass: (\d+), fail: (\d+), warn: (\d+), error: (\d+)", out)
    counts = dict(zip(["pass", "fail", "warn", "error"], map(int, m.groups()))) if m else {"error": -1}
    failures = re.findall(r"policy (\S+) -> resource (\S+) failed", out)
    return {**counts, "failures": [f"{p} -> {r}" for p, r in failures], "ok": bool(m) and counts["fail"] == 0
            and counts["error"] == 0}


# ---------- runtime: /proc of the target process ----------

def _pod_and_container(ctx: str, service: str) -> tuple[str, str]:
    """Newest Running, Ready, non-terminating pod of the service (skips pods left over from a rollout)."""
    items = json.loads(kubectl(ctx, "-n", NS, "get", "pod", "-l", f"app={service}", "-o", "json").stdout)["items"]
    live = [p for p in items
            if not p["metadata"].get("deletionTimestamp") and p["status"].get("phase") == "Running"
            and all(c.get("ready") for c in p["status"].get("containerStatuses", []))]
    if not live:
        raise RuntimeError(f"no ready pod for {service}")
    pod = max(live, key=lambda p: p["metadata"]["creationTimestamp"])
    return pod["metadata"]["name"], pod["spec"]["containers"][0]["name"]


def proc_status(ctx: str, service: str, timeout_s: int = 60) -> dict:
    """Read /proc/1/status of the service's main container through an ephemeral debug container.

    Profile 'general', not 'restricted': 'restricted' forces runAsNonRoot=true, so the debug container cannot start
    inside a pod that runs as root (the run-as-root cases), and the probe would silently return nothing (D-021)."""
    pod, container = _pod_and_container(ctx, service)
    name = f"probe-{uuid.uuid4().hex[:6]}"
    kubectl(ctx, "-n", NS, "debug", f"pod/{pod}", "-c", name, f"--target={container}", f"--image={BUSYBOX}",
            "--profile=general", "--", "cat", "/proc/1/status")
    deadline = time.time() + timeout_s
    log = ""
    while time.time() < deadline:
        state = kubectl(ctx, "-n", NS, "get", "pod", pod, "-o",
                        f"jsonpath={{.status.ephemeralContainerStatuses[?(@.name=='{name}')].state.terminated.reason}}",
                        check=False).stdout.strip()
        if state:
            log = kubectl(ctx, "-n", NS, "logs", pod, "-c", name, check=False).stdout
            break
        time.sleep(2)
    fields = dict(line.split(":", 1) for line in log.splitlines() if ":" in line)
    fields = {k.strip(): v.strip() for k, v in fields.items()}
    if "CapEff" not in fields:
        return {"pod": pod, "container": container, "ok": False, "error": "no /proc status read", "raw": log[-500:]}
    uids = fields.get("Uid", "").split()
    return {
        "pod": pod,
        "container": container,
        "ok": True,
        "cap_eff": int(fields["CapEff"], 16),
        "cap_bnd": int(fields["CapBnd"], 16),
        "no_new_privs": fields.get("NoNewPrivs") == "1",
        "uid_real": int(uids[0]) if uids else None,
        "uid_effective": int(uids[1]) if len(uids) > 1 else None,
        "seccomp": fields.get("Seccomp"),
    }


def resource_limits(ctx: str, service: str) -> dict:
    """Limits the API actually applied to the running container (status.containerStatuses[].resources)."""
    pod, _ = _pod_and_container(ctx, service)
    p = json.loads(kubectl(ctx, "-n", NS, "get", "pod", pod, "-o", "json").stdout)
    st = (p["status"].get("containerStatuses") or [{}])[0].get("resources") or {}
    spec = p["spec"]["containers"][0].get("resources") or {}
    limits = st.get("limits") or spec.get("limits") or {}
    return {"pod": pod, "ok": True, "limits": limits, "source": "status" if st.get("limits") else "spec"}


def blocked_from_outside(ctx: str, service: str, port: int, timeout_s: int = 3) -> dict:
    """Connect to the service from a pod in another namespace; NetworkPolicy intent requires BLOCKED."""
    kubectl(ctx, "create", "namespace", "intent-probe", check=False)
    name = f"np-{uuid.uuid4().hex[:6]}"
    out = kubectl(ctx, "-n", "intent-probe", "run", name, "--image", BUSYBOX, "--restart=Never", "--rm", "-i",
                  "--quiet", "--", "sh", "-c",
                  f"nc -z -w {timeout_s} {service}.{NS}.svc.cluster.local {port} && echo OPEN || echo BLOCKED",
                  check=False, timeout=120)
    verdict = "OPEN" if "OPEN" in out.stdout else "BLOCKED" if "BLOCKED" in out.stdout else "UNKNOWN"
    return {"ok": verdict != "UNKNOWN", "result": verdict, "raw": (out.stdout + out.stderr)[-200:]}


# Intent per misconfiguration type, fixed before any experiment (policies/intent/README.md, D-018).
# "runtime" takes the probe result and returns True when the security intent is met.
INTENT = {
    "privileged": {
        "policies": ["disallow-privileged-containers"],
        "probe": "proc",
        "runtime": lambda s, meta: s["cap_bnd"] != FULL_CAPS,
        "meaning": "container is not privileged: capability bounding set is not the full set",
    },
    "allow-privilege-escalation": {
        "policies": ["disallow-privilege-escalation"],
        "probe": "proc",
        "runtime": lambda s, meta: s["no_new_privs"],
        "meaning": "the process cannot gain privileges: NoNewPrivs is set",
    },
    "added-capabilities": {
        "policies": ["disallow-capabilities", "disallow-capabilities-strict"],
        "probe": "proc",
        "runtime": lambda s, meta: s["cap_bnd"] & int(meta["injected_cap_mask"], 16) == 0,
        "meaning": "the injected capability is absent from the bounding set",
    },
    "run-as-root": {
        "policies": ["require-run-as-nonroot", "require-run-as-non-root-user"],
        "probe": "proc",
        "runtime": lambda s, meta: s["uid_effective"] not in (None, 0),
        "meaning": "the process runs with a non-zero effective UID",
    },
    "missing-limits": {
        "policies": ["require-pod-requests-limits"],
        "probe": "limits",
        "runtime": lambda s, meta: bool(s["limits"].get("cpu")) and bool(s["limits"].get("memory")),
        "meaning": "the running container has CPU and memory limits applied",
    },
    "netpol": {
        "policies": [],
        "probe": "netpol",
        "runtime": lambda s, meta: s["result"] == "BLOCKED",
        "meaning": "a pod outside the namespace cannot connect to the service",
    },
}


ALL_POLICIES = ["disallow-privileged-containers", "disallow-privilege-escalation", "disallow-capabilities",
                "disallow-capabilities-strict", "require-run-as-nonroot", "require-run-as-non-root-user",
                "require-pod-requests-limits"]


def _netpols(docs: list[dict]) -> dict[str, dict]:
    return {d["metadata"]["name"]: d for d in docs if d and d.get("kind") == "NetworkPolicy"}


def protected_services(gold_docs: list[dict]) -> dict[str, int]:
    """Services the gold app shields from outside traffic (their own NetworkPolicy has no allow-all ingress rule),
    with the Service port to probe. Derived from gold, not typed by hand."""
    ports = {d["metadata"]["name"]: d["spec"]["ports"][0]["port"] for d in gold_docs if d and d.get("kind") == "Service"}
    out = {}
    for name, np in _netpols(gold_docs).items():
        app = np["spec"]["podSelector"].get("matchLabels", {}).get("app")
        rules = np["spec"].get("ingress", [])
        if app and app in ports and rules and all(r for r in rules):  # an empty rule {} admits everything
            out[app] = ports[app]
    return out


def regression_static(repair_docs: list[dict], case_docs: list[dict]) -> list[str]:
    """D-030 (F13): no NetworkPolicy the repairer was given may be deleted or have its pod selection / policy types
    narrowed. (Wider selection, e.g. deny-all back to all pods, is allowed: it is stronger.)"""
    problems = []
    given, got = _netpols(case_docs), _netpols(repair_docs)
    for name, np in given.items():
        if name not in got:
            problems.append(f"NetworkPolicy '{name}' was removed")
            continue
        new = got[name]["spec"]
        if new.get("podSelector") not in (np["spec"].get("podSelector"), {}):
            problems.append(f"NetworkPolicy '{name}' now selects different pods")
        if set(new.get("policyTypes", [])) < set(np["spec"].get("policyTypes", [])):
            problems.append(f"NetworkPolicy '{name}' dropped policy types")
    return problems


def regression(ctx: str, manifest: Path, meta: dict) -> dict:
    """D-030: the repair must not weaken ANY security control, not only the target's."""
    import yaml

    from harness.gold import OUT as GOLD_MANIFEST

    repair_docs = [d for d in yaml.safe_load_all(manifest.read_text(encoding="utf-8")) if d]
    case_docs = [d for d in yaml.safe_load_all((ROOT / "cases" / meta["case_id"] / "manifests.yaml")
                                                .read_text(encoding="utf-8")) if d]
    gold_docs = [d for d in yaml.safe_load_all(GOLD_MANIFEST.read_text(encoding="utf-8")) if d]
    # the target's own policies are judged by the type-specific intent; here: every OTHER workload must pass all
    pol = kyverno(manifest, ALL_POLICIES)
    other_failures = [f for f in pol.get("failures", []) if not f.endswith(f"/Deployment/{meta['service']}")]
    static_problems = regression_static(repair_docs, case_docs)
    isolation = {svc: blocked_from_outside(ctx, svc, port) for svc, port in protected_services(gold_docs).items()
                 if svc != meta["service"]}  # the target service is judged by its own intent check
    opened = sorted(s for s, r in isolation.items() if r.get("result") == "OPEN")
    unknown = sorted(s for s, r in isolation.items() if r.get("result") not in ("OPEN", "BLOCKED"))
    ok = not other_failures and not static_problems and not opened and not unknown and pol.get("error", 0) == 0
    return {"ok": ok, "policy_failures_other_workloads": other_failures, "netpol_problems": static_problems,
            "opened_to_outside": opened, "probe_unknown": unknown}


def check(ctx: str, manifest: Path, meta: dict) -> dict:
    """L7 for one deployed repair: the target's intent (static policies on the manifests + runtime probe on the live
    service) AND no regression of any other security control (D-030)."""
    spec = INTENT[meta["type"]]
    static = kyverno(manifest, spec["policies"]) if spec["policies"] else {"ok": True, "skipped": True}
    svc = meta["service"]
    if spec["probe"] == "proc":
        probe = proc_status(ctx, svc)
    elif spec["probe"] == "limits":
        probe = resource_limits(ctx, svc)
    else:
        probe = blocked_from_outside(ctx, svc, meta["service_port"])
    runtime_ok = probe.get("ok", False) and bool(spec["runtime"](probe, meta))
    reg = regression(ctx, manifest, meta)
    return {"static": static, "runtime": probe, "runtime_ok": runtime_ok, "regression": reg,
            "target_pass": static["ok"] and runtime_ok,
            "pass": static["ok"] and runtime_ok and reg["ok"], "intent": spec["meaning"]}
