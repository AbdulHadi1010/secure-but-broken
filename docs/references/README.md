# References (local copies, for checkable citations)

| ID | Document | File | SHA-256 | Retrieved |
|---|---|---|---|---|
| R-PSS | Kubernetes Documentation, "Pod Security Standards", kubernetes/website commit 77db41e9c776b614fdb31de4cc6c8e9a70673817 (CC BY 4.0) | `pod-security-standards.77db41e9….md` | a7e5e08c9dc83cf0b0c6cb6e2eb028fac2ea32e3347e6009e4d66f6aa3615e56 | 2026-10-04 |
| R-NSA | NSA & CISA, "Kubernetes Hardening Guidance", Ver. 1.2, August 2022 (U/OO/168286-21, PP-22-0324) | `CTR_KUBERNETES_HARDENING_GUIDANCE_1.2_20220829.pdf` (downloaded by Abdul from media.defense.gov) | 5738e33f80064ab3fe465f513a7b698bc88e1538e53d35e43b2cab4171d1d509 | 2026-10-04 |

Page numbers below are the **printed** page numbers (PDF page = printed + 7).

## Where each misconfiguration type is covered

| Type | R-PSS (profile, control) | R-NSA (printed page: section) |
|---|---|---|
| privileged container | Baseline, "Privileged Containers" | p.2 executive summary ("Preventing privileged containers"); p.46 Appendix D (`privileged: false`) |
| added Linux capabilities | Baseline, "Capabilities" (only listed defaults may be added); Restricted, "Capabilities" (drop ALL) | p.46 Appendix D (`requiredDropCapabilities`) |
| allowPrivilegeEscalation | Restricted, "Privilege Escalation" | p.45 Pod security table ("Restricts escalation to root"); p.46 Appendix D |
| runAsRoot | Restricted, "Running as Non-root", "Running as Non-root user" | p.9 "Non-root containers and rootless container engines" |
| missing resource limits | not covered | pp.16–17 "Use LimitRange and ResourceQuota"; Appendices G, H |
| missing / permissive NetworkPolicy | not covered | p.14 "Use network policies and firewalls"; p.15 "Network policies" |

Note: R-NSA recommends namespace LimitRange/ResourceQuota. The gold app deliberately does not add them
(they would mask or block the injected resource-limit cases); reasons in `app/gold/accepted-findings.md`.
Our resource-limit type concerns container-level limits, which R-NSA's LimitRange discussion also constrains.
