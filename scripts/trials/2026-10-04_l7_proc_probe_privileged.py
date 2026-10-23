# Trial (not counted): does the /proc runtime probe distinguish gold from the privileged case?
# Deploy gold, probe frontend; apply privileged-frontend, wait for rollout, probe again.
import json
from pathlib import Path

from harness.checks import intent
from harness.deploy import kind
from harness.gold import NAMESPACE, OUT

ctx = "sbb-l7"
res = {}
try:
    kind.create_cluster(ctx)
    kind.kubectl(ctx, "create", "namespace", NAMESPACE)
    kind.kubectl(ctx, "apply", "-f", str(OUT))
    kind.kubectl(ctx, "-n", NAMESPACE, "wait", "deploy", "--all", "--for=condition=Available", "--timeout=600s", timeout=700)
    res["gold_frontend"] = intent.proc_status(ctx, "frontend")
    res["gold_redis"] = intent.proc_status(ctx, "redis-cart")
    kind.kubectl(ctx, "apply", "-f", "cases/privileged-frontend/manifests.yaml")
    kind.kubectl(ctx, "-n", NAMESPACE, "rollout", "status", "deploy/frontend", "--timeout=300s", timeout=400)
    res["privileged_frontend"] = intent.proc_status(ctx, "frontend")
finally:
    kind.delete_cluster(ctx)
for k, v in res.items():
    if v.get("ok"):
        v["cap_eff_hex"] = f"{v['cap_eff']:016x}"
        v["cap_bnd_hex"] = f"{v['cap_bnd']:016x}"
print(json.dumps(res, indent=1))
Path("scripts/trials/2026-10-04_l7_proc_probe_privileged.result.json").write_text(json.dumps(res, indent=1))
