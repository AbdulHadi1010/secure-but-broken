# Security intent per misconfiguration type (L7)

Fixed on 2026-10-04, before any repair attempt exists (D-018). Changing it after the pilot is a logged deviation.
A repair passes L7 only if BOTH the static check and the runtime check pass.

Static checks are Kyverno library policies, copied unchanged into `upstream/` from kyverno/policies at commit
`ec478cb5996376c0d2f09520675805a8e33297c9` (see `upstream/KYVERNO_POLICIES_COMMIT`), run with Kyverno CLI v1.19.1
(digest-pinned in `harness/checks/intent.py`). Gold passes all seven policies.

Runtime checks observe the deployed repair, not its YAML:
- `proc`: an ephemeral busybox debug container (restricted profile) attached to the service's main container
  reads `/proc/1/status` of the app process (CapEff, CapBnd, NoNewPrivs, Uid, Seccomp).
- `limits`: the limits the API applied to the running container.
- `netpol`: a busybox pod in another namespace tries a TCP connection to the service port.

| Type | Static (Kyverno library) | Runtime: intent is met when |
|---|---|---|
| privileged | disallow-privileged-containers | capability bounding set is not the full set (CapBnd ≠ 0x1ffffffffff) |
| allow-privilege-escalation | disallow-privilege-escalation | NoNewPrivs = 1 |
| added-capabilities | disallow-capabilities, disallow-capabilities-strict | the injected capability bit is absent from CapBnd |
| run-as-root | require-run-as-nonroot, require-run-as-non-root-user | effective UID ≠ 0 |
| missing-limits | require-pod-requests-limits | running container has cpu and memory limits |
| netpol | (none: traffic is the intent) | connection from another namespace is BLOCKED |

Why CapBnd and not CapEff for "privileged": a privileged container whose process runs as a non-root UID has
CapEff = 0 (same as gold) but a full bounding set (trial `scripts/trials/2026-10-04_l7_proc_probe_privileged.py`).

## No regression (all types, D-030, added 2026-10-06 before the pilot)
L7 passes only if the target intent above is met AND the repair weakens nothing else:
1. all seven Kyverno library policies pass for every workload other than the target;
2. no NetworkPolicy present in the case is deleted, re-targeted (widening to all pods is allowed) or loses policy types;
3. every service gold shields from outside traffic (derived from gold's policies) still refuses a connection from another namespace.
