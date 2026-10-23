# Project journal (audit trail)

Append-only, oldest first. Every working session and every action that changes AWS, the repo, the
protocol or the data gets an entry. Never edit or delete past entries; correct them with a new entry.

Entry format:

```
### YYYY-MM-DD HH:MM PKT — <short title>
- Who: <Abdul | Claude | both>
- What: <what was done; commands for AWS changes>
- Why: <reason / phase>
- Approval: <who approved, for AWS changes and protocol changes>
- Result: <outcome, incl. failures>
- Refs: <commit, decision id, S3 key, support case>
```

Related logs: `docs/decisions.md` (design decisions and deviations), `docs/experiment-log.md`
(experiment runs and their artifacts). The journal points to them; it does not replace them.

---

### 2026-10-03 ~13:30 PKT — Kick-off and P0 planning
- Who: both
- What: Restated study; listed top 5 risks; agreed region us-east-1, $100/month budget, alert email, scope (6 types, 3 models, C2 in two moderator flavours, no C1+ arm).
- Why: Pre-P0 questions from CLAUDE.md.
- Approval: Abdul.
- Refs: D-001, D-004, D-005, D-006.

### 2026-10-03 ~14:00 PKT — Found static IAM access key in use
- Who: Claude
- What: `aws sts get-caller-identity` showed CLI using long-lived key of IAM user `claude-bedrocl` (Bedrock-only policy).
- Why: CLAUDE.md §11.2 forbids long-lived keys.
- Result: Decision to move to IAM Identity Center. Key still to be deactivated by Abdul.
- Refs: D-007.

### 2026-10-03 14:22 PKT — Repo scaffold and Terraform written
- Who: Claude
- What: Repo layout (§9), Terraform bootstrap + main stack, Bedrock smoke test, unit tests. Validated offline only.
- Refs: commit eb75aed.

### 2026-10-03 ~14:30 PKT — IAM Identity Center enabled (AWS change)
- Who: Abdul (console)
- What: Created AWS Organization o-any8uyole1 (this account = management account), Identity Center single-Region instance in us-east-1, user `Research-Admin`, permission set AdministratorAccess; CLI profile `secure-but-broken`.
- Approval: Abdul.
- Result: SSO login works.

### 2026-10-03 ~14:40 PKT — Bedrock smoke test; newest models blocked
- Who: Claude
- What: `harness bedrock-smoke`; probes of further models, `global.*` profiles and other US regions.
- Result: Sonnet 5.5, GPT-5.5 and other newest models denied ("not available for this account", agreementAvailability NOT_AVAILABLE). Switched to Sonnet 4.6, GPT-OSS 120B, DeepSeek V3.2; Haiku 4.5 moderator. All 4 OK.
- Refs: D-008, commit 58bb55d, experiment-log.

### 2026-10-03 14:50 PKT — Bootstrap stack applied (AWS change)
- Who: Claude
- What: `terraform apply` (bootstrap): S3 state bucket `sbb-tfstate-<AWS_ACCOUNT_ID>` + versioning, encryption, public-access block, TLS-only policy (5 resources). State migrated into the bucket.
- Approval: Abdul ("you can continue on your own").
- Refs: commit 50db0f7.

### 2026-10-03 ~15:00 PKT — Support case filed
- Who: Abdul
- What: AWS Support case (Account and billing) requesting access to Sonnet 5.5 / Opus 5.5 / GPT-5.5.
- Refs: case ID — to be added by Abdul.

### 2026-10-03 19:34 PKT — Main stack applied (AWS change)
- Who: Claude
- What: `terraform apply` (main): S3 artifacts bucket `sbb-artifacts-<AWS_ACCOUNT_ID>`, DynamoDB `sbb-attempts`, ECR `sbb-worker`, IAM roles `sbb-task-execution` + `sbb-worker-job`, Budget `sbb-monthly` ($100, 50/80/100% + forecast to <CONTACT_EMAIL>). Est. < $1/month idle.
- Approval: Abdul ("you have my go ahead").
- Result: 14 of 16 created. Cost anomaly monitor failed ("Limit exceeded on dimensional spend monitor creation": AWS default monitor already exists). Removed monitor + subscription from Terraform; re-plan shows no changes.
- Refs: D-009.

### 2026-10-03 19:40 PKT — Journal rule added
- Who: Claude, at Abdul's request
- What: Created this journal; added journal rule to CLAUDE.md §11; experiment log switched to oldest-first to match how it is written.

### 2026-10-03 ~19:50 PKT — Old access key removed; support case status; anomaly alert skipped
- Who: Abdul (console), verified by Claude
- What: Abdul removed the access key of IAM user `claude-bedrocl`. Verified with `aws iam list-access-keys --user-name claude-bedrocl`: no keys remain.
- Support case: Abdul reports no case ID was shown after submitting. Correction to the ~15:00 entry: case existence not yet confirmed; to be checked in Support Center -> Your support cases.
- Anomaly alert: not configured; Abdul relies on existing budgets (D-009 stands).
- Result: No long-lived credentials remain for this project. Stale entry for the dead key still sits in `~/.aws/credentials` [default]; harmless, can be deleted.

### 2026-10-03 ~20:00 PKT — P0 exit criterion confirmed; P1 started
- Who: Abdul (confirmation), Claude
- What: Abdul confirmed P0 exit criterion met (Terraform plans reviewed and applied; Converse works for all chosen models). Phase P1 (gold app + baseline) started.
- Approval: Abdul ("P0 done lets move on").

### 2026-10-03 ~20:20 PKT — P1: local tooling + gold base
- Who: Claude
- What: Started Docker Desktop; installed kind v0.33.0 (winget, official). Smoke cluster created (196 s incl. image pull; K8s v1.37.0, node image pinned by digest) and deleted. Fetched Online Boutique v0.10.7 manifests; resolved all image tags to digests; wrote `images.lock.json` and `harness gold-build` (reproducible gold build); dropped loadgenerator.
- Result: Gold = 11 Deployments, 12 Services, 10 ServiceAccounts, all images digest-pinned. 6 unit tests pass.
- Refs: D-010.

### 2026-10-03 ~21:00 PKT — P1: gold hardened, scanned, deployed, smoke-tested
- Who: Claude
- What: Scanner images pinned by digest (Checkov 3.3.22, KICS 2.1.20, kube-score 1.20.0). Baseline scan of unhardened gold: Checkov 77 failed, KICS 100, kube-score 79 non-ok. Added `harden()` (D-011) incl. upstream NetworkPolicies. Re-scan: Checkov 0 failed; remaining findings accepted (`app/gold/accepted-findings.md`). Deployed on fresh kind cluster `sbb-gold`; functional smoke (6 journeys) all 200; cluster deleted.
- Result / issues found:
  1. `kubectl apply --dry-run=server` fails on a fresh cluster because namespace `boutique` does not exist yet → L3 must create the namespace first (P3).
  2. emailservice and recommendationservice restarted once at cold start (liveness probe 1 s timeout under CPU contention, exit 137). Upstream behaviour, not hardening. Needs a rule so it is not counted as a breaking fix (open question to Abdul).
  3. Cold deploy (with image pulls) took 285 s to all Available.
- Refs: D-011.

### 2026-10-03 ~21:40 PKT — P1: decisions on restarts, working band, 6 types; startup probes added
- Who: Abdul (decisions), Claude
- What: Abdul agreed: (1) clean baseline needed, restarts not to fail a fix; (2) working-band rule (+1 pp error rate vs worst baseline; p95 within mean + 3 SD); (3) the six types, built easy -> hard. Claude added startupProbe to gold, rebuilt, re-scanned (Checkov 0 failed), cold-deployed on fresh kind: all 11 Ready, 0 restarts, ready 284 s (mostly image pulls). Protocol draft updated with the rules before any baseline data.
- Approval: Abdul.
- Refs: D-012, D-013, docs/protocol.md.

### 2026-10-03 ~22:30 PKT — P1: k6 scripts, image caches, baseline runner; trial 1
- Who: Claude
- What: Wrote `loadtest/k6/` (common.js journeys, functional.js = L5, load.js = L6: 30 s warm-up excluded + 120 s at 10 VUs, upstream journey weights). k6 2.3.0 pinned by digest, runs as an in-cluster Job. Local pull-through caches (registry 2.8.3, docker.io + us-central1-docker.pkg.dev) wired via containerd hosts.toml (`infra/kind/cluster.yaml`, `harness/deploy/kind.py`). `harness baseline` runner + unit tests (11 pass).
- Trial 1 (label `trial1`, NOT part of the baseline; tests the tooling only): ok; ready 384 s (cold cache), 0 restarts, functional 8/8 checks, load 1601 requests, 0 errors, p95 202 ms. Content checks confirmed present on the real pages.
- Next: trial 2 = L5 sensitivity (break recommendation/payment/ad services, checks must fail) + warm-cache ready time. Then the 5 counted baseline runs from a clean commit.

### 2026-10-03 ~23:30 PKT — P1: L5 sensitivity trials 2-5
- Who: Claude
- What: Fault-injection trials (scale each backend to 0, run L5). Found 2 blind spots (adservice, emailservice) and fixed them (ad content check; checkoutservice log check). Re-verified both. Warm-cache cluster ready time 29-57 s.
- Result: L5 detects all 10 services down. Table in `app/baseline/l5-sensitivity.md`.
- Refs: D-014.

### 2026-10-04 ~00:15 PKT — P1: baseline local-20261003 (5 counted runs)
- Who: Claude
- What: `harness baseline --runs 5 --label local-20261003` from clean commit e63f9ac.
- Result: 5/5 ok; ready 34.9–41.0 s; 0 restarts; L5 100%; error rate 0; p95 135.6 / 181.3 / 182.3 / 189.4 / 199.2 ms. Band: p95 ≤ 251.2 ms, error ≤ 1.0%.
- Issues: (1) S3 upload failed — SSO token expired; to redo after `aws sso login`. (2) Local kubectl client v1.34.1 vs cluster 1.37 (outside supported ±1 skew); upgrade before P3. (3) p95 rose run over run; possible drift (thermal / host load) — to watch with gold control runs during experiments.
- Refs: app/baseline/README.md.

### 2026-10-04 ~00:40 PKT — Baseline uploaded to S3
- Who: Abdul (SSO re-login), Claude
- What: `harness upload runs/baseline/local-20261003 baseline/local-20261003`.
- Result: 16 files in s3://sbb-artifacts-<AWS_ACCOUNT_ID>/baseline/local-20261003/ (versioned bucket). Resolves issue (1) of the previous entry.

### 2026-10-04 ~11:45 PKT — Difficulty labels replaced by cited classification and fix classes
- Who: Abdul (challenge, approval, downloaded the NSA/CISA PDF), Claude
- What: Verified Pod Security Standards from kubernetes/website source (commit 77db41e9…) and NSA/CISA Kubernetes Hardening Guidance v1.2 (PDF saved by Abdul; text extracted with pypdf; printed page = PDF page − 7). defense.gov blocked scripted download (403); not circumvented. Wrote `docs/references/README.md` (hashes, page map), D-015, protocol update with fix classes (a/b/c) and hypothesis H-FC.
- Approval: Abdul ("I really like the a b c options").
- Refs: D-015, docs/references/.

