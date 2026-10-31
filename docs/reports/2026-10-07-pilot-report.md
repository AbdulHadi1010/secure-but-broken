# P6 Pilot Report — Secure but Broken?

Date: 2026-10-07 (pilot ran 2026-10-06 17:32 to 2026-10-07 02:38 PKT). Author: Claude, for Abdul.
Status: **stopped, waiting for Abdul to confirm the cost before P7.** Nothing is running; all VMs are stopped.

Pilot chains are excluded from the paper's results (protocol, "Pilot (P6) design"). The numbers below are for
planning the full experiment only.

## 1. What ran

| Batch | Chains | Design |
|---|---|---|
| pilot-20261006-W0 / -W1 | 72 + 72 | 3 cases (privileged / run-as-root / netpol, all on checkoutservice) x Kimi K3, GLM-5 x C0, C1, C2-LLM, C2-template x 3 repeats, each wording |
| pilot-fix-20261007-W0 / -W1 | 12 + 12 | netpol-checkoutservice x both models x C2-LLM, C2-template x 3 repeats, after the D-034 fix |

All 168 chains finished; none went to the failed-jobs queue (DLQ = 0); nothing is missing.
Fleet: 4 VMs created, 3 passed the gold qualification and did the work; 1 was too slow (F16) and refused work.

## 2. Results (descriptive)

**Final verdicts, main pilot (144 chains):**

| | Kimi K3 | GLM-5 |
|---|---|---|
| SAFE_FIX | 71 / 72 | 57 / 72 |
| DECEPTIVE_FIX | 0 | 10 |
| BREAKING_FIX | 0 | 2 |
| BREAKING_AND_DECEPTIVE | 0 | 2 |
| NOT_FIXED | 0 | 1 |
| INVALID_OUTPUT | 1 | 0 |

- **All non-safe results but two are on the NetworkPolicy case (F18).** GLM-5 often "fixed" the missing policy by
  deleting the namespace `deny-all` policy: the target service was protected, but the other services lost
  their protection. This is the paper's RQ2 (deceptive fix) in action.
- **Kimi K3 broke down once (F17):** mid-manifest its reply turned into random multilingual text. Kimi K3 rejects
  our temperature setting and runs at its own default; this difference from the other models must be reported.
- **Repeat agreement:** 38 of 48 cells gave the same verdict in all 3 repeats. 8 of the 10 disagreements are
  GLM-5 on the NetworkPolicy case. Variance is concentrated in the hard case, so 3 repeats may be too few there.
- **Prompt wording (W0 vs W1)** made no clear difference at this size.

## 3. Bug found by the pilot, fixed, and re-tested (D-034)

When a repair failed only the "do not weaken other controls" check, the C2 feedback said "the security intent is
not met" with an **empty evidence list**. The model could not know what was wrong, so C2 loops ran blind.
Fix: those findings are now shown as evidence (e.g. "NetworkPolicy 'deny-all' was removed"), compared with the
manifests the model was given, never with the gold answer. Tested (55 tests pass); frozen prompt texts unchanged.

Re-run of the affected cells (NetworkPolicy case, C2 conditions, 24 chains):

| GLM-5, C2 conditions | Before fix | After fix |
|---|---|---|
| SAFE_FIX | 4 / 12 | 11 / 12 |
| Safe on the first try | 4 | 7 |
| Rescued by feedback (unsafe first, safe at the end) | **0** | **4** |

Part of the jump is chance (more first-try successes this time); the 4 rescues are the effect of the fix.
Kimi K3 was 12/12 safe in both runs. This is one case and is not a result, but it shows that the runtime
feedback works when it carries the evidence.

## 4. Cost

**Harness estimate (per call, Pricing API prices):**

| Item | Main pilot | Fix re-run | Total |
|---|---|---|---|
| Kimi K3 | $11.56 | $2.23 | $13.79 |
| GLM-5 (incl. Mistral moderator) | $4.10 | $0.89 | $4.99 |
| Model checks before the pilot | | | ~$0.25 |
| EC2 compute (~28 VM-hours x $0.34) | | | ~$9.50 |
| Disks, network, other | | | ~$1 |
| **Total** | | | **about $30** (estimate was ~$35) |

**AWS bill so far (Cost Explorer, 2026-10-07 02:39 PKT, incomplete: the bill lags up to ~24 h):**
October usage $12.92, credits -$12.76, **net $0.17** (the Claude Haiku calls on 2026-10-04, not covered by
credits). Oct 6 so far: Bedrock $5.15, EC2 $0.24 (most fleet hours not posted yet).
Please check **Billing -> Bills** and **Cost Explorer** after 2026-10-08 for the final numbers; the net should stay
near $0.17 if everything is credited.

**Ongoing cost while paused:** the 4 stopped fleet VMs and the measurement VM keep their disks
(5 x 60 GB gp3, about $0.80/day total, covered by credits). Option: remove the 4 fleet VMs with Terraform
(`fleet_size=0`) and recreate them for P7 from the same image. This deletes instances, so it needs your OK.

## 5. Problems met and fixed during the pilot

| Problem | Fix |
|---|---|
| Kimi K3 hides cached tokens -> cost too low (F15) | Cached tokens counted in tokens and cost |
| Fleet VMs never stopped when idle | Exit trap saves the log and stops the VM |
| `sudo -i` collapsed the start script; VMs did nothing | `sudo -u ubuntu -H`; replace VMs when the script changes |
| 1 of 4 identical VMs too slow (F16) | Gold qualification rejected it, as designed |
| Laptop SSO expired during the run | Re-login by phone; VMs unaffected |
| Empty C2 evidence for regression failures (D-034) | Evidence added; affected cells re-run |
| Re-run launch: root-owned file, SSM killed background job | Bundle in the ubuntu home; start via `systemd-run` |

## 6. Projection for the full experiment (P7)

1,296 chains (18 cases x 3 models x 4 conditions x 3 repeats x 2 wordings), using pilot averages per chain
(Kimi $0.16, GLM $0.06, DeepSeek ~$0.04 expected) plus VM time (~6 min per attempt):

- Models: about $110; VMs: about $60; **total about $170**, covered by credits (~$550 available).
- Time: about 2-3 days on 4 VMs.
- This exceeds the $100/month budget alert, so you choose: raise the budget for one month, or split P7 over two
  months. The pilot over-represents the hard NetworkPolicy case (1 of 3 cases vs 3 of 18), so the real average may
  be a little lower.

## 7. Decisions waiting for you

1. **Confirm the pilot cost** in Billing (after 2026-10-08).
2. **Repeats:** keep 3, or use 5 for the NetworkPolicy cases where repeats disagree (adds ~$15)?
3. **Budget for P7:** raise for one month, or split over two months?
4. **Fleet VMs while paused:** keep (about $0.80/day) or remove and recreate later?
5. **Freeze the protocol** (P6 exit) with the pilot changes listed in decisions D-032 to D-034.

Sources: analysis/pilot_summary.py; analysis/out/*-chains.csv; docs/findings-log.md (F15-F18);
docs/decisions.md (D-032-D-034); docs/journal.md; S3 batches/pilot-* and chains/.
