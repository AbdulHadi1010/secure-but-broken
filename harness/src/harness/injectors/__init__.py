"""Misconfiguration injectors: gold manifests in, exactly one injected misconfiguration out.

Each injector is a pure function on the parsed gold documents. Registry maps type -> injector spec.
Reference fixes and fix classes live here for analysis only; they must never reach a prompt (CLAUDE.md §5).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Callable

Docs = list[dict]


@dataclass(frozen=True)
class InjectorSpec:
    type: str
    fix_class: str  # a | b | c  (protocol.md, D-015)
    inject: Callable[[Docs, str], Docs]
    reference_fix: str  # human description of the minimal correct fix (analysis only)
    target_rules: tuple[str, ...] = ()  # "<tool>:<rule_id>" that L1 requires cleared (confirmed by case validation)
    coupled_rules: tuple[str, ...] = ()  # rules triggered by fields the API forces to change with the injection (D-016)
    meta_extra: dict = field(default_factory=dict)  # facts L7 needs (e.g. injected capability bit); analysis only


def find_deployment(docs: Docs, service: str) -> dict:
    for d in docs:
        if d.get("kind") == "Deployment" and d["metadata"]["name"] == service:
            return d
    raise KeyError(f"no Deployment named {service}")


def main_container(dep: dict) -> dict:
    return dep["spec"]["template"]["spec"]["containers"][0]


def privileged(docs: Docs, service: str) -> Docs:
    """Make the service's main container privileged.

    The API server rejects privileged: true together with allowPrivilegeEscalation: false, so the
    explicit false is removed (privileged implies escalation). See D-016.
    """
    out = copy.deepcopy(docs)
    sc = main_container(find_deployment(out, service)).setdefault("securityContext", {})
    sc["privileged"] = True
    sc.pop("allowPrivilegeEscalation", None)
    return out


def allow_privilege_escalation(docs: Docs, service: str) -> Docs:
    """Explicitly allow privilege escalation on the service's main container (gold sets it to false)."""
    out = copy.deepcopy(docs)
    main_container(find_deployment(out, service)).setdefault("securityContext", {})["allowPrivilegeEscalation"] = True
    return out


CAP_SYS_ADMIN_BIT = 21  # linux/capability.h


def added_capabilities(docs: Docs, service: str) -> Docs:
    """Add CAP_SYS_ADMIN to the main container (gold drops ALL and adds nothing)."""
    out = copy.deepcopy(docs)
    caps = main_container(find_deployment(out, service)).setdefault("securityContext", {}).setdefault("capabilities", {})
    caps["add"] = ["SYS_ADMIN"]
    return out


def run_as_root(docs: Docs, service: str) -> Docs:
    """Run the whole pod as root (UID 0). Pod level, because gold sets the non-root UID at pod level: a fix must
    choose a non-root UID that the image can run as (class b), not just delete a container override.
    runAsNonRoot must become false, or the kubelet refuses to start the pod (coupled field)."""
    out = copy.deepcopy(docs)
    psc = find_deployment(out, service)["spec"]["template"]["spec"].setdefault("securityContext", {})
    psc["runAsUser"] = 0
    psc["runAsNonRoot"] = False
    return out


def missing_limits(docs: Docs, service: str) -> Docs:
    """Remove CPU and memory limits from the main container (requests and ephemeral-storage stay)."""
    out = copy.deepcopy(docs)
    limits = main_container(find_deployment(out, service)).get("resources", {}).get("limits", {})
    limits.pop("cpu", None)
    limits.pop("memory", None)
    return out


def _policy_selects(d: dict, service: str) -> bool:
    return d.get("kind") == "NetworkPolicy" and d["spec"]["podSelector"].get("matchLabels", {}).get("app") == service


def missing_netpol(docs: Docs, service: str) -> Docs:
    """Remove the service's NetworkPolicy. The namespace deny-all must then exclude the service, or the service
    becomes unreachable and the case would not work (coupled change, D-019). Result: no policy governs the pod."""
    out = [d for d in copy.deepcopy(docs) if not _policy_selects(d, service)]
    for d in out:
        if d.get("kind") == "NetworkPolicy" and d["metadata"]["name"] == "deny-all":
            d["spec"]["podSelector"] = {"matchExpressions": [{"key": "app", "operator": "NotIn", "values": [service]}]}
    return out


