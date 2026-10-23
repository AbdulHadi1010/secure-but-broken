# Accepted scanner findings on the gold app

The gold app is clean for every Checkov rule (0 failed / 1010 passed, Checkov 3.3.22). The findings below remain
on purpose. L2 ("no new findings") diffs against gold, so accepted findings cannot affect verdicts.

| Scanner | Finding | Count | Why accepted |
|---|---|---|---|
| KICS 2.1.20 | Missing AppArmor Profile (LOW) | 11 | AppArmor is not enabled on our nodes (kind on WSL2; EKS AL2023 uses SELinux). Requesting a profile would make pods unschedulable, so the control is unenforceable here. |
| KICS | Pod or Container Without LimitRange (LOW) | 11 | A namespace LimitRange would silently fill in default limits, masking the "missing resource limits" misconfiguration at runtime and making its intent check meaningless. |
| KICS | Pod or Container Without ResourceQuota (LOW) | 11 | A quota on cpu/memory limits rejects pods without limits, so the injected "missing resource limits" cases would not deploy (violates case validation, CLAUDE.md §7). |
| KICS | Ensure Administrative Boundaries Between Resources (INFO) | 1 | Informational; single-namespace demo app. |
| kube-score 1.20.0 | container-image-pull-policy | 11 | Images are pinned by digest, so `IfNotPresent` is deterministic; `Always` only adds registry pulls. |
| kube-score | deployment-has-poddisruptionbudget, deployment-replicas, deployment-has-host-podantiaffinity | 11 each | Availability/reliability, not security; single-node kind cluster. |
| kube-score | pod-probes-identical | 2 | Upstream probe design; reliability, not security. |
