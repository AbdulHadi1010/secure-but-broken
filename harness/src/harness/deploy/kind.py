"""Fresh kind cluster per run, with local pull-through registry caches.

Caches: one `registry` container per upstream registry, on the `kind` Docker network, with a named
volume so cached layers survive across clusters. Nodes reach them via containerd hosts.toml mirrors.

P8 (D-038): with SBB_PLATFORM=eks every kubectl call goes to the one EKS cluster named by SBB_KUBE_CONTEXT, and a
"fresh cluster" becomes a clean slate on it: every namespace the run creates is deleted before and after each
attempt (and the deletion is waited for). The checks themselves are unchanged.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PLATFORM = os.environ.get("SBB_PLATFORM", "kind")  # "kind" (default) or "eks" (P8)
EKS_CONTEXT = os.environ.get("SBB_KUBE_CONTEXT", "")
RUN_NAMESPACES = ("boutique", "loadtest", "intent-probe")  # every namespace an attempt or baseline run creates
KIND_CONFIG = ROOT / "infra" / "kind" / "cluster.yaml"
NODE_IMAGE = "kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5"
REGISTRY_IMAGE = "registry:2.8.3@sha256:a3d8aaa63ed8681a604f1dea0aa03f100d5895b6a58ace528858a7b332415373"
CACHES = {  # upstream registry host -> (cache container name, remote URL)
    "docker.io": ("sbb-cache-dockerio", "https://registry-1.docker.io"),
    "us-central1-docker.pkg.dev": ("sbb-cache-gar", "https://us-central1-docker.pkg.dev"),
}


def _exe(name: str) -> str:
    # Prefer the winget-installed tools (kind, kubectl 1.37) over Docker Desktop's bundled kubectl (1.34),
    # which comes first on the Windows PATH but is outside the supported version skew for the 1.37 cluster.
    winget = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet"
    for candidate in [winget / "Links" / f"{name}.exe", *sorted((winget / "Packages").glob(f"*/{name}.exe"))]:
        if candidate.exists():
            return str(candidate)
    found = shutil.which(name)
    if found:
        return found
    raise FileNotFoundError(name)


def run(*args: str, check: bool = True, input: str | None = None, timeout: int = 900) -> subprocess.CompletedProcess:
    exe = _exe(args[0])
    return subprocess.run([exe, *args[1:]], check=check, capture_output=True, text=True, input=input,
                          timeout=timeout, encoding="utf-8", errors="replace")


def ensure_caches() -> None:
    if PLATFORM == "eks":  # EKS nodes pull directly (images are pinned by digest either way)
        return
    for host, (name, remote) in CACHES.items():
        state = run("docker", "inspect", "-f", "{{.State.Running}}", name, check=False)
        if state.returncode == 0 and state.stdout.strip() == "true":
            continue
        if state.returncode == 0:
            run("docker", "start", name)
            continue
        run("docker", "run", "-d", "--restart=always", "--name", name,
            "-e", f"REGISTRY_PROXY_REMOTEURL={remote}", "-v", f"{name}-data:/var/lib/registry", REGISTRY_IMAGE)


def _hosts_toml(host: str, cache: str) -> str:
    server = CACHES[host][1]
    return f'server = "{server}"\n\n[host."http://{cache}:5000"]\n  capabilities = ["pull", "resolve"]\n'


def eks_reset() -> float:
    """EKS: delete every namespace a run creates and wait until they are gone (clean slate). Returns seconds."""
    t0 = time.perf_counter()
    for ns in RUN_NAMESPACES:
        run("kubectl", "--context", EKS_CONTEXT, "delete", "namespace", ns, "--ignore-not-found", "--wait=true",
            "--timeout=600s", check=False, timeout=700)
    left = run("kubectl", "--context", EKS_CONTEXT, "get", "namespaces", "-o", "name").stdout.split()
    stuck = [n for n in left if n.removeprefix("namespace/") in RUN_NAMESPACES]
    if stuck:
        raise RuntimeError(f"EKS clean slate failed, namespaces still present: {stuck}")
    return time.perf_counter() - t0


def create_cluster(name: str) -> float:
    """Create a fresh cluster wired to the caches (EKS: clean slate on the P8 cluster). Returns seconds."""
    if PLATFORM == "eks":
        return eks_reset()
    t0 = time.perf_counter()
    run("kind", "create", "cluster", "--name", name, "--image", NODE_IMAGE, "--config", str(KIND_CONFIG), "--wait", "120s")
    ensure_caches()
    for _, (cache, _) in CACHES.items():
        run("docker", "network", "connect", "kind", cache, check=False)  # no-op if already connected
    for node in run("kind", "get", "nodes", "--name", name).stdout.split():
        for host, (cache, _) in CACHES.items():
            d = f"/etc/containerd/certs.d/{host}"
            run("docker", "exec", "-i", node, "sh", "-c", f"mkdir -p {d} && cat > {d}/hosts.toml",
                input=_hosts_toml(host, cache))
    return time.perf_counter() - t0


def delete_cluster(name: str) -> None:
    if PLATFORM == "eks":
        eks_reset()
        return
    run("kind", "delete", "cluster", "--name", name, check=False)


def context(ctx: str) -> str:
    return EKS_CONTEXT if PLATFORM == "eks" else f"kind-{ctx}"


def kubectl(ctx: str, *args: str, check: bool = True, input: str | None = None, timeout: int = 900):
    return run("kubectl", "--context", context(ctx), *args, check=check, input=input, timeout=timeout)


def pods(ctx: str, ns: str) -> list[dict]:
    items = json.loads(kubectl(ctx, "-n", ns, "get", "pods", "-o", "json").stdout)["items"]
    return [
        {
            "name": p["metadata"]["name"],
            "app": p["metadata"].get("labels", {}).get("app"),
            "phase": p["status"].get("phase"),
            "ready": all(c.get("ready") for c in p["status"].get("containerStatuses", [])),
            "restarts": sum(c.get("restartCount", 0) for c in p["status"].get("containerStatuses", [])),
            # why the container last stopped / is waiting (e.g. OOMKilled, CrashLoopBackOff, CreateContainerConfigError)
            "last_terminated_reason": next((c["lastState"]["terminated"].get("reason") for c in
                                            p["status"].get("containerStatuses", [])
                                            if c.get("lastState", {}).get("terminated")), None),
            "waiting_reason": next((c["state"]["waiting"].get("reason") for c in p["status"].get("containerStatuses", [])
                                    if c.get("state", {}).get("waiting")), None),
        }
        for p in items
    ]


def versions() -> dict:
    if PLATFORM == "eks":
        nodes = json.loads(run("kubectl", "--context", EKS_CONTEXT, "get", "nodes", "-o", "json").stdout)["items"]
        cni = run("kubectl", "--context", EKS_CONTEXT, "-n", "kube-system", "get", "daemonset", "aws-node", "-o",
                  "jsonpath={.spec.template.spec.containers[*].image}", check=False).stdout.split()
        return {
            "platform": "eks",
            "server": json.loads(run("kubectl", "--context", EKS_CONTEXT, "version", "-o", "json").stdout)["serverVersion"]["gitVersion"],
            "kubectl": json.loads(run("kubectl", "version", "--client", "-o", "json").stdout)["clientVersion"]["gitVersion"],
            "nodes": [{"instance_type": n["metadata"]["labels"].get("node.kubernetes.io/instance-type"),
                       "kubelet": n["status"]["nodeInfo"]["kubeletVersion"], "os_image": n["status"]["nodeInfo"]["osImage"],
                       "runtime": n["status"]["nodeInfo"]["containerRuntimeVersion"]} for n in nodes],
            "cni_images": cni,
        }
    return {
        "kind": run("kind", "version").stdout.strip(),
        "kubectl": json.loads(run("kubectl", "version", "--client", "-o", "json").stdout)["clientVersion"]["gitVersion"],
        "node_image": NODE_IMAGE,
        "registry_cache_image": REGISTRY_IMAGE,
        "docker": run("docker", "version", "--format", "{{.Server.Version}}").stdout.strip(),
    }