REGISTRY: dict[str, InjectorSpec] = {
    "privileged": InjectorSpec(
        type="privileged",
        fix_class="a",
        inject=privileged,
        reference_fix="set securityContext.privileged to false (or remove it) and restore allowPrivilegeEscalation: false",
        target_rules=(
            "checkov:CKV_K8S_16",  # Container should not be privileged
            "kics:dd29336b-fe57-445b-a26e-e6aa867ae609",  # Container Is Privileged
            "kube-score:container-security-context-privileged",
        ),
        coupled_rules=(
            "checkov:CKV_K8S_20",  # Containers should not run with allowPrivilegeEscalation
            "kics:5572cc5e-1e4c-4113-92a6-7a8a3bd25e6d",  # Privilege Escalation Allowed
        ),
    ),
    "allow-privilege-escalation": InjectorSpec(
        type="allow-privilege-escalation",
        fix_class="a",
        inject=allow_privilege_escalation,
        reference_fix="set securityContext.allowPrivilegeEscalation to false",
        target_rules=(
            "checkov:CKV_K8S_20",  # Containers should not run with allowPrivilegeEscalation
            "kics:5572cc5e-1e4c-4113-92a6-7a8a3bd25e6d",  # Privilege Escalation Allowed
        ),
    ),
    "added-capabilities": InjectorSpec(
        type="added-capabilities",
        fix_class="a",
        inject=added_capabilities,
        reference_fix="remove SYS_ADMIN from securityContext.capabilities.add (keep drop: [ALL])",
        target_rules=(
            "checkov:CKV_K8S_25",  # Minimize the admission of containers with added capability
            "checkov:CKV_K8S_39",  # Do not use the CAP_SYS_ADMIN linux capability
            "kics:235236ee-ad78-4065-bd29-61b061f28ce0",  # Containers With Sys Admin Capabilities
            "kics:19ebaa28-fc86-4a58-bcfa-015c9e22fe40",  # Containers With Added Capabilities
        ),
        meta_extra={"injected_capability": "SYS_ADMIN", "injected_cap_mask": f"{1 << CAP_SYS_ADMIN_BIT:x}"},
    ),
    "run-as-root": InjectorSpec(
        type="run-as-root",
        fix_class="b",
        inject=run_as_root,
        reference_fix="set pod securityContext.runAsUser to a non-root UID the image can run as (gold: 10001) and runAsNonRoot: true",
        target_rules=(
            "checkov:CKV_K8S_23",  # Minimize the admission of root containers
            "checkov:CKV_K8S_40",  # Containers should run as a high UID to avoid host conflict
            "kics:cf34805e-3872-4c08-bf92-6ff7bb0cfadb",  # Container Running As Root
            "kics:02323c00-cdc3-4fdc-a310-4f2b3e7a1660",  # Container Running With Low UID
            "kube-score:container-security-context-user-group-id",
        ),
    ),
    "missing-limits": InjectorSpec(
        type="missing-limits",
        fix_class="b",
        inject=missing_limits,
        reference_fix="add cpu and memory limits the service tolerates (gold values per service in app/gold/manifests.yaml)",
        target_rules=(
            "checkov:CKV_K8S_11",  # CPU limits should be set
            "checkov:CKV_K8S_13",  # Memory limits should be set
            "kics:b14d1bc4-a208-45db-92f0-e21f8e2588e9",  # Memory Limits Not Defined
            "kics:4ac0e2b7-d2d2-4af7-8799-e8de6721ccda",  # CPU Limits Not Set
            "kube-score:container-resources",
        ),
    ),
    "netpol": InjectorSpec(
        type="netpol",
        fix_class="c",
        inject=missing_netpol,
        reference_fix="restore a NetworkPolicy for the service that admits only its real callers on its port "
                      "(gold: upstream policy) and let deny-all select it again",
        target_rules=("kube-score:pod-networkpolicy",),  # Checkov/KICS do not flag it (trial 2026-10-04)
    ),
}
