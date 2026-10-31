# L5 sensitivity check (trial, not counted): do functional checks FAIL when a dependency is broken?
import json, time
from harness.deploy import kind
from harness.checks import k6
from harness.gold import NAMESPACE, OUT

ctx = "sbb-trial3"
res = {}
try:
    res["cluster_create_s"] = round(kind.create_cluster(ctx), 1)
    kind.kubectl(ctx, "create", "namespace", NAMESPACE)
    t0 = time.perf_counter()
    kind.kubectl(ctx, "apply", "-f", str(OUT))
    kind.kubectl(ctx, "-n", NAMESPACE, "wait", "deploy", "--all", "--for=condition=Available", "--timeout=600s", timeout=700)
    res["ready_s_warm_cache"] = round(time.perf_counter() - t0, 1)
    res["healthy"] = k6.functional_result(k6.run_job(ctx, "f0", "functional.js", 180))
    for i, svc in enumerate(["adservice", "cartservice", "checkoutservice", "currencyservice", "emailservice", "paymentservice", "productcatalogservice", "recommendationservice", "redis-cart", "shippingservice"], 1):
        kind.kubectl(ctx, "-n", NAMESPACE, "scale", f"deploy/{svc}", "--replicas=0")
        kind.kubectl(ctx, "-n", NAMESPACE, "wait", "pod", "-l", f"app={svc}", "--for=delete", "--timeout=120s", check=False)
        r = k6.functional_result(k6.run_job(ctx, f"f{i}", "functional.js", 180))
        res[f"without_{svc}"] = {"pass_rate": r["pass_rate"], "failed": [k for k, v in r["checks"].items() if v["fails"]]}
        kind.kubectl(ctx, "-n", NAMESPACE, "scale", f"deploy/{svc}", "--replicas=1")
        kind.kubectl(ctx, "-n", NAMESPACE, "wait", "deploy", svc, "--for=condition=Available", "--timeout=180s", check=False)
finally:
    kind.delete_cluster(ctx)
res["healthy"] = {"pass_rate": res["healthy"]["pass_rate"]} if "healthy" in res else None
print(json.dumps(res, indent=1))