### 2026-10-04 ~12:10 PKT — kubectl upgraded; prompt design logged as open item
- Who: Claude, Abdul (prompt discussion)
- What: Installed kubectl 1.37.1 (winget). Harness `_exe` now prefers winget tools over Docker Desktop's bundled kubectl 1.34 (outside ±1 skew with the 1.37 cluster). The baseline local-20261003 used kubectl 1.34 only to apply manifests and wait; all measurements came from k6 inside the cluster, so the band is unaffected. Prompt design (fixed prompt, pre-registered, not tuned on test cases; "keep app working" wording open) added to protocol as an open item for Abdul before P4.
- Result: tests pass (11). Closes issue (2) of the baseline entry.

### 2026-10-04 ~12:20 PKT — P1 exit criterion confirmed; P2 started
- Who: Abdul (confirmation), Claude
- What: Abdul confirmed P1 done (5/5 clean baseline runs, Checkov 0 failed, band recorded and in S3). Phase P2 (case catalogue) started with type 1, privileged container (fix class a).
- Approval: Abdul ("P1 done").

### 2026-10-04 ~12:40 PKT — Docker Desktop fails to start (stale sockets)
- Who: Claude, Abdul
- What: Docker Desktop 4.63.0 failed at start: stale AF_UNIX socket files from the previous session (`Docker\run\dockerInference`, then `docker-secrets-engine\engine.sock`) could not be removed. Renamed `%LOCALAPPDATA%\Docker\run` to `run.stale-20261004` (nothing deleted); second socket then blocked start. Recommended a Windows restart.
- Result: blocked until restart. P2 work so far: injector framework + privileged injector written (uncommitted, untested).

### 2026-10-04 ~13:30 PKT — Architecture page for research fellows
- Who: Claude, at Abdul's request
- What: Wrote `docs/architecture/architecture.html` (Figure 1: one attempt through L1–L7 + feedback loop and gold isolation; Figure 2: laptop vs AWS, built vs planned; phase status; type classification; known gaps). Published as a private artifact: https://claude.ai/artifact/G8uYKrmvr2HQpJ6An9kVZN
- Note: lists open gaps (prompt wording, blocked models, kind NetworkPolicy enforcement, probes on distroless images, coupled fields, moderator grounding, kind in Batch, drift/sample size, verdict audit).

### 2026-10-04 ~13:50 PKT — P2: feasibility probes; scanner runner; case builder/validator
- Who: Claude
- What: Probes on scratch cluster `sbb-p2` (deleted): coupled-field rejection confirmed (D-016); kindnet NetworkPolicy enforcement confirmed (D-017). Added `harness/checks/scanners.py` (Checkov/KICS/kube-score, normalised finding keys; reused by L1/L2), `harness/cases.py` + CLI `case-build`, `case-validate` (V1 flagged incl. declared targets and no unexpected findings, V2 gold clean, V3 dry-run + Ready + L5). Gold scan cached in `app/gold/scan.json`. Injector spec now carries target/coupled rules. Tests: 13 pass.
- Result: privileged-frontend scan validation passed (5 new findings, all declared). Full validation of 3 privileged variants (frontend, checkoutservice, cartservice) running.
- Refs: D-016, D-017.

### 2026-10-04 ~13:50 PKT — Full reproducibility trail set up
- Who: Claude, at Abdul's request ("do all 5")
- What:
  1. Command log: project hook `.claude/settings.json` (PostToolUse + PostToolUseFailure on Bash|PowerShell) runs `scripts/log_command.py`, appending every shell command (UTC time, cwd, command, description, success flag, session id) to `docs/command-log/YYYY-MM-DD.jsonl`. Pipe-tested and proven live (first logged command 07:37:49 UTC).
  2. Trial scripts moved from the scratch folder into `scripts/trials/` with their outputs; README lists each. Gap recorded: the exact trial-2 script was edited in place and not preserved (output kept).
  3. `docs/REPRODUCE.md`: step-by-step rebuild from a clean machine (tools, AWS, gold, caches, L5 trials, baseline, cases).
  4. CLAUDE.md rule 10 added (command log, scripts in repo, REPRODUCE.md, session exports).
  5. Session transcript exported to `docs/sessions/2026-10-04_session-01_p0-p2-start.zip` (sha256 2a236d57801fc393d5ee60dcfa5f21bebab8a798a01eae4ea73b1a0e32ab6d25).
- Approval: Abdul.
- Note: commands before 07:37 UTC on 2026-10-04 are not in the command log; they are reconstructed in REPRODUCE.md and preserved verbatim in the session export.

### 2026-10-04 ~14:00 PKT — P2: privileged cases validated (3/3)
- Who: Claude
- What: `harness case-build privileged <svc>` + `harness case-validate privileged-<svc>` for frontend, checkoutservice, cartservice (fresh kind cluster each; console log in scratch, results in each `cases/*/validation.json`, committed in 6a31a59).
- Result: all 3 valid — declared target rules present, no unexpected findings, gold clean for them, server dry-run OK, all Deployments Available (ready 40.8 / 54.1 / 41.1 s), L5 100%, 0 restarts.
- Next: L7 for the privileged type (Kyverno intent policy + /proc runtime probe via ephemeral debug container).

### 2026-10-04 ~14:05 PKT — Repository stays local
- Who: Abdul (decision)
- What: The git repository is kept local only (no remote, not published). Session exports and docs may therefore contain the account ID, alert email and conversation text.
- Open: backup of the local repo (proposed: end-of-session `git bundle` uploaded to the versioned S3 artifacts bucket) — awaiting Abdul's choice.

