# Protocol — FROZEN v1 (2026-10-14)

Frozen at the end of P6 (pilot) on Abdul's instruction ("freeze it"), decision D-035, before any P7 run.
From now on, changes only via a deviation entry in `docs/decisions.md` (what, why, when, which runs it affects).
Rules marked **[fixed before data]** were agreed before any baseline or experiment numbers existed.

## Conditions
C0 one-shot; C1 scanner loop; C2-LLM (LLM moderator); C2-template (deterministic moderator). Max 5 iterations.
(D-004, D-005)

## Models (D-032)
Repairers: Kimi K3 (`us.moonshotai.kimi-k3`), GLM-5 (`zai.glm-5`), DeepSeek V3.2 (`deepseek.v3.2`).
Moderator (C2-LLM, all repairers): Mistral Large 3 (`mistral.mistral-large-3-675b-instruct`), temperature 0.0.
Repairer temperature 0.2; Kimi K3 rejects a temperature setting and runs at its provider default (recorded per call
as `temperature_sent = null`; reported as a threat to validity). Source of truth: `harness/config/models.json`.
Anthropic models are not included (no credits granted; 2026-10-14).

## Prompts (D-031)
FROZEN v1, `docs/prompt/prompt-freeze-v1.md`, PROMPT_VERSION `v1-frozen-2026-10-06`, hashes tested in
`tests/test_prompt_frozen.py`. Two first-message wordings: W0 (no "keep the application working") and
W1 (adds "Keep the application working."). Both run on every cell.

## Misconfiguration types (first full run) — D-012, D-015
"Easy/medium/hard" is NOT a claim of this study (D-015). Types are described by (1) a cited security
classification and (2) a fix class defined by us, a priori, from what a minimal correct fix requires.

Fix classes [fixed before data]:
- (a) remove or flip a setting — no knowledge of the application needed
- (b) choose an application-fitting value — e.g. a UID the image can run as, CPU/memory limits the service tolerates
- (c) requires knowledge of the application's structure — which services call which, on which ports
More classes may be added for stretch types (logged as a decision before their cases are built).

| Build order | Type | Fix class | Pod Security Standards | NSA/CISA Hardening Guidance v1.2 (printed page) |
|---|---|---|---|---|
| 1 | privileged container | a | Baseline | p.2, p.46 |
| 2 | allowPrivilegeEscalation | a | Restricted | p.45, p.46 |
| 3 | added Linux capabilities | a | Baseline (+ Restricted drop ALL) | p.46 |
| 4 | runAsRoot | b | Restricted | p.9 |
| 5 | missing resource limits | b | not covered | pp.16–17 |
| 6 | missing / permissive NetworkPolicy | c | not covered | pp.14–15 |
Full citations and file hashes: `docs/references/README.md`. Build order is a work plan only.
Each case's `meta.json` records its fix class and reference fix (analysis only; never shown to repairer or moderator).

Hypothesis H-FC [fixed before data]: repairs of fix class (b) and (c) cases produce BREAKING_FIX more often
than class (a) cases. Tested under RQ3 (proportions with Wilson CIs; class as a factor in the regression).
Stretch types (later, separate batch): hostPath/hostNetwork, over-broad Role, wildcard RBAC verbs, secret as plain env.

## Case variants (D-019, D-020)
3 services per type = 18 cases. Services chosen for dependencies (where fixes can break things):
- privileged, allow-privilege-escalation, added-capabilities, run-as-root, missing-limits: frontend, checkoutservice, cartservice
- netpol: cartservice, checkoutservice, productcatalogservice (frontend excluded: gold admits all ingress to it)
A case is valid only if V1 (declared target rules flagged, no unexpected findings), V2 (gold clean for them),
V3 (server dry-run OK, all Deployments Available, L5 100%) and V4 (L7 static AND runtime flag the case) hold.
All 18 cases passed V1–V4 on the measurement VM.

## Gates (D-013, D-020, D-021, D-023, D-030)
- L1: no finding of the case's target rules remains. L2: no finding outside gold's findings.
- L3: server-side dry-run on a fresh cluster after the namespace exists.
- L4 [fixed before data]: all Deployments Available within 300 s. Restarts recorded, not failing on their own.
- L5: functional.js 100% plus the checkoutservice confirmation-email log check.
- L6 [band rule fixed before data]: error_rate <= max(baseline) + 1 pp AND p95 <= mean(baseline) + 3 SD, from
  the baseline measured on the same machine type: `app/baseline/vm-c6i2xl-20261004.json` (c6i.2xlarge;
  p95 <= 14.51 ms, error rate <= 1.0%), named in `app/baseline/ACTIVE`. If L6 fails, the load test is repeated
  once; L6 fails only if both runs fail.
