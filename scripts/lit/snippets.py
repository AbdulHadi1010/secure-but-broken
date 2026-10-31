"""Reading aid for full-text screening: print the parts of a paper that answer the gap-table questions.

For one record: title/venue, the abstract, the section headings, and keyword-in-context passages (with an
approximate page number) for deployment, clusters, load/functional testing, scanners/oracles, runtime and
security-intent checks, and feedback loops. The reviewer still reads and judges; this only locates evidence.
Usage: uv run python scripts/lit/snippets.py R0123 [max_hits_per_group]
"""

import csv
import re
import sys
from pathlib import Path

LR = Path(__file__).resolve().parents[2] / "docs" / "lit-review"
GROUPS = {
    "deploy": r"\b(deploy(ed|ment|ing|s)?|terraform apply|kubectl apply|helm install|provision(ed|ing)?|real (cloud|cluster)|live (cloud|cluster|environment))\b",
    "cluster": r"\b(kind|minikube|k3s|microk8s|EKS|AKS|GKE|OpenShift|Kubernetes cluster|testbed|sandbox|LocalStack|AWS account)\b",
    "app-behaviour": r"\b(load test(ing)?|k6|locust|JMeter|wrk|latency|throughput|end-to-end|functional (test|check|correct)|smoke test|unit test|integration test|health ?check|readiness|availability|regression test)",
    "oracle": r"\b(Checkov|KICS|kube-score|kube-linter|Trivy|tfsec|Terrascan|Kubesec|Polaris|OPA|Rego|Kyverno|Conftest|terraform (plan|validate)|dry-run|schema validation|static analy[sz]\w*|scanner)",
    "intent": r"\b(security intent|runtime (check|verification|probe|test|security)|deceptive|actually (fix|secure)|penetration|exploit\w*|attack (simulation|test)|can-i|policy enforcement|NetworkPolicy|least privilege)",
    "success": r"(success (rate|criteri\w+)|pass@\d|pass rate|ground truth|accuracy|precision|recall|F1|manual(ly)? (review|inspect|check|verif)\w*|correct(ly|ness)|BLEU|exact match|we (consider|deem|count) .{0,40}(success|correct|fixed))",
    "feedback": r"\b(feedback (loop)?|iterat\w+|self-(correct|refine|repair)\w*|multi-turn|retry|re-prompt\w*|refinement loop|agent(ic)? loop)",
}


def main(rec_id: str, k: int = 6) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    rec = next(r for r in csv.DictReader((LR / "screening.csv").open(encoding="utf-8")) if r["rec_id"] == rec_id)
    print(f"== {rec_id} ({rec['year']}) {rec['title']}\n   venue: {rec['venue']} | doi {rec['doi']} | arXiv {rec['arxiv']}")
    txt_path = LR / "fulltext" / f"{rec_id}.txt"
    if not txt_path.exists():
        print("   NO FULL TEXT. Abstract:", rec["abstract"][:1500])
        return
    text = txt_path.read_text(encoding="utf-8")
    pages = text.split("\f") if "\f" in text else None
    flat = " ".join(text.split())
    print(f"   full text: {len(flat)} chars")
    m = re.search(r"abstract[\s\-—:.]*(.{200,1800}?)(\b1\.?\s+introduction|\bintroduction\b)", flat, re.I)
    print("-- abstract:", (m.group(1) if m else flat[:1500]).strip())
    heads = re.findall(r"(?:^|\s)((?:[1-9]|[IVX]{1,4})\.?\s+(?:[A-Z][A-Za-z\-]+\s){1,6}[A-Z]?[A-Za-z\-]+)(?=\s)", text)
    print("-- headings:", " | ".join(dict.fromkeys(h.strip() for h in heads))[:900])
    for g, pat in GROUPS.items():
        hits = [mm.start() for mm in re.finditer(pat, flat, re.I)]
        print(f"-- [{g}] {len(hits)} hits")
        shown, last = 0, -10_000
        for pos in hits:
            if pos - last < 400:
                continue
            last = pos
            print("   ·", flat[max(0, pos - 220): pos + 260].replace("\n", " "))
            shown += 1
            if shown >= k:
                break


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 6)