### 2026-10-04 ~14:40 PKT — L7 built; APE and capabilities injectors
- Who: Claude (autonomous, per Abdul's instruction to continue without stopping)
- What: Pinned Kyverno CLI v1.19.1 (`latest` is a dev build, rejected). Copied 7 library ValidatingPolicies from kyverno/policies@ec478cb5 into `policies/intent/upstream/`. Wrote `harness/checks/intent.py` (Kyverno apply, /proc probe via ephemeral debug container, applied limits, cross-namespace connect, INTENT registry for 6 types) and `policies/intent/README.md`. Trial `scripts/trials/2026-10-04_l7_proc_probe_privileged.py`: run 1 hit a pod-selection bug (picked a terminating pod; result kept as `.run1-podselect-bug.result.json`), fixed, run 2: gold CapEff 0/CapBnd 0/NoNewPrivs 1/UID 10001; privileged CapEff 0/CapBnd 1ffffffffff/NoNewPrivs 0. Gold passes all 7 Kyverno policies. Injectors `allow-privilege-escalation` (APE true) and `added-capabilities` (SYS_ADMIN); target rules taken from scans (no kube-score rule exists for either). Case validation gains V4 (L7 must flag the case).
- Refs: D-018.

### 2026-10-04 ~15:10 PKT — Class (b)/(c) injectors; line endings pinned
- Who: Claude (autonomous)
- What: `.gitattributes` (LF everywhere, binaries marked) after finding that Windows checkout (core.autocrlf=true) would change hashes verified in code; fresh-clone test confirms upstream sha256 and PDF sha256 intact (commit 142c559). Injectors run-as-root (pod level), missing-limits, netpol (missing policy + deny-all exclusion). Target rules from scans: run-as-root 5 rules (Checkov CKV_K8S_23/40, KICS cf34805e/02323c00, kube-score user-group-id), missing-limits 5 rules (Checkov CKV_K8S_11/13, KICS b14d1bc4/4ac0e2b7, kube-score container-resources), netpol 1 rule (kube-score pod-networkpolicy). Trial on netpol options: permissive policy invisible to all scanners. Case meta now records service_port.
- Refs: D-019.

### 2026-10-04 ~15:30 PKT — P3 groundwork: verdict evaluator, prompt builder, strict parser
- Who: Claude (autonomous)
- What: `harness/evaluate/verdict.py` (deterministic CLAUDE.md §4 rules, 8 tests), `harness/repair/prompt.py` (DRAFT prompt in two wordings, never contains type label / reference fix / gold; strict parser: exactly one yaml block, all expected objects, no duplicates), tests (24 pass).
- Open question for Abdul: CLAUDE.md has no label for L1 pass + L2 fail (target cleared but new findings). Implemented as NOT_FIXED with l2=false recorded so it can be counted separately; to confirm before the pilot.

### 2026-10-04 13:01 PKT — CORRECTION: wrong times in today's entries
- Who: Claude
- What: Entries dated 2026-10-04 from "~13:30" to "~15:30" carry times Claude estimated instead of reading the clock; they are wrong. Real times (git commit time of the work each entry describes):
  - "~13:30 Architecture page" → 12:18 (f27d913)
  - "~13:50 P2: feasibility probes; scanner runner…" → 12:32 (626c34b)
  - "~13:50 Full reproducibility trail set up" → 12:39 (6a31a59)
  - "~14:00 privileged cases validated" → 12:39 (c8d48e0)
  - "~14:05 Repository stays local" → 12:40 (6ae44eb)
  - "~14:40 L7 built; APE and capabilities injectors" → 12:53 (3c0d971)
  - "~15:10 Class (b)/(c) injectors; line endings pinned" → 12:54–12:57 (142c559, fd669e6)
  - "~15:30 P3 groundwork" → 12:59 (a12168e)
  - Also in "Full reproducibility trail": the first logged command was 07:37 UTC = 12:37 PKT.
- Also: `scripts/log_command.py` was briefly broken (a sed edit inserted a newline, ~13:00); 1–2 shell commands in that window are missing from the command log. Fixed and syntax-checked; logger now writes LF.
- Rule from now on: every journal time comes from the system clock (`date`), never estimated.

### 2026-10-04 13:05 PKT — P4 groundwork: feedback builders, leakage and grounding checks; LF writes
- Who: Claude (autonomous)
- What: `harness/moderator/feedback.py`: numbered evidence from the attempt record; C1 scanner-only template (silent once scanner-clean, so C1 ends there, as in prior work); C2 deterministic template (What failed / Evidence / Constraints still required); C2-LLM moderator prompt (temperature 0, prompt sha recorded) with leakage check (code blocks, key: value lines, gold-vs-case diff lines and values) and grounding check (every What-failed bullet cites a known [E#]); 2 regenerations then template fallback, all tries logged. Tests: 29 pass.
- Also: all harness JSON/YAML writes now use LF (case_sha256 must survive checkout). A sed edit broke 4 files for ~1 min (13:03–13:04); repaired with a Python script and syntax-checked; the running validation batch was not affected (its next build ran after the repair, see log line 222).

### 2026-10-04 13:17 PKT — P2: all 9 class (a) cases valid incl. V4 (L7 flags the case)
- Who: Claude (autonomous)
- What: Batch build + validate (log `cases/_validation-classA-20261004.log`) for privileged, allow-privilege-escalation, added-capabilities × frontend, checkoutservice, cartservice.
- Result: 9/9 valid: declared target rules present, no unexpected findings, gold clean, dry-run OK, all Available (ready 43–60 s), L5 100%, and L7 flags each case statically and at runtime (privileged: CapBnd 0x1ffffffffff; APE: NoNewPrivs 0; capabilities: CapBnd 0x200000 = SYS_ADMIN only).
- Fix: `build_case` still wrote CRLF (the earlier newline fix landed on read_text); corrected and all cases rebuilt; verified 0 CR bytes and meta case_sha256 matches every manifest (a grep-based CR count under Git Bash gave false positives; Python byte count is authoritative).

### 2026-10-04 13:18 PKT — Loop stop-rule tests; SSO expired
- Who: Claude (autonomous)
- What: `tests/test_loop.py` (fake Bedrock + fake gates): C0 = 1 iteration; C1 stops once scanner-clean even if breaking; C2-template continues to SAFE_FIX; C2-LLM calls the moderator 3x per round and falls back to the template when ungrounded. 33 tests pass.
- Blocked: AWS SSO token expired (Pricing API call failed). Waiting for Abdul to run `aws sso login --profile secure-but-broken`; local work continues (known-answer tests running, class b/c validation next).

### 2026-10-04 13:29 PKT — P3: known-answer tests of the L1–L7 pipeline (no LLM)
- Who: Claude (autonomous)
- What: `scripts/trials/2026-10-04_p3_known_answer_tests.py` runs hand-made repairs whose right verdict is known, through `run_attempt` (fresh kind cluster each, run alone so L6 is not disturbed). Console: `...console.log`; records: `runs/known-answer/<test>/attempt.json`.
- Result (4/4 correct): gold as repair → SAFE_FIX (all gates true); case unchanged → NOT_FIXED (L1, L2 false); allow-all NetworkPolicy for cartservice → DECEPTIVE_FIX (L1–L6 pass, L7 false: scanners satisfied, traffic from another namespace gets through); 8Mi memory limit → BREAKING_FIX, but at L3 (API rejects request 64Mi > limit 8Mi), not at runtime.
- Next: two more known-answer tests to exercise the runtime gates: OOM at runtime (request = limit = 12Mi, expect L4 fail) and CPU starvation (frontend 20m, expect L6 fail). Running.

### 2026-10-04 13:41 PKT — P3: known-answer tests 6/6; evidence cleaned
- Who: Claude (autonomous)
- Result: OOM at runtime (cartservice request=limit=12Mi) → BREAKING_FIX via L4 (5 restarts); CPU starvation (frontend 20m) → BREAKING_FIX via L6 only (L5 100%, p95 2499 ms vs 251 ms band). With the earlier four, every gate L1, L3, L4, L6, L7 has been shown to fail when it should and the pipeline gives the known verdict 6/6 (L5 sensitivity shown separately, D-014).
- Fix: moderator evidence now lists only unhealthy workloads (transient 'serviceaccount not found' events from parallel object creation were noise) and adds the container's last termination / waiting reason (e.g. OOMKilled).

### 2026-10-04 14:03 PKT — Class b/c validation exposed two instrument bugs; full re-validation started
- Who: Claude (autonomous)
- What: Class b/c batch (log `cases/_validation-classBC-20261004.log`): run-as-root ×3 and missing-limits ×3 valid; netpol ×3 marked invalid. Inspection: run-as-root L7 runtime returned no data (restricted debug profile cannot start as root) — V4 passed for the wrong reason; netpol invalid only because V4 demanded a static policy the type does not have. Both fixed (D-021). Re-validating all 18 cases with the final instrument.
- Refs: D-021.

### 2026-10-04 14:41 PKT — P2: all 18 cases valid with the final instrument
- Who: Claude (autonomous)
- What: Re-validated all 18 cases after D-021 (log `cases/_validation-all18-20261004.log`).
- Result: 18/18 valid. Ready 36–45 s, L5 100% each, V4 holds on real probe data: privileged CapBnd 0x1ffffffffff; APE NoNewPrivs 0; capabilities CapBnd 0x200000; run-as-root effective UID 0 (previously no data); missing-limits only ephemeral-storage applied; netpol connection from another namespace OPEN.
- P2 exit criterion (every case passes case validation) is met for the agreed scope of 6 types × 3 services (D-004, D-012, D-020). Awaiting Abdul's confirmation of P2.

### 2026-10-04 14:46 PKT — Analysis code and draft analysis plan; cost flag
- Who: Claude (autonomous)
- What: `analysis/stats.py` (Wilson, Newcombe risk difference, Fisher, chi-square, exact McNemar, Holm) + `tests/test_stats.py`; scipy added; pytest pythonpath includes repo root. 42 tests pass. Draft analysis plan and rough cost estimate added to protocol.md (to be frozen after the pilot). Cost flag for Abdul: full-manifest prompts and replies may make the full experiment cost more than the monthly budget for the frontier model share; pilot must measure it.

### 2026-10-04 14:52 PKT — P2 confirmed; decisions; first LLM attempt
- Who: Abdul (decisions), Claude
- What: Abdul confirmed P2 done; AWS SSO renewed. Decisions D-022 (L1 pass + L2 fail = NOT_FIXED; both prompt wordings). Discussion opened: Groq instead of Bedrock for cost; GitHub private repo for backup. First real repair started: `harness run-one --case privileged-frontend --model deepseek-v3-2 --condition C0`.
- Approval: Abdul ("P2 done").

### 2026-10-04 15:01 PKT — Laptop L6 flake; decision to move to a dedicated VM; plan shown
- Who: Abdul (decision), Claude
- What: Known-answer re-run "safe_gold_for_privileged" → BREAKING_FIX via L6 only (p95 285.5 ms > 251.2) while Claude ran unit tests on the laptop. Abdul: measure on a clean VM instead. Wrote `infra/terraform/worker-vm.tf` + `worker-vm-userdata.sh` (c6i.2xlarge, 60 GB gp3 encrypted, IMDSv2, SSM, no inbound). Prices via Pricing API: $0.34/h instance, $0.08/GB-month gp3. `terraform plan`: 6 to add, 0 change, 0 destroy (first attempt failed on a sensitive AMI output; fixed with nonsensitive()). NOT applied; awaiting Abdul's OK. GitHub private repo created by Abdul: https://github.com/AbdulHadi1010/SBB-RP (Abdul pushes). vm-sync over SSM agreed instead of CodeDeploy.
- Refs: D-023.

### 2026-10-04 15:04 PKT — Abdul approves VM apply and D-024
- Who: Abdul (approval: "apply"; L6 retest "sure"), Claude
- What: Applying the reviewed plan (6 resources). D-024 recorded.

### 2026-10-04 15:10 PKT — VM created and verified; re-validation on the VM started
- Who: Claude (Abdul approved apply)
- What: `terraform apply` created the VM (i-013e08f65a16a17e5, ami-0045d7fc2ad003464, c6i.2xlarge). First-boot setup verified over SSM: Docker 29.1.3 (Ubuntu package; laptop had 29.2.1), kind 0.33.0, kubectl 1.37.1, uv 0.11.7, 8 vCPU, 15 GiB. `harness vm sync` ships an exact commit (3fe80dd) as a git bundle via S3. On the VM: 42 tests pass; gold-build sha256 08aa0fee… identical to the laptop. Step 2 running: L5 fault injection (`scripts/trials/2026-10-04_vm_l5_sensitivity.py`). Code: `harness/vm.py`, L6 retest rule in run_attempt, AWS profile from environment, L6 band read from `app/baseline/ACTIVE` (still local-20261003 until the VM baseline exists).
- Note: a third escape-sequence slip (cli.py f-strings broken by a heredoc) was caught by an import check before commit; code is now written with the Write/Edit tools only.

### 2026-10-04 15:19 PKT — VM step 2: L5 fault injection, 10/10 detected
- Who: Claude
- What: `scripts/trials/2026-10-04_vm_l5_sensitivity.py` on the VM (SSM output s3://sbb-artifacts-<AWS_ACCOUNT_ID>/ssm/238df288-12cb-45cc-b4f5-96f339f89a6b/; result `app/baseline/vm-l5-sensitivity.json`, also in S3 vm-results/).
- Result: healthy 100%; L5 fails for every one of the 10 backends scaled to 0 (all_detected = true). Same conclusion as on the laptop (D-014).
- Next: 10-run baseline on the VM (label vm-c6i2xl-20261004).

### 2026-10-04 15:56 PKT — VM step 3: 10-run baseline; L6 band switched to the VM
- Who: Claude
- What: `harness baseline --runs 10 --label vm-c6i2xl-20261004` on the VM (SSM output s3://sbb-artifacts-<AWS_ACCOUNT_ID>/ssm/d8ddb182-c8e0-48ba-a851-3bdf9351ed61/; raw files s3://…/baseline/vm-c6i2xl-20261004/, summary `app/baseline/vm-c6i2xl-20261004.json`).
- Result: 10/10 ok, 0 errors, 0 restarts, L5 100%, ready 25.8–33.1 s, p95 11.86 ± 0.88 ms (10.84–13.68). Band (D-013 rule, unchanged): p95 ≤ 14.51 ms, error ≤ 1%. Laptop for comparison: p95 177.5 ± 24.5 ms.
- `app/baseline/ACTIVE` now = vm-c6i2xl-20261004 (laptop baseline kept as tooling evidence only).
- Concern recorded: band is +2.6 ms over the mean and comes from one session on one host; between-session variance is unknown. Checks planned: known-answer gold on the VM, and a second baseline session after stop/start.

### 2026-10-04 15:57 PKT — Dirty-flag fix
- Who: Claude
- What: The VM baseline recorded git_commit "5eed31d…-dirty". Cause: the L5 trial had written its result file into the VM working tree (untracked); the dirty check counted untracked files. The code was the committed 5eed31d (gold sha256 identical, 08aa0fee…). Dirty checks now use --untracked-files=no (tracked changes only); vm-sync uses a forced checkout on the VM (deployment target only).

### 2026-10-04 16:12 PKT — Research pitch doc for outside reviewers
- Who: Claude, at Abdul's request
- What: Shareable doc "Secure but Broken? Research Pitch" (idea, problem, research gap table vs the six prior works from CLAUDE.md, RQs, approach diagram + conditions, early evidence F1–F7, contributions, risks and reviewer questions): https://claude.ai/code/artifact/0399251e-bd0f-4e61-9dce-d6e79c089b29
- Note: prior-work rows summarise CLAUDE.md's reading notes and are flagged in the doc for re-checking against each paper; early-evidence numbers state that the laptop results are being re-run on the VM.

### 2026-10-04 16:19 PKT — VM step 5 done (known-answer 6/6); VM step 4 failed (quoting) and redone as a script
- Who: Claude
- Known-answer on the VM (result `scripts/trials/2026-10-04_p3_known_answer_tests.vm.result.json`, S3 vm-results/): 6/6 correct — gold SAFE_FIX (all gates, inside the 14.5 ms band), unchanged case NOT_FIXED, allow-all netpol DECEPTIVE_FIX (L7), 8Mi BREAKING (L3), OOM BREAKING (L4), CPU-starved BREAKING (L6 only). Confirms the laptop L6 flake was the laptop.
- Case validation on the VM did NOT run: the one-line loop sent through PowerShell → SSM → bash lost its loop variable, so all 18 `case-validate` calls ran with an empty case id (SSM e5ab1cba…, kept as `scripts/trials/2026-10-04_vm_validation_attempt1_quoting_bug.txt`). The validation.json files on disk are still the laptop ones. Redone as a committed script `scripts/vm/validate_all_cases.sh` (no inline quoting).

### 2026-10-04 16:44 PKT — VM step 4: all 18 cases valid on the VM; re-validation on the VM complete
- Who: Claude
- What: `bash scripts/vm/validate_all_cases.sh vm-validation-20261004` on the VM (SSM 93567857…; log `cases/_validation-vm-20261004.log`; files s3://…/vm-results/vm-validation-20261004/). First local download used `aws s3 sync`, which skipped 15 of 18 files as "unchanged"; re-copied with `aws s3 cp --recursive` and verified all 18 validation.json now carry the VM run's timestamps (11:19–11:41 UTC).
- Result: 18/18 valid, V4 18/18, L5 100% each, ready 25.8–34.4 s.
- VM re-validation (D-024) complete: tools identical, gold hash identical, L5 fault injection 10/10, baseline 10/10 (band p95 ≤ 14.51 ms), 18/18 cases valid, known-answer 6/6. Ready for the first LLM repairs.

### 2026-10-04 16:51 PKT — First real LLM repair (P3 exit criterion met)
- Who: Claude
- What: On the VM: `harness run-one --case privileged-frontend --model deepseek-v3-2 --condition C0` (SSM 8f1d2ca6…; run_id 20261004T114422Z-privileged-frontend-deepseek-v3-2-C0-r1-bfe231; s3://sbb-artifacts-<AWS_ACCOUNT_ID>/chains/<run_id>/; DynamoDB item present; git 71cfa0e).
- Result: SAFE_FIX on iteration 1 — all gates L1–L7 pass. 8,022 input / 7,791 output tokens, 90 s model time, 233 s for the gates. The model changed only Deployment/frontend: privileged true→false and restored allowPrivilegeEscalation: false (the coupled field), identical to the reference fix.
- P3 exit criterion (one case runs L1–L7 + verdict + S3 upload) met; awaiting Abdul's confirmation. Note: tokens per attempt (~16k) are lower than the earlier rough estimate (~37k); the pilot will measure properly.

### 2026-10-04 17:06 PKT — Exploratory smoke run started (D-025)
- Who: Abdul (request), Claude
- What: D-025 recorded before running. `bash scripts/vm/smoke_run.sh deepseek-v3-2` on the VM: C0 on one case per type. Excluded from analysis; no case changes in response.

### 2026-10-04 17:46 PKT — Smoke run results (exploratory, D-025)
- Who: Claude
- What: `scripts/vm/smoke_run.sh deepseek-v3-2` (SSM b3bcdb97…; log s3://…/vm-results/smoke-deepseek-v3-2.log; records under s3://…/chains/).
- Result: 5 SAFE_FIX (APE-checkout, capabilities-cart, run-as-root-frontend, missing-limits-cart, privileged-checkout; each repair semantically identical to gold), 1 BREAKING_FIX (netpol-cartservice: egress restricted to redis only, DNS forgotten; L5 and L6 fail, L7 BLOCKED = secure). Tokens ~8.0k in / ~7.8k out per attempt. Findings F8, F9. Excluded from analysis; no case changes made in response.

### 2026-10-04 18:06 PKT — D-026; P4 loop check started
- Who: Abdul (decision), Claude
- What: Keep current cases (F9 as limitation); later problems as a separate batch. Started `bash scripts/vm/loop_check.sh netpol-cartservice deepseek-v3-2` on the VM (exploratory, not counted).

### 2026-10-04 18:18 PKT — P5 design D-027 (fleet + queue); code and plan
- Who: Abdul (decision B), Claude
- What: `harness/fleet.py` (enqueue + manifest, worker qualification on gold, work loop, completeness), CLI `enqueue`, `worker`, `completeness`; run_chain records batch, worker and active baseline and writes a done marker. `harness vm wait` re-attaches after the laptop lost its network mid-poll (VM job 79fa1144 kept running). Terraform `fleet.tf` + `fleet-userdata.sh`: plan 3 to add (SQS jobs queue, DLQ, SQS policy on the worker role), 0 change, 0 destroy; fleet size 0. Not applied; awaiting Abdul's OK. AMI of the VM to be made after the loop check finishes.
- Refs: D-027.

### 2026-10-04 18:20 PKT — Queue applied
- Who: Claude (Abdul: "apply")
- What: `terraform apply` of the reviewed plan: SQS `sbb-jobs` (https://sqs.us-east-1.amazonaws.com/<AWS_ACCOUNT_ID>/sbb-jobs), `sbb-jobs-dlq`, SQS policy on the worker role. Fleet still size 0.

### 2026-10-04 19:25 PKT — P4 loop check results; C2 instrument fixes (D-028)
- Who: Claude
- What: Loop check on the VM (SSM 79fa1144…; runs in s3://…/chains/20261004T13*-netpol-cartservice-deepseek-v3-2-*). C1: BREAKING at it1 (stops when scanner-clean, as designed). C2-template: BREAKING, NOT_FIXED (hallucinated shoppingassistantservice), BREAKING, NOT_FIXED ×2. C2-LLM: BREAKING ×4 (moderator fell back to template 3×), then INVALID_OUTPUT (deny-all NetworkPolicy omitted). Input tokens grew to ~43k by iteration 5.
- Fixes: grouped citations, error lines from all pods, explicit evidence wording (D-028); 44 tests pass. Findings F10, F11.
- Open for Abdul: should a reply that omits an object be INVALID_OUTPUT (current) or be judged by the gates?

### 2026-10-04 20:05 PKT — D-029 implemented
- Who: Abdul (decision B), Claude
- What: parser no longer rejects missing objects; `removed_objects` recorded in each attempt.json; tests updated (45 pass).

### 2026-10-04 21:21 PKT — Loop check re-run after D-028; progress report; end of day
- Who: Claude (Abdul asked to stop for today)
- What: Loop check re-run on the VM (SSM 3141ff1d…): C1 BREAKING_FIX (1 iteration); C2-template SAFE_FIX in 4; C2-LLM SAFE_FIX in 3 (moderator accepted first try every round, no leakage, diagnosed DNS failures). Exploratory, not counted. New findings F12 (first sign of the RQ4 effect), F13 (a "safe" repair deleted the namespace deny-all policy; not measured today — decision needed before the pilot), F14 (noisy INFO lines in error evidence). Corrected F6 for the VM: CPU-starved p95 657 ms vs 11.9 ms (~55x); the 2,499 ms figure was the laptop's.
- Report: `docs/reports/2026-10-04-progress-report.pdf` built by `scripts/reports/build_progress_report.py` from the result files (5 pages).
- Cost Explorer showed USD 0.03 for October (lag); estimate for today: VM ~7 h (~USD 2.40) + ~30 Bedrock calls (< USD 2). To confirm tomorrow.
- VM stopped. Open for Abdul: F13 decision; F14 filter; worker AMI + fleet plan; the pitch doc still quotes the laptop F6 figure (2,499 ms vs ~250 ms) and should be updated to the VM numbers.

### 2026-10-06 14:22 PKT — Session start (Abdul at office, answering by phone); F14 fixed
- Who: Abdul (instructions), Claude
- What: Remote Control enabled for this session, keep-awake on; AWS SSO renewed with a device-code login approved by Abdul. Abdul asked to continue the plan indefinitely. F14: error-line evidence now drops lines their logger marks INFO/DEBUG/TRACE (`is_error_line`), with tests (47 pass). Open for Abdul: F13 decision.

### 2026-10-06 14:23 PKT — F13 decided: L7 no-regression rule (D-030)
- Who: Abdul (decision, by phone), Claude
- What: L7 now = target intent AND no regression (other workloads pass all 7 Kyverno policies; no given NetworkPolicy removed/narrowed; all 10 gold-shielded services still block outside traffic). `harness/checks/intent.py` (regression, regression_static, protected_services), tests (51 pass), intent README + protocol updated, known-answer test 7 added (deny-all deleted → DECEPTIVE_FIX). Next: run the 7 known-answer tests on the VM.
- Refs: D-030.

### 2026-10-06 14:25 PKT — Drafts for approval: prompt freeze v1, literature-search protocol; pitch figure corrected
- Who: Claude
- What: `docs/prompt/prompt-freeze-v1.md` (generated from code: system sha256 c3d3f9fe6a00…, moderator 0ac76815560b…, both wordings, settings). `docs/lit-review/search-protocol.md` (sources, search string, inclusion/exclusion, screening with 20% re-check, PRISMA counts, extraction fields, seed set). Pitch doc: F6 example updated to VM figure (657 ms vs 12 ms) and deny-all example added. Known-answer tests (7) running on the VM.

### 2026-10-06 14:54 PKT — Known-answer tests 7/7 with D-030 on the VM
- Who: Claude
- What: `bash scripts/vm/known_answer.sh known-answer-d030` on the VM (SSM 421b0f29…; s3://…/vm-results/known-answer-d030/; result `scripts/trials/2026-10-06_known_answer_d030.vm.result.json`).
- Result: 7/7 correct. New test "deny-all deleted" → DECEPTIVE_FIX with target_pass=true and regression = "NetworkPolicy 'deny-all' was removed"; gold → SAFE_FIX with regression ok (no other-workload policy failures, no netpol problems, all 10 shielded services BLOCKED). VM stopped afterwards.

### 2026-10-06 15:03 PKT — Approvals: prompt freeze, search protocol, fleet (D-031)
- Who: Abdul (by phone: "Freeze", "Approve", "Go fleet"), Claude
- What: PROMPT_VERSION set to v1-frozen-2026-10-06 (texts unchanged); freeze doc and search protocol marked approved; protocol.md updated. Next: AMI of the stopped VM, then fleet plan + pilot design + cost for Abdul.
- Refs: D-031.

### 2026-10-06 15:03 PKT — Worker AMI created
- Who: Claude (approved by Abdul: "Go fleet")
- What: `aws ec2 create-image --instance-id i-013e08f65a16a17e5 --name sbb-worker-20261006` (VM stopped, consistent snapshot; tagged Project=secure-but-broken). AMI: ami-0ae9b34326f1f5a20. Snapshot cost ~USD 0.05/GB-month of used blocks.

### 2026-10-06 15:05 PKT — Credits do NOT cover Claude models (CLAUDE.md credits caveat); unknown services in the account
- Who: Claude
- What: Pricing API: DeepSeek V3.2 USD 0.62 / 1.85 per M tokens (in/out), GPT-OSS 120B 0.15 / 0.60, Claude Sonnet 4.6 (US CRIS) 3.30 / 16.50, Claude Haiku 4.5 ~1.10 / 5.50 — Claude models are "AWS Marketplace software usage". Cost Explorer Oct 1–6 by record type: Bedrock (DeepSeek/GPT-OSS) 0.68 fully credited; EC2/S3/DynamoDB credited; Claude Haiku 4.5 0.17 and Sonnet 4.6 0.0001 charged as Usage with NO credit line (cash).
- Also seen in the account, not created by this project: EKS 0.37, EFS 0.57, RDS 0.05, KMS 0.33, Amplify (credited). Reported to Abdul; nothing touched.
- Blocked: pilot design waits for Abdul's decision on Claude (cash) vs credit-covered models, and on the moderator model.

### 2026-10-06 15:14 PKT — Credits-only model set (D-032); Claude credits route
- Who: Abdul ("move the whole project to credits only… use those whether they are chinese or whatever"), Claude
- What: Researched free Claude routes: Groq (no Claude), OpenRouter (Claude at provider price + 5.5%), Gemini (free, not Claude), Anthropic AI for Science (up to USD 20k API credits, academic affiliation) — drafted a message for Prof. Zulkifl Hassan (UCP). Pricing API: all candidate open models are AWS-sold. Probe (`scripts/trials/2026-10-06_credit_model_probe.py`): 13/15 callable (Qwen3-Coder-480B id invalid, Nova Premier end of life; Kimi K3 now callable). New set: Kimi K3, GLM-5, DeepSeek V3.2; moderator Mistral Large 3. cost_usd per call added (harness/config/prices.json). 52 tests pass.
- Refs: D-032.

### 2026-10-06 15:30 PKT — Format-only check of D-032 models on the VM (exploratory, excluded)
- Who: Claude (autonomy granted by Abdul)
- What: Started VM i-013e08f65a16a17e5, synced commit, ran `scripts/trials/2026-10-06_format_check.py` (frozen first prompt, case privileged-frontend; parse only, no gates, no verdict), stopped VM. Note: the local `[default]` AWS profile holds the deactivated access key; all harness commands must run with AWS_PROFILE=secure-but-broken.
- Result: all 5 repairers parse (45 docs each). Cost per first call: Kimi K3 $0.124 (but reported only 7 input tokens, investigating), GLM-5 $0.032, DeepSeek V3.2 $0.019, GPT-OSS 120B $0.006, Qwen3-Coder-Next $0.014. Wall: 47–183 s. Moderator Mistral Large 3: grounded, leakage-clean message on first try ($0.005, 3 s).
- Refs: scripts/trials/2026-10-06_format_check.json.

### 2026-10-06 15:40 PKT — Cache-token accounting fix (F15); pilot design proposed
- Who: Claude
- What: Kimi K3 reports cached prompt tokens separately (cacheWriteInputTokens 483, inputTokens 7 in a probe). bedrock.converse now counts cache read/write tokens in input_tokens and cost (full input price = upper bound) and keeps the raw fields; test tests/test_bedrock_usage.py; 54 tests pass. Protocol: moderator line updated to Mistral Large 3; pilot design written (3 checkoutservice cases, one per fix class; Kimi K3 + DeepSeek V3.2; 4 conditions x 3 repeats x 2 wordings = 144 chains), awaiting Abdul's OK with cost estimate and fleet plan.
- Refs: F15, docs/protocol.md "Pilot (P6) design".

### 2026-10-06 15:50 PKT — Fleet self-stop fix; fleet plan for pilot shown
- Who: Claude
- What: Found fleet-userdata.sh never stopped the instance after the worker exited (idle VMs would keep running, ~USD 33/day for 4). Added an EXIT trap: upload /var/log/sbb-worker.log to s3://sbb-artifacts-<AWS_ACCOUNT_ID>/fleet-logs/<commit>/, then shutdown (behaviour = stop). `terraform plan` (fleet_size=4, fleet_ami=ami-0ae9b34326f1f5a20, fleet_commit=11eeb15): 4 to add, 0 change, 0 destroy. Not applied; awaiting Abdul's OK with the pilot cost estimate.
- Refs: commit 11eeb15.

### 2026-10-06 15:36 PKT — P3 confirmed; unknown charges explained; pilot models changed (D-033)
- Who: Abdul, Claude
- What: Abdul confirmed "P3 done". Abdul: EKS and EFS charges come from his older projects (not this project; untouched). RDS, KMS, Amplify still unexplained. Pilot models changed from Kimi K3 + DeepSeek V3.2 to Kimi K3 + GLM-5 (D-033). Revised pilot estimate: expected ~USD 35, worst case ~USD 92, all credit-covered. Still awaiting "Go pilot".
- Refs: D-033, docs/protocol.md.

### 2026-10-06 16:40 PKT — Abdul: "Go Pilot"; remaining unknown charges explained
- Who: Abdul (approval), Claude
- What: Abdul confirmed RDS, KMS and Amplify charges are from his older projects (with EKS, EFS: all unrelated, untouched). Abdul approved the pilot (D-033 design, 144 chains, est. ~USD 35 / max ~USD 92, credit-covered) and the 4-VM fleet. Because done-markers do not encode the wording, the pilot is queued as two batches: pilot-W0 and pilot-W1 (72 chains each).

### 2026-10-06 16:42 PKT — Pilot started: 144 chains queued, 4-VM fleet created
- Who: Claude (approved by Abdul: "Go Pilot")
- What: Uploaded code bundle for commit 0827d4d to s3://sbb-artifacts-<AWS_ACCOUNT_ID>/code/. Enqueued batches pilot-20261006-W0 and pilot-20261006-W1 (72 chains each; cases privileged/run-as-root/netpol-checkoutservice; models kimi-k3, glm-5; C0, C1, C2-LLM, C2-template; 3 repeats); queue was empty before (0/0), 144 after. `terraform apply fleet.tfplan` (fleet_size=4, ami-0ae9b34326f1f5a20, fleet_commit=0827d4d): created i-0c27ddfc9d662843a, i-099ffe0daf5d98d4a, i-088102ede731ca873, i-07cc21319564de513. Each worker qualifies on gold before taking jobs and stops itself when idle 15 min.
- Refs: batches/pilot-20261006-W0|W1/manifest.json.

### 2026-10-06 17:27 PKT — Fleet start failed (no work done); cause found and fixed; replacement plan awaiting OK
- Who: Claude
- What: All 4 fleet VMs stopped ~1 min after boot without qualifying (no chains run, queue still 144). Console output: the user-data inner script ran 0.7 s and printed nothing. Cause: `sudo -iu ubuntu bash -lc '<multi-line>'` — sudo -i escapes the command, newlines become line continuations, the script collapses into `set -e aws s3 cp ...` (sets positional args, runs nothing, exit 0), then the EXIT trap shut the VM down. Reproduced and fix verified on the measurement VM (scripts/vm/debug_fleet_userdata.sh): `sudo -u ubuntu -H bash -lc` runs every step. Fixed fleet-userdata.sh (also set -x, flush delay before log upload) and added user_data_replace_on_change = true (user data only runs on first boot). Bundle for e12a790 uploaded. Plan: 4 to add, 0 to change, 4 to destroy (replace the 4 stopped, empty fleet VMs). Not applied: awaiting Abdul's OK because it destroys instances. Measurement VM stopped. Cost of the failed start: ~4 VM-minutes (< USD 0.10).
- Refs: commit e12a790.

### 2026-10-06 17:32 PKT — Fleet replaced (Abdul: "Replace")
- Who: Claude (approved by Abdul)
- What: `terraform apply fleet.tfplan` (fleet_commit e12a790): destroyed the 4 stopped, empty fleet VMs and created i-0a710ccafebc2764f, i-0b5c40557f7319d06, i-0c7b299edabcd510a, i-02ddbd14db83e0b01. 4 added, 0 changed, 4 destroyed.

### 2026-10-06 17:47 PKT — Fleet qualification: 3 of 4 workers qualified; pilot running
- Who: Claude
- What: Gold qualification on the new fleet: i-0a710ccafebc2764f SAFE_FIX p95 11.99 ms, i-0c7b299edabcd510a SAFE_FIX 11.63 ms, i-02ddbd14db83e0b01 SAFE_FIX 12.07 ms; i-0b5c40557f7319d06 BREAKING_FIX (L6 only: p95 20.02 ms > band 14.51 ms) -> refused work and stopped itself, as designed (F16). Queue: 141 waiting, 3 in progress. Pilot continues on 3 workers.
- Refs: F16, s3://sbb-artifacts-<AWS_ACCOUNT_ID>/workers/.

### 2026-10-06 23:02 PKT — Pilot W0 complete; summary script; instrument bug found and fixed (D-034)
- Who: Claude
- What: Re-logged SSO via device code (Abdul approved on phone). W0 72/72, W1 49/72 at 22:59, DLQ 0. New analysis/pilot_summary.py (S3 -> analysis/out/*.csv + tables). W0: Kimi K3 35 SAFE + 1 INVALID (gibberish, F17); GLM-5 28 SAFE, 6 DECEPTIVE, 1 NOT_FIXED, 1 BREAKING_AND_DECEPTIVE, all non-safe on netpol-checkoutservice (deny-all deleted, F18). Repeat agreement 19/24 cells. Cost W0: Kimi USD 5.74, GLM USD 2.29. Found C2 evidence empty for regression-only L7 failures -> fixed (D-034), 55 tests pass. W1 still running on the pre-fix commit (left untouched).
- Refs: D-034, F17, F18.

### 2026-10-07 00:56 PKT — Pilot complete (144/144); D-034 re-run started
- Who: Claude (Abdul: "Re-run the cells hit by the bug ... then just write a report and stop")
- What: pilot-20261006-W0 72/72 and -W1 72/72 done, DLQ 0, all fleet VMs stopped themselves (W1 done 00:31). Enqueued pilot-fix-20261007-W0 and -W1 (12 chains each: netpol-checkoutservice x kimi-k3, glm-5 x C2-LLM, C2-template x 3 repeats). Started the 3 qualified fleet VMs (i-0a710ccafebc2764f, i-0c7b299edabcd510a, i-02ddbd14db83e0b01) and launched the worker via SSM with scripts/vm/fleet_rerun_worker.sh. Two failed launches first (no jobs taken): root-owned /tmp/repo.bundle blocked the download; then SSM killed the nohup'd child. Fixed: bundle in /home/ubuntu, start via systemd-run. Workers running commit bd026d6 (includes D-034); each re-qualifies on gold first.

### 2026-10-07 02:40 PKT — D-034 re-run complete; pilot report; work paused for cost confirmation
- Who: Claude (Abdul: "write a report and stop for now so that I can confirm the total cost")
- What: pilot-fix-20261007-W0/W1 24/24 done, DLQ 0, VMs stopped themselves (02:38). GLM-5 C2 on netpol: 11/12 SAFE after fix vs 4/12 before; feedback rescued 4 chains (0 before). Cost: harness estimate ~USD 30 total for the pilot (models USD 18.8, EC2 ~USD 9.5); Cost Explorer so far (incomplete): October usage USD 12.92, credits -12.76, net 0.17 (Haiku, 2026-10-04). Report docs/reports/2026-10-07-pilot-report.md; chain tables analysis/out/*.csv. All instances stopped. Stopped: awaiting Abdul's cost confirmation and decisions (repeats, P7 budget, fleet VMs, protocol freeze).

### 2026-10-07 02:45 PKT — Session transcript exported
- Who: Claude
- What: Exported this session's transcript to docs/sessions/2026-10-07-session-export.zip (9.5 MB; source C:\Users\DELL\Downloads\session-export-1791322849600.zip).

### 2026-10-07 12:42 PKT — Paused one day (Abdul)
- Who: Abdul
- What: Wait one more day: confirm final pilot cost in Billing; supervisor (Prof. Zulkifl Hassan) has applied for Anthropic AI for Science credits. Model set and protocol freeze wait for that outcome. All VMs stopped; no runs queued.

### 2026-10-07 13:04 PKT — Plain-language pilot walkthrough doc
- Who: Claude (Abdul: "write me a document that is simplified and walks us through what we did and how did the test go ... proper graphs")
- What: Claude Docs doc "Pilot Walkthrough: Secure but Broken?" (https://claude.ai/code/artifact/34934008-102f-4e5e-af68-14f37926cbd9): pipeline diagram, verdicts-by-model chart, bug-fix before/after chart, cost and problems tables, next decisions. Numbers from analysis/out pilot tables and docs/reports/2026-10-07-pilot-report.md.

### 2026-10-14 14:08 PKT — Decisions for P7; protocol frozen (D-035)
- Who: Abdul (decisions), Claude
- What: Abdul: no Anthropic credits; pilot bill confirmed final; 5 repeats (netpol cases; 3 elsewhere); freeze protocol; full-run spend approved; start P7 ASAP, full audit trail, contact by phone. Claude rewrote docs/protocol.md as FROZEN v1 (design 1,440 chains; W0 primary; stale L6 band and open items corrected; cost section removed). Laptop SSO expired; device-code login sent to Abdul.
- Refs: D-035, tag protocol-v1-frozen.

### 2026-10-14 14:12 PKT — P7 full experiment started
- Who: Claude (approved by Abdul: "start the full experiment ASAP")
- What: SSO re-login (device code, approved by Abdul). 55 tests pass; queues empty before. Enqueued 1,440 chains in 4 batches: p7-20261014-W0-std (540), p7-20261014-W0-netpol (180), p7-20261014-W1-std (540), p7-20261014-W1-netpol (180); models kimi-k3, glm-5, deepseek-v3-2; conditions C0, C1, C2-LLM, C2-template; repeats 3 (std) / 5 (netpol). Code bundle for commit ab4b526 (tag protocol-v1-frozen) uploaded. `terraform apply fleet.tfplan` (fleet_size=4, ami-0ae9b34326f1f5a20, fleet_commit=ab4b526): replaced the 4 stopped pilot fleet VMs with i-0f071573463a5a2e5, i-06d8ae62f07a357e8, i-0e97b3a8c1758f16e, i-060c0e3ad90a43fde (4 added, 4 destroyed). Each qualifies on gold before taking work.
- Refs: D-035; s3://sbb-artifacts-<AWS_ACCOUNT_ID>/batches/p7-20261014-*/manifest.json.

### 2026-10-14 14:30 PKT — P7 workers qualified
- Who: Claude
- What: All 4 workers passed gold qualification (SAFE_FIX; p95 12.11, 12.97, 10.59, 12.28 ms; band 14.51 ms). Queue: 1,436 waiting, 4 in progress. Added scripts/vm/watch_p7.sh (read-only progress watch; stops on DLQ, a stopped worker, expired login or completion).

### 2026-10-14 15:08 PKT — P7 sanity check of first chains
- Who: Claude
- What: First 2 finished chains per model (added-capabilities-cartservice, C0) all parse and run every gate on commit ab4b526 across 3 workers; DeepSeek V3.2 works on the final pipeline (8.0k in / 7.8k out tokens, 113-163 s model time). Attempt time ~276-283 s. No intervention.

### 2026-10-14 22:58 PKT — P7 progress; laptop SSO expired
- Who: Claude
- What: At 21:56: 260/1,440 chains done (W0-std 249, W0-netpol 1, W1-std 5, W1-netpol 5), DLQ 0, 4 workers running (~34 chains/hour). Laptop SSO expired ~22:10; workers unaffected (instance role). Device-code login sent to Abdul's phone.

### 2026-10-15 10:13 PKT — P7 progress 638/1,440
- Who: Claude
- What: Laptop SSO expired ~07:00 (morning link not used); new device-code login approved by Abdul 10:13. Progress: W0-std 532/540, W0-netpol 87/180, W1-std 12/540, W1-netpol 7/180 = 638/1,440; DLQ 0; 4 workers running. Rate dropped to ~23 chains/h while network-policy chains (often 5 iterations) run; estimated finish ~16 Oct afternoon.

### 2026-10-15 18:32 PKT — P7 progress 882/1,440; W0 complete
- Who: Claude
- What: At 18:11: W0-std 540/540, W0-netpol 180/180 (W0 complete, 720 chains), W1-std 155/540, W1-netpol 7/180 = 882/1,440; DLQ 0; 4 workers running (~30 chains/h since 10:13). Laptop SSO expired 18:32; new device-code login sent to Abdul.

### 2026-10-16 14:27 PKT — P7 complete
- Who: Claude (SSO re-login approved by Abdul)
- What: Completeness check: p7-20261014-W0-std 540/540, -W0-netpol 180/180, -W1-std 540/540, -W1-netpol 180/180 = 1,440/1,440, nothing missing. SQS sbb-jobs 0/0, DLQ 0 (no chain failed twice). All 4 fleet workers stopped themselves when the queue stayed empty (user-initiated shutdown from inside the VM). Laptop monitoring gap 21:04-14:25 (SSO expired overnight); workers unaffected. Next: build chain tables from S3 (analysis/pilot_summary.py), verify every chain ran commit ab4b526, then the frozen analysis plan.
- Refs: D-035; s3://sbb-artifacts-<AWS_ACCOUNT_ID>/batches/p7-20261014-*/.

### 2026-10-16 14:44 PKT — P7 integrity check and pre-registered analysis
- Who: Claude (Abdul: "please continue")
- What: Chain table from S3 (analysis/pilot_summary.py over the 4 P7 batches): 1,440 rows, 0 missing, all on commit ab4b526 (no -dirty), workers 347-379 chains each; first chain done 2026-10-14 14:29, last 2026-10-16 13:12. New analysis/p7_analysis.py (frozen plan, D-036) + stats.fisher_2x2(alternative) and stats.rxc_exact with tests (57 tests pass). Outputs analysis/out/p7-results-W0.md/.json (primary), -W1, -wording.md. Headline W0: SAFE_FIX 680/720 (94.4%); breaking among scanner-clean 29/714 (4.1%), deceptive 8/714 (1.1%), all of them NetworkPolicy cases; RQ4 family all three rejected after Holm (C2-LLM vs C1 p_holm 0.031, C2-LLM vs C0 0.012, C2-template vs C1 0.023); C2-LLM vs C2-template n.s. (p 0.51). W1 same direction.
- Refs: D-036.

### 2026-10-16 14:47 PKT — Verdict audit of 30 P7 chains: 30/30 consistent
- Who: Claude (Abdul: "please do")
- What: scripts/trials/2026-10-16_verdict_audit.py (stratified sample, seed 20261016, rule fixed before reading: 12 SAFE (2/type), 8 breaking, 5 deceptive, 5 not-fixed/invalid). Final iteration of each chain re-checked independently of the gates (verdict recomputed from gates; repaired manifest parsed for the target property; NetworkPolicies removed vs case input; functional and load numbers vs band). 30/30 consistent. Breaking = checkout journeys failing (netpol-checkoutservice) or all pages failing, p95 ~6,000 ms (DeepSeek netpol-cartservice); deceptive = deny-all deleted (5/5, all GLM-5); NOT_FIXED = target fixed but a new KICS finding on another Deployment (L2, rule as decided); INVALID = no complete yaml block. Added uv dependency group "analysis" (statsmodels 0.15.0, matplotlib 3.11.2), not installed on workers.
- Refs: scripts/trials/2026-10-16_verdict_audit.json/.md.

### 2026-10-16 14:52 PKT — P7 sensitivity regression and paper figures
- Who: Claude
- What: analysis/p7_regression.py (D-037): mixed-effects logistic regression of SAFE_FIX, variational Bayes. All 1,440 chains, vs C1: C2-LLM OR 5.3 [2.7, 10.2], C2-template OR 16.9 [7.2, 40], C0 OR 1.27 [0.76, 2.15]; DeepSeek vs Kimi OR 0.054; NetworkPolicy vs privileged OR 0.049; W1 vs W0 OR 0.94 [0.62, 1.43]. W0 only: same conclusions. analysis/figures.py: 4 figures (PNG 300 dpi + PDF) from the chain table with the analysis definitions; palette validated (3 categorical slots, all-pairs pass; low-contrast aqua carries marker + label). REPRODUCE.md updated with the analysis steps.
- Refs: D-037, analysis/out/p7-regression.md, analysis/figures/.

### 2026-10-16 15:08 PKT — P8 built (no AWS change yet)
- Who: Claude (Abdul: "please continue and complete P8 as soon as possible")
- What: docs/p8-plan.md (D-038) written before any EKS run; sample drawn and frozen (scripts/p8/sample.json: 48 SAFE, 31 BREAKING, 6 DECEPTIVE, 3 BREAKING_AND_DECEPTIVE; 46 NetworkPolicy cases). infra/terraform/eks.tf (eks_enabled=false default; plan with it off = no changes). EKS mode in harness/deploy/kind.py + SBB_BASELINE override in attempt.py; tests/test_platform.py; 60 tests pass. scripts/p8/replay.py, scripts/vm/p8_run.sh. EKS 1.37 confirmed available (aws eks describe-cluster-versions). Next: terraform plan with eks_enabled=true, shown to Abdul for approval.
- Refs: D-038.

### 2026-10-16 15:45 PKT — P8 terraform plan shown; awaiting Abdul's OK
- Who: Claude
- What: `terraform plan -var eks_enabled=true` -> 15 to add, 0 to change, 0 to destroy (EKS cluster sbb-p8 1.37, node group 2 x c6i.2xlarge, addons vpc-cni (NetworkPolicy on) / coredns / kube-proxy, cluster + node IAM roles, access entry + cluster-admin association for the measurement VM role, eks:DescribeCluster policy on that role, SG rule VM -> API 443). Not applied.

### 2026-10-16 15:10 PKT — P8 apply approved and started
- Who: Claude (Abdul: "apply")
- What: `terraform apply eks.tfplan` started (15 to add). Measurement VM i-013e08f65a16a17e5 started and synced to drive P8.

### 2026-10-16 15:22 PKT — Correction; EKS cluster created
- Who: Claude
- What: Correction to the entry "2026-10-16 15:45 PKT — P8 terraform plan shown": its time was typed by hand, not taken from the clock; the plan was shown shortly before 15:00 (apply finished 15:21 by `date`). Rule kept: times only from `date`. Apply result: 15 added, 0 changed, 0 destroyed (cluster sbb-p8 9m18s, node group 1m50s, addons vpc-cni/kube-proxy/coredns, access entry for role sbb-worker-vm).

### 2026-10-16 15:24 PKT — P8 driver started on the measurement VM
- Who: Claude
- What: VM -> EKS access verified (2 nodes Ready, server v1.37.0-eks, kubectl v1.37.1, VPC CNI network policy agent running with --enable-network-policy=true). Started `systemd-run --unit sbb-p8 scripts/vm/p8_run.sh eks-p8-20261016 8b0526f` as root on i-013e08f65a16a17e5: EKS baseline (10 gold runs) running, then 88 replays. Output to s3://sbb-artifacts-<AWS_ACCOUNT_ID>/p8/eks-p8-20261016/.

### 2026-10-16 16:27 PKT — P8 EKS baseline done; replays running
- Who: Claude
- What: EKS baseline eks-p8-20261016: 10/10 clean; p95 mean 10.89 ms, SD 0.95 -> band p95 <= 13.75 ms, error <= 1% (kind VM band: 14.51 ms). Versions: EKS v1.37.0-eks-6c518f7, nodes c6i.2xlarge AL2023, containerd 2.3.5, amazon-k8s-cni v1.22.4, aws-network-policy-agent v1.4.0. Copied to app/baseline/eks-p8-20261016.json (NOT named in ACTIVE; used only via SBB_BASELINE). Replays started; 1/88 netpol-cartservice kind=SAFE_FIX eks=SAFE_FIX.

### 2026-10-16 23:40 PKT — P8 interim: 67/88 replayed
- Who: Claude (SSO re-login approved by Abdul after two expired codes)
- What: 67/88 replays done, VM running. Interim agreement 66/67 (98.5%), kappa 0.974; NetworkPolicy 36/36; gates L3-L5, L7 100%, L6 66/67. Only disagreement so far: missing-limits-cartservice (DeepSeek) BREAKING_FIX on kind (L6 only) -> SAFE_FIX on EKS (p95 10.99 ms vs band 13.75 ms). Interim numbers only; final analysis after 88/88.

### 2026-10-17 01:01 PKT — Abdul approves EKS teardown after P8
- Who: Abdul ("once its done you have the go ahead to delete the cluster")
- What: Approval to destroy the P8 EKS resources (the 15 created by eks_enabled=true) once all 88 replays are done and their results are in S3. Plan: terraform plan with eks_enabled=false must show only those 15 destroys, 0 add, 0 change; anything else stops the teardown.

### 2026-10-17 02:13 PKT — P8 complete; EKS destroyed
- Who: Claude (teardown approved by Abdul in advance)
- What: P8 driver finished 01:50 (DONE marker); 88/88 replay results in s3://sbb-artifacts-<AWS_ACCOUNT_ID>/p8/eks-p8-20261016/, driver log without errors or infrastructure re-runs; measurement VM stopped itself. Teardown plan (eks_enabled=false): 0 add, 0 change, 15 destroy, all P8 resources -> applied: 15 destroyed. `aws eks list-clusters`: none. Laptop SSO gap 22:30-23:38 (two device codes expired before approval).

### 2026-10-17 02:16 PKT — P8 analysis
- Who: Claude
- What: analysis/p8_agreement.py on all 88: agreement 87/88 (98.9% [93.8, 99.8]), kappa 0.980; NetworkPolicy 46/46; safe 48/48; non-safe 39/40. Only disagreement: borderline L6 on a 300m CPU limit (kind p95 15.1/20.3 ms vs 14.5; EKS 11.0 vs 13.75). F19; report docs/reports/2026-10-17-p8-eks-validation.md.

### 2026-10-17 09:48 PKT — P9: number macros, draft v0, reproducibility check pending
- Who: Claude (Abdul: "Continue")
- What: analysis/paper_numbers.py -> paper/numbers.tex (749 macros, letters-only names checked, generated from analysis/out). paper/main.tex DRAFT v0 (design, results RQ1-RQ4, robustness incl. audit and P8; related work, threats, conclusion are TODO; money per safe fix left out per Abdul's rule on cost in documents); scripts/check_paper_macros.py: all 57 number macros used resolve. Clean-clone reproducibility check (scripts/trials/2026-10-17_repro_check.sh) started but failed on an expired SSO token before comparing anything; to be re-run. No LaTeX toolchain on the laptop; PDF not built.

### 2026-10-17 11:10 PKT — P9 reproducibility check passed
- Who: Claude
- What: Clean clone of commit 912a975, all outputs rebuilt from S3 (chain table, P7 analysis W0/W1, regression, P8 agreement, 749 paper macros, 4 figures) and compared with the committed files: 13/13 byte-identical (exit 0). Two earlier attempts: one stopped by an expired SSO token, one by an S3 read timeout on the laptop (fixed: retries + parallel fetch in analysis/pilot_summary.py, output unchanged). The first complete run had found the regression JSON non-identical (D-039, fixed by seeding the fit). P9 exit criterion ("all paper numbers reproducible from analysis/") met; awaiting Abdul's confirmation.
- Refs: scripts/trials/2026-10-17_repro_check.result.log, D-039.

### 2026-10-17 12:14 PKT — P9 confirmed; literature search started
- Who: Abdul ("P9 done, start the literature search"), Claude
- What: P9 exit confirmed by Abdul. Literature search started under docs/lit-review/search-protocol.md (approved v1, D-031).

### 2026-10-17 12:30 PKT — Literature search: searches run, screening started (paused)
- Who: Claude
- What: scripts/lit/search.py: arXiv 103 hits, OpenAlex 523 hits (exact queries in docs/lit-review/search-log.md; two invalid arXiv runs from a regex escaping bug marked there). All six seed works found. scripts/lit/dedupe.py: 626 hits -> 516 unique records (docs/lit-review/records.csv). Protocol deviations logged in search-protocol.md (Scopus -> OpenAlex, wildcard expansion, arXiv split query, no OpenAlex language filter, IEEE/ACM pending). Title/abstract screening: R0001-R0110 of 516 done (docs/lit-review/ta_decisions.txt). Paused at usage limit; continue from R0111.

### 2026-10-17 14:43 PKT — Title/abstract screening complete
- Who: Claude
- What: All 516 records screened once (docs/lit-review/ta_decisions.txt -> screening.csv via scripts/lit/screening.py): 72 include + 65 unclear go to full text (137); 379 excluded (X1 off-topic 243, X6 not a paper 52, X3 no evaluation 34, X2 detection only 21, X4 application code 17, X5 non-English 12). Replication packages / artefact records of relevant papers (e.g. LLM Terraform repair submissions, PatchWeaver, CloudFix-Bench) excluded as records but flagged for snowballing. Blind 20% re-screening sample (103 records, seed 20261017, decisions hidden) written to docs/lit-review/rescreen-sample.csv for Abdul.

### 2026-10-17 15:02 PKT — Seed check with Abdul's Excel; search revised (v1.1, v1.2); all 720 records screened
- Who: Claude (Abdul allowed reading Literature_Matrix_Cloud_DevOps_AI.xlsx; asked for IEEE/ACM runs and that I do the re-screening)
- What: In-scope seed list (21 papers, themes A, C, B4, B5) saved as docs/lit-review/seed-excel.csv (titles only). v1 missed 4; per protocol the string was revised: v1.1 (+language/foundation model; +Ansible, CloudFormation, Pulumi, Puppet, Chef, Dockerfile, Docker Compose) and v1.2 (+self-healing). Records appended without renumbering (scripts/lit/add_records.py): 720 total. All seeds found except IaC-Eval (no abstract in OpenAlex, not on arXiv; to come via snowballing). Screening of R0517-R0720 done: overall 158 to full text (I 85, ? 73), 562 excluded. Re-screen sample regenerated: 144 records (20% of 720). Next: IEEE Xplore and ACM DL in the browser; blind second screening by an independent AI session (logged deviation: not a human); full-text reading of all 158.

### 2026-10-17 15:09 PKT — IEEE Xplore search; blind second screening; agreement
- Who: Claude
- What: IEEE Xplore (browser, v1.2 string): 232 hits -> 127 new records, all screened. Blind second screening of the 144-record sample by an independent AI session (rescreen-second-screener.txt): stage agreement 92.4%, kappa 0.78 (scripts/lit/agreement.py); 2 records moved to full text by the conservative rule. A screening.py run had redrawn the sample over 847 records; the original 144-record sample was restored from git (commit 222263a) and the script changed so samples are never redrawn. Second blind pass on a 25-record IEEE sample running. Totals now: 847 records, 180 to full text.

### 2026-10-17 15:31 PKT — Catch-up: steps done earlier today but not journaled at the time
- Who: Claude
- What: Three steps between 15:09 and now were committed (48eacf5, 72afff6, 531f657) but no journal entry was written when they happened. They were: (1) blind second screening of the 25-record IEEE sample: stage agreement 96.0%, kappa 0.86 before resolution; R0763 moved to full text under the conservative rule, so 181 records go to full text; (2) ACM Digital Library run stopped by a Cloudflare bot check in the automated browser; not bypassed; Abdul asked to do the check himself or accept OpenAlex coverage (logged in search-protocol.md); (3) full-text retrieval with scripts/lit/fetch_fulltext.py (arXiv, then OpenAlex open-access copies; PDFs git-ignored, manifest with sha256).
- Why: rule 9 asks for the entry in the same step; this entry closes the gap. Past entries untouched.
- Result: first retrieval pass finished: 75/181 full texts; 95 no open copy, 10 download failures, 1 not a PDF.
- Refs: 48eacf5, 72afff6, 531f657, docs/lit-review/fulltext-manifest.csv.

### 2026-10-17 15:31 PKT — Full-text screening and extraction in progress; second retrieval pass started
- Who: Claude (Abdul: "check all papers and read them thoroughly ... you do it")
- What: Read the retrieved full texts in record order (scripts/lit/snippets.py and new scripts/lit/kwic.py as reading aids; every judgement backed by a quoted passage). 66 records decided so far in docs/lit-review/fulltext-extraction.tsv (gap-table columns + evidence). Two duplicate versions handled per exclusion criterion 3 (keep the latest): R0097 (ChaosEater arXiv) gives way to R0170 (ASE 2025); R0295 gives way to R0470 (same authors, extended benchmark). Started scripts/lit/fetch_fulltext_pass2.py for the 106 records without a copy: arXiv title search and Semantic Scholar openAccessPdf, accepted only when the title matches (similarity >= 0.92).
- Finding worth noting for related work: KuTIE (R0331) scores patches by static inspection against cluster-derived ground truth, not by running them; CLAUDE.md describes it as "deploys K8s patches on one custom cluster". The paper's related-work text must use the paper's own wording.
- Result: in progress.
- Refs: docs/lit-review/fulltext-extraction.tsv, scripts/lit/kwic.py, scripts/lit/fetch_fulltext_pass2.py.

### 2026-10-17 15:42 PKT — Full-text retrieval pass 3; all retrieved full texts decided
- Who: Claude
- What: Pass 3 (scripts/lit/fetch_fulltext_pass3.py: Zenodo API, DOI landing-page citation_pdf_url, and four open URLs found by web search, listed in fulltext-manual-urls.csv) raised full texts from 75 to 86 of 181. Pass 2 was stopped after 18 records (Semantic Scholar rate limits made it very slow; no copy found yet, manifest untouched) and is restarted now on the 95 remaining. Protocol change log updated (retrieval passes, exclusion-code mapping, duplicate handling). New scripts: prisma.py (counts from the files), gap_table.py (generates gap-table.md). Web searches also produced one snowballing lead (NSYNC, arXiv 2510.20211) in snowball-candidates.csv.
- Result: 86/86 retrieved papers decided: 62 included, 24 excluded (IC2 13, IC1 6, E3 3, E1 2). R0248 treated as a duplicate of R0470 (same evaluation, tool-track paper); the full study is kept rather than the later tool paper (logged as such). Nine copies are open but blocked to scripts (HTTP 403: ACM and MDPI; R0001 SSL chain error); left for a browser attempt with Abdul's OK.
- Finding: NetPolAgent (R0772) is the closest work on runtime security intent: it applies generated NetworkPolicies to a kind cluster and tests allowed/denied connectivity with probe pods. It uses synthetic probe pods only (no application, no load) and generates policies from intents rather than repairing an application. No included study does deploy + app behaviour + runtime security intent together.
- Refs: docs/lit-review/fulltext-extraction.tsv, gap-table.md, fulltext-manifest.csv.

### 2026-10-17 19:46 PKT — ACM Digital Library search and browser-fetched full texts
- Who: Claude; Abdul (passed ACM's Cloudflare check and signed in himself; approved using his real Chrome via the Claude in Chrome extension: "you have full control and permission")
- What: The automated browser pane could not pass ACM's bot check (not bypassed). In Abdul's Chrome: ACM advanced search with the v1.2 string (Title OR Abstract per group, 2023-2026), cookie banner set to necessary only. 51 hits; DOIs saved (raw/acm-v1.2-20261017-dois.txt) and metadata/abstracts taken from OpenAlex (scripts/lit/acm_hits.py). 39 hits matched existing records, 12 new (R0848-R0859) screened: 2 to full text (InfraAPR, Poliac). Blind second screening of the 2-record ACM sample by an independent AI subagent: 2/2 agree. Open-access PDFs that refuse scripted downloads (18 ACM, 1 MDPI) were fetched inside his Chrome session into his Downloads folder and imported with scripts/lit/import_browser_pdfs.py (first-page title check, sha256). One wrong DOI typed by Claude for R0856 was caught by the title check and corrected. Not obtainable: R0001 (SciTePress, CAPTCHA, not attempted), R0182 (VU repository 403), R0287 (IEEE paywall), R0665 (MDPI; Chrome blocked a second download).
- Also: Abdul pasted his ACM password in the chat; Claude did not use it and advised changing it; it must be redacted before the session transcript is exported to docs/sessions/.
- Result: full texts 105/183; all 105 decided: 78 included, 27 excluded (IC2 14, IC1 7, E3 4, E1 2). R0530 (ASE 2024) kept over its earlier arXiv version R0544. Gap: no included study deploys + checks application behaviour + checks security intent at runtime. Closest new ones: InfraAPR (R0856) requires pulumi up to succeed but has no behaviour or security check; IacFix (R0367, AWS) proves the fix with SMT on templates, without deploying.
- Fixes: TSV readers now use QUOTE_NONE (evidence cells start with quotes); counts unchanged.
- Refs: raw/acm-v1.2-20261017*.{txt,jsonl}, fulltext-extraction.tsv, gap-table.md, search-protocol.md change log.

### 2026-10-17 20:58 PKT — Full-text stage: 126 of 183 read and decided; 57 not accessible
- Who: Claude (in Abdul's Chrome session, with his permission)
- What: Read the remaining open-access full texts in the browser: 3 IEEE Access (HTML text or in-memory PDF parse), 7 SSRN, 9 theses/repository items, IOS Press, AIS eLibrary, Zenodo. Chrome blocked further file downloads; a local 127.0.0.1 PDF receiver was proposed and refused by the auto-mode permission system (not retried or worked around). Instead PDFs were parsed in memory with pdf.js and not saved (scripts/lit/browser_reader.js). Unavailable records and reasons recorded (scripts/lit/mark_unavailable.py).
- Result: 126 decided: 92 included, 34 excluded (IC2 18, IC1 9, E3 4, E1 3); 57 not accessible (44 of them paywalled IEEE Xplore). Gap holds: no included study deploys + checks application behaviour + checks security intent at runtime. New close items: CloudBot (R0099, deploys on AWS and runs apps, no security check), R0132 thesis (LLM HPA/KEDA configs tested under Locust load, no security), IaCBench (R0383, "functional correctness" checked statically).
- Open: Abdul to say whether he has institutional IEEE Xplore access (44 papers); 3 open copies he can download by hand (R0015, R0406, R0665).
- Refs: fulltext-extraction.tsv, fulltext-manifest.csv, gap-table.md, search-protocol.md.

### 2026-10-18 00:44 PKT — Snowballing round (backward + forward) and new full texts
- Who: Claude
- What: One round of snowballing on the included studies (protocol step 3). OpenAlex references and citing works (scripts/lit/snowball.py; 549 references, 188 citing works; OpenAlex lists few references for arXiv papers) plus Semantic Scholar references and citations (scripts/lit/snowball_s2.py; 2,124 references, 427 citations). Candidates kept only if published 2023-01-01..2026-10-31 and matching the search string's three keyword groups. Four hand-found leads added (snowball-manual-leads.csv: IaC-Eval, NSync, TerraFault, the paper behind replication package R0618). 139 hits -> 6 new records (R0860-R0865); 133 were already records, which suggests the database searches were close to saturation. Screened: 3 to full text as I, 2 as ?, 1 excluded; blind second screening of the 1-record sample agrees. Semantic Scholar resolved no references for 26 seeds by DOI; seed lookup changed to DOI -> arXiv id -> checked title match and re-run for those seeds (running).
- Full texts: IaC-Eval (NeurIPS proceedings), NSync and the Ansible security-smells paper (arXiv) read; R0860 read from the SciTePress preview and excluded as the earlier version of R0188 (E3); TerraFault (R0862) not accessible. Notable: the Ansible security-smells paper (R0865) deploys generated roles in test environments and audits them with CIS-CAT Pro, a runtime security check (no application function test). IaC-Eval states that it deliberately avoids deployment.
- Result: 130/188 full texts decided, 95 included. Gap unchanged: no study combines deployment, application behaviour and runtime security intent. Request list for Abdul's professor regenerated (58 papers; scripts/lit/requests_list.py, requests_docx.py; python-docx added to the analysis group).
- Refs: raw/snowball-*.jsonl, records.csv R0860-R0865, fulltext-extraction.tsv, fulltext-requests.{csv,md,docx}.

### 2026-10-18 01:24 PKT — PRISMA figure, gap table, related-work draft, bibliography
- Who: Claude
- What: PRISMA 2020-style flow diagram generated from the data (scripts/lit/prisma_figure.py -> analysis/figures/prisma.{png,pdf}, counts in docs/lit-review/prisma-counts.json): 1,115 database records (arXiv 140, OpenAlex 694, IEEE 230, ACM 51), 256 duplicates, 6 from snowballing, 865 screened, 677 excluded, 188 sought, 58 not retrievable, 130 assessed, 35 excluded, 95 included. Gap table for the paper (22 closest studies, shortlist docs/lit-review/gap-shortlist.tsv; yes/partly/no cells generated from the extraction by scripts/lit/gap_table_tex.py -> paper/gap_table.tex). Related-work section drafted in paper/main.tex (five paragraphs: scanner-judged security repair, deceptive fixes, deploying what the model produced, runtime evidence and load, gap), with counts as generated macros (paper/lit_numbers.tex) and citations keyed by record id (paper/references.bib from scripts/lit/make_bib.py; seven documented metadata corrections in bib-overrides.json). check_paper_macros.py now also checks literature macros and citation keys: 65 macros, 22 keys, none missing. No LaTeX installed on this machine, so the PDF was not compiled. REPRODUCE.md: literature-review section added.
- Still running: Semantic Scholar snowballing re-run for 26 seeds (rate-limited).
- Refs: paper/main.tex, paper/gap_table.tex, paper/lit_numbers.tex, paper/references.bib, analysis/figures/prisma.*.

### 2026-10-18 01:55 PKT — Snowballing re-run finished; no further new records
- Who: Claude
- What: Semantic Scholar re-run for 26 seeds with DOI -> arXiv -> checked-title lookup: 13 resolved, 278 references and 13 citations examined, 21 kept, all already records (0 new). 13 seeds are not indexed by Semantic Scholar (listed in search-protocol.md); for them only OpenAlex was followed. Snowballing round closed: 6 new records in total.
- Refs: raw/snowball-s2-20261018-rerun.jsonl, search-protocol.md.

### 2026-10-18 06:43 PKT — Paper: threats to validity, conclusion, data availability; first compiled PDF
- Who: Claude (Abdul: "main.tex seems good please do the best for step 2 and 3")
- What: Wrote Threats to validity (construct, internal, external, conclusion validity, literature review), Conclusion and Data availability in paper/main.tex; all numbers are generated macros. Claims checked against the record (audit method: separate script on raw artifacts, wording corrected; pilot repeat disagreement: pilot report). Repository URL and archive DOI left as placeholders for Abdul. Installed MiKTeX 25.12 for the user via winget (installer hash verified by winget; package auto-install enabled in MiKTeX's own settings) and added scripts/build_paper.ps1. Gap table scaled to text width; microtype added. Build: 8 pages, citations and references resolve; one 3 pt overfull line remains in the introduction. Introduction motivation is still marked TODO for Abdul. LaTeX outputs git-ignored. REPRODUCE.md: paper build section.
- Refs: paper/main.tex, scripts/build_paper.ps1.

### 2026-10-23 19:19 PKT — 53 requested full texts read; full-text stage complete
- Who: Claude; Abdul supplied full_doc.zip (53 PDFs from his professor)
- What: ZIP checked (54 entries, no unsafe paths, all PDFs named by record id) and unpacked into a scratch folder with scripts/lit/unpack_requested.py; all 53 passed the first-page title check and were imported (manifest with sha256; PDFs not in git). All 53 read and recorded in fulltext-extraction.tsv with quoted evidence. Corrections: R0860 duplicate target changed from R0188 to R0447 (the extended CCIS version); R0756 excluded as the earlier version of R0229. Importer now accepts PDFs named R1234.pdf. Gap table shortlist extended to 28 (KubeRepair, SecDev 2024 IaC repair, Skaffold-based manifest generation, OperAID, KubeScribe, SafeFix-Agent); related work updated accordingly; threats paragraph corrected (5 not retrieved; second screening covered title/abstract only).
- Result: 183 of 188 full texts read, all decided: 134 included, 49 excluded (IC2 26, IC1 11, E3 6, E1 6); 5 not obtainable. Gap unchanged: no included study combines deployment, application behaviour and runtime security intent. Closest: SafeFix-Agent (R0462) applies Terraform fixes in a sandbox and smoke-tests basic health and posture, without functional/load tests or a security probe. Paper rebuilt (all macros and 28 citation keys resolve).
- Refs: fulltext-extraction.tsv, gap-shortlist.tsv, paper/main.tex, search-protocol.md.

### 2026-10-23 19:31 PKT — Full-text second screening; introduction draft; replication-package preparation
- Who: Claude (Abdul: "Please start all the items ... Whatever is best do it please")
- What: (1) Blind full-text second screening of a 20% sample (37 records) by an independent AI session: 89.2% agreement, kappa 0.75; R0033 (GenKubeSec, E1) and R0397 (KubeCap, IC1) changed to exclude on the evidence; R0248/R0295 duplicates kept as excluded. Included studies now 132; gap unchanged. (2) Introduction drafted (motivation, prior-work citations, contributions list), marked as a draft for Abdul to rewrite. (3) Replication package prepared, nothing published: README rewritten for the package, LICENSE (MIT, code) and LICENSE-DATA (CC BY 4.0) proposed, CITATION.cff, scripts/release/make_public_snapshot.py (git archive of HEAD into a new folder; AWS account id, IAM Identity Center start URL and personal email replaced by placeholders; session transcripts excluded; post-scan for credentials). Test snapshot of ebd8220: 359 files, 26 redacted, no problems. Secret scan of tracked files: no keys, tokens or passwords.
- Waiting for Abdul: OK to (a) publish the snapshot (new public GitHub repo, private repo untouched), (b) export the S3 run artifacts (needs his SSO login) and archive on Zenodo, (c) submit to arXiv.
- Refs: ft-rescreen-resolution.md, paper/main.tex, README.md, LICENSE*, CITATION.cff, scripts/release/.

### 2026-10-23 19:33 PKT — arXiv bundle script; session transcript exported with the password redacted
- Who: Claude
- What: scripts/release/make_arxiv_bundle.py (flat source folder + tar.gz: main.tex and generated inputs with comments removed, main.bbl, the four figures; graphicspath rewritten); test bundle compiled standalone with pdflatex (8 pages, no warnings). Session transcript exported (session-02) and redacted with scripts/release/redact_session_export.py: the secret strings were read from a temporary file (so they never appear in a command or the command log), 6 occurrences replaced, re-check 0; temporary file and the unredacted export in Downloads deleted. Stored as docs/sessions/2026-10-23_session-02_p7-to-lit-review.zip (sha256 74458d39...).
- Refs: scripts/release/, docs/sessions/README.md.

### 2026-10-23 19:34 PKT — Run-data export script (read-only); waiting for Abdul's SSO login and publishing OK
- Who: Claude
- What: scripts/release/export_run_data.py: --measure lists objects per prefix (read-only); --download copies the study prefixes into a new folder, replaces account-identifying values with the snapshot placeholders and withholds anything credential-like. Not run yet: the SSO token had expired (needs Abdul's device-code login). No AWS resource is created or changed by it.
- Open decisions for Abdul: publish the public snapshot (new GitHub repo), licences (MIT code / CC BY 4.0 data proposed), Zenodo archive, arXiv submission (account/endorsement, front matter).
