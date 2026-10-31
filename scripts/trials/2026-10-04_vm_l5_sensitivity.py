# VM re-run of the L5 fault-injection check (D-023/D-024): break each backend in turn; L5 must fail every time.
# Uses the final L5 = functional.js + checkoutservice email log check. Run on the measurement VM, nothing else running.
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

from harness.checks import k6
from harness.deploy import kind
from harness.gold import NAMESPACE, OUT

SERVICES = ["adservice", "cartservice", "checkoutservice", "currencyservice", "emailservice", "paymentservice",
            "productcatalogservice", "recommendationservice", "redis-cart", "shippingservice"]
RESULT = Path("app/baseline/vm-l5-sensitivity.json")

ctx = "sbb-l5"
res = {"started": datetime.now(timezone.utc).isoformat(), "host": platform.node(), "versions": kind.versions()}


def l5(since="5m"):
    r = k6.with_email_check(k6.functional_result(k6.run_job(ctx, f"f{len(res)}", "functional.js", 180)),
                            k6.email_check(ctx, since))
    return {"pass_rate": r["pass_rate"], "failed": [k for k, v in r["checks"].items() if v["fails"]]}


try:
    kind.create_cluster(ctx)
    kind.kubectl(ctx, "create", "namespace", NAMESPACE)
    kind.kubectl(ctx, "apply", "-f", str(OUT))
    kind.kubectl(ctx, "-n", NAMESPACE, "wait", "deploy", "--all", "--for=condition=Available", "--timeout=600s", timeout=700)
    res["healthy"] = l5()
    for svc in SERVICES:
        kind.kubectl(ctx, "-n", NAMESPACE, "scale", f"deploy/{svc}", "--replicas=0")
        kind.kubectl(ctx, "-n", NAMESPACE, "wait", "pod", "-l", f"app={svc}", "--for=delete", "--timeout=120s", check=False)
        res[f"without_{svc}"] = l5(since="60s")
        kind.kubectl(ctx, "-n", NAMESPACE, "scale", f"deploy/{svc}", "--replicas=1")
        kind.kubectl(ctx, "-n", NAMESPACE, "wait", "deploy", svc, "--for=condition=Available", "--timeout=180s", check=False)
finally:
    kind.delete_cluster(ctx)
res["all_detected"] = res.get("healthy", {}).get("pass_rate") == 1.0 and all(
    res.get(f"without_{s}", {}).get("pass_rate", 1.0) < 1.0 for s in SERVICES)
RESULT.write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
print(json.dumps({k: (v if k.startswith(("without", "healthy", "all")) else "...") for k, v in res.items()}, indent=1))
