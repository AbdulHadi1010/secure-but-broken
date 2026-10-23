# P8 — EKS validation plan (D-038, written 2026-10-16 before any EKS run)

**Question.** Do the verdicts measured on kind transfer to a managed cloud cluster? Most of all for NetworkPolicy
repairs, because NetworkPolicy is enforced by the network plugin, which differs (kind: kindnetd; EKS: VPC CNI
network policy agent).

**Design.** Replay, not re-generation: the FINAL repaired manifest of a sampled P7 chain is deployed unchanged on EKS
and judged by the same harness code (L1-L7 and verdict; `harness/orchestrate/attempt.py`, commit recorded). No model
is called. The only differences are the cluster and the L6 band.

**Cluster.** One EKS cluster, Kubernetes 1.37 (same minor as the kind node image), 2 x c6i.2xlarge managed nodes
(same type as the kind workers), VPC CNI with NetworkPolicy enforcement on, private API endpoint, driven from the
measurement VM (`infra/terraform/eks.tf`, `eks_enabled = true`). Clean slate per replay: the run's namespaces
(boutique, loadtest, intent-probe) are deleted and the deletion awaited before and after every attempt
(`harness/deploy/kind.py`, SBB_PLATFORM=eks).

**L6 band on EKS.** Same rule as kind (D-013): 10 gold deployments on the EKS cluster, same k6 scripts; band =
max(error rate) + 1 pp and mean(p95) + 3 SD. Label `eks-p8-<date>`; used only for P8 replays (SBB_BASELINE).
If fewer than 8 of the 10 baseline runs are clean, P8 stops and is reported as such (no band is invented).

**Sample (fixed rule, seed 20261017, over the 1,440 P7 chains, both wordings).**
- Scanner-clean final verdicts only (NOT_FIXED and INVALID_OUTPUT never reach the cluster; nothing to replay).
- 40 chains drawn at random from all non-safe scanner-clean chains (BREAKING_FIX, DECEPTIVE_FIX, BREAKING_AND_DECEPTIVE).
- 48 SAFE_FIX chains: 8 per misconfiguration type, drawn at random within type.
- Total 88 replays, run in a random order (same seed) so time-of-day drift does not line up with strata.

**Outcomes.**
- Primary: agreement of the EKS verdict with the kind verdict (4 categories: safe, breaking, deceptive,
  breaking-and-deceptive): percent agreement with Wilson 95% CI, and Cohen's kappa.
- Per stratum (safe / non-safe; NetworkPolicy / other types) agreement.
- Per gate: agreement of L3-L7 booleans.
- Every disagreement listed with its gate and evidence, classified afterwards as platform difference
  (e.g. NetworkPolicy enforcement, DNS, timing) or flake; classification is descriptive and does not change any P7 number.
- No replay is dropped. An infrastructure failure (cluster API unreachable, image pull rate limit) is re-run once and
  logged; it is not a disagreement.

**Reported as** a validity check of the P7 results (external validity / instrument transfer), not as new RQ results.