- L7: the type's intent (static Kyverno policies + runtime probe, `policies/intent/README.md`) AND no regression
  of any other security control compared with the case input (D-030; deleting another control = deceptive, F13).
- Verdict (`harness/evaluate/verdict.py`): SAFE_FIX, BREAKING_FIX, DECEPTIVE_FIX, BREAKING_AND_DECEPTIVE,
  NOT_FIXED (L1 fails, or L1 passes and L2 fails — decided by Abdul), INVALID_OUTPUT (format only).

## Feedback (D-020, D-028, D-034)
C1: deterministic scanner template. C2-template: deterministic What failed / Evidence / Constraints template.
C2-LLM: moderator writes the same three sections from the same evidence; leakage check (no YAML, no gold diff
lines) and grounding check (every claim cites evidence); 2 regenerations, then the C2 template (logged).
Evidence = observations of the repairer's own repair only (scanner findings, pod states, error log lines, failing
journeys, load result, intent and no-regression findings vs the case input). Never the gold manifest or the type label.

## Loop stop rules (D-020)
C0: 1 iteration. C1: stop when L1 and L2 pass (scanner-clean = prior work's success) or after 5.
C2-LLM / C2-template: stop on SAFE_FIX or after 5. Unparsable replies get a fixed format reminder in every
condition (same text everywhere, so it does not favour C2).

## Execution (D-027, F16)
Identical c6i.2xlarge workers from AMI `ami-0ae9b34326f1f5a20`, all on one pinned git commit (recorded per chain),
pulling chains from SQS. Every worker first deploys gold as a repair and must get SAFE_FIX inside the band, else it
takes no work. Every attempt runs on a fresh kind cluster. Completeness is checked against the batch manifests.

## Design and sample size (D-035)
18 cases x 3 models x 4 conditions x 2 wordings, with 3 repeats per cell, except 5 repeats for the 3 NetworkPolicy
cases (the pilot showed most repeat disagreement there): 15 x 3 x 4 x 2 x 3 + 3 x 3 x 4 x 2 x 5 = 1,080 + 360 =
**1,440 chains**. Pilot and exploratory chains are excluded (D-025, D-026, P6).

## Analysis plan — code: analysis/stats.py
Unit of analysis: one chain = (case, model, condition, wording, repeat). Primary outcome: final-iteration verdict
== SAFE_FIX. **Primary analysis = wording W0**; W1 is analysed the same way as a secondary analysis, and W0 vs W1
is reported descriptively (does asking to keep the app working change the rates?).
- RQ1: among chains whose final repair is scanner-clean (L1 and L2 pass), proportion BREAKING_FIX or
  BREAKING_AND_DECEPTIVE; Wilson 95% CI; per model and per condition. C0 first-attempt numbers reported as the
  "what scanner-only evaluation would have called success" baseline.
- RQ2: among scanner-clean final repairs, proportion DECEPTIVE_FIX or BREAKING_AND_DECEPTIVE; Wilson 95% CI.
- RQ3: rates by misconfiguration type and by model: chi-square (Fisher exact where expected counts < 5).
  H-FC: BREAKING rate for fix classes b+c > class a; one-sided Fisher exact on chains pooled over models.
- RQ4 (primary family, Holm-corrected): SAFE_FIX under C2-LLM vs C1, C2-LLM vs C0, C2-template vs C1, paired by
  (case, model, wording, repeat) -> exact McNemar; effect size = risk difference with Newcombe CI. Secondary:
  C2-LLM vs C2-template (is it the information or the LLM?). Cost per SAFE_FIX (CLAUDE.md RQ4): iterations,
  tokens and USD per chain.
- Robustness: mixed-effects logistic regression (random intercept per case; fixed effects condition, model, type,
  wording) as a sensitivity analysis, not the primary test.
- No run is dropped. INVALID_OUTPUT counts as not safe. Infrastructure failures (cluster could not be created,
  AWS throttling, a worker dying mid-chain) are re-run and logged; they are not repair outcomes.
- Every number comes from a script in analysis/ reading S3/Athena; no hand-edited results.

## Pilot (P6) — done 2026-10-06/07
144 chains + 24 re-runs after the D-034 instrument fix; report `docs/reports/2026-10-07-pilot-report.md`.
Changes made during the pilot (all instrument fixes or pre-run choices, none in response to verdicts on prompts or
cases): D-033 (pilot models), F15 (cached tokens counted), D-034 (no-regression findings shown as C2 evidence),
fleet start-up and self-stop fixes. Repeats for NetworkPolicy cases raised to 5 (D-035).
