# P2 feasibility probes (not part of any experiment): coupled fields + NetworkPolicy enforcement on kind.
import copy, json, yaml
from harness.deploy import kind
from harness.gold import build, harden, NAMESPACE, OUT
from harness.injectors import privileged, find_deployment, main_container

ctx = "sbb-p2"
res = {}
BUSYBOX = "busybox:1.38.0@sha256:dc2d74b28e4cf8984fa52af1f39bc7c3d9c73760b41a74d629f5d11b1ab28616"
try:
    kind.create_cluster(ctx)
    kind.kubectl(ctx, "create", "namespace", NAMESPACE)
    gold = harden(build())
    # 1a) privileged + allowPrivilegeEscalation:false (naive injection)
    naive = copy.deepcopy(gold)
    main_container(find_deployment(naive, "frontend"))["securityContext"]["privileged"] = True
    r = kind.kubectl(ctx, "apply", "--dry-run=server", "-f", "-", input=yaml.safe_dump_all(naive), check=False)
    res["naive_privileged_dry_run"] = {"rc": r.returncode, "err": r.stderr.strip()[-300:]}
    # 1b) injector output (APE removed)
    inj = privileged(gold, "frontend")
    r = kind.kubectl(ctx, "apply", "--dry-run=server", "-f", "-", input=yaml.safe_dump_all(inj), check=False)
    res["injector_privileged_dry_run"] = {"rc": r.returncode, "err": r.stderr.strip()[-300:]}
    # 2) NetworkPolicy enforcement with gold deployed
    kind.kubectl(ctx, "apply", "-f", str(OUT))
    kind.kubectl(ctx, "-n", NAMESPACE, "wait", "deploy", "--all", "--for=condition=Available", "--timeout=600s", timeout=700)
    kind.kubectl(ctx, "create", "namespace", "probe")
    def probe(ns, name, labels, target):
        lbl = ",".join(f"{k}={v}" for k, v in labels.items())
        args = ["-n", ns, "run", name, "--image", BUSYBOX, "--restart=Never", "--rm", "-i", "--quiet"]
        if lbl: args += ["--labels", lbl]
        args += ["--", "sh", "-c", f"nc -z -w 3 {target} && echo OPEN || echo BLOCKED"]
        out = kind.kubectl(ctx, *args, check=False, timeout=120)
        return (out.stdout.strip() or out.stderr.strip())[-120:]
    res["other_ns_to_cartservice"] = probe("probe", "p1", {}, "cartservice.boutique.svc.cluster.local 7070")
    res["unlabeled_same_ns_to_cartservice"] = probe(NAMESPACE, "p2", {}, "cartservice 7070")
    res["as_checkout_to_cartservice"] = probe(NAMESPACE, "p3", {"app": "checkoutservice"}, "cartservice 7070")
    res["other_ns_to_frontend"] = probe("probe", "p4", {}, "frontend.boutique.svc.cluster.local 80")
    res["cni"] = kind.kubectl(ctx, "-n", "kube-system", "get", "ds", "-o", "jsonpath={.items[*].metadata.name}").stdout
finally:
    kind.delete_cluster(ctx)
print(json.dumps(res, indent=1))
