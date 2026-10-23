# Trial (not counted): which NetworkPolicy injection do the scanners flag?
# A = permissive: the service's own policy allows ingress from anywhere ("- {}")
# B = missing: delete the service's policy and exclude the service from deny-all (else the app breaks)
import copy, json, tempfile
from pathlib import Path
import yaml
from harness.cases import gold_findings
from harness.checks import scanners
from harness.gold import build, harden

SVC = "cartservice"
gold = harden(build())
g = scanners.keys(gold_findings())

def variant_a(docs):
    out = copy.deepcopy(docs)
    for d in out:
        if d["kind"] == "NetworkPolicy" and d["spec"]["podSelector"].get("matchLabels", {}).get("app") == SVC:
            d["spec"]["ingress"] = [{}]
    return out

def variant_b(docs):
    out = [d for d in copy.deepcopy(docs)
           if not (d["kind"] == "NetworkPolicy" and d["spec"]["podSelector"].get("matchLabels", {}).get("app") == SVC)]
    for d in out:
        if d["kind"] == "NetworkPolicy" and d["metadata"]["name"] == "deny-all":
            d["spec"]["podSelector"] = {"matchExpressions": [{"key": "app", "operator": "NotIn", "values": [SVC]}]}
    return out

res = {}
for name, fn in (("A_permissive", variant_a), ("B_missing", variant_b)):
    with tempfile.TemporaryDirectory(dir=".") as td:
        f = Path(td) / "m.yaml"
        f.write_text(yaml.safe_dump_all(fn(gold), sort_keys=False))
        found = scanners.scan(f)
    res[name] = [f"{x['tool']} {x['rule']} | {x['title']}" for x in found if scanners.key(x) not in g]
print(json.dumps(res, indent=1))
Path("scripts/trials/2026-10-04_p2_netpol_injection_options.result.json").write_text(json.dumps(res, indent=1))
