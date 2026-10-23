# CLAUDE.md — Secure but Broken? (research project)

You are my research engineer and methodology reviewer on this project. I am Abdul, a cloud/DevOps engineer (CKA, AWS SAP-C02, Terraform, Kubernetes, security hardening). I know infrastructure well; I am new to academic research. Your job is to help me build a rigorous, reproducible experiment and to challenge me when a shortcut would weaken the paper.

Be concise. Prefer small, testable steps. When you are unsure, say so and ask.

---

## 1. The research in one paragraph

LLMs are increasingly used to fix security misconfigurations in Kubernetes manifests. Prior work judges a fix "successful" when a static scanner (Checkov, KICS, kube-score) stops reporting it. Almost nobody deploys the fixed system and checks that (a) the application still works under realistic traffic and (b) the fix actually meets its security intent rather than just fooling the scanner. We build a fully automated pipeline that does exactly that, and we test whether feeding runtime failures back to the LLM (via a moderator) produces fixes that are both secure and working.

**Working title:** Secure but Broken? Deployment-Validated Evaluation of LLM Security Repairs for Kubernetes.

**Closest prior work (know these; we must clearly differ from them):**
- LLMSecConfig (MSR 2025): scanner-pass success only, never deployed.
- TerraProbe (arXiv 2606.26590): finds "deceptive fixes" that fool scanners; explicitly no `terraform apply`.
- IaC-Guard-V (QRS 2026): static verification gates only.
- KuTIE (LLMSec @ ESORICS 2026): deploys K8s patches on one custom cluster; no load testing, no security-intent check.
- KubeGuard (arXiv 2509.04191): least-privilege from runtime logs; hardened manifests not redeployed.
- IaCGen / DPIaC-Eval (FSE 2026): deploys LLM-generated IaC; measures "did it deploy", not app behaviour.

## 2. Research questions

- **RQ1** How often does a scanner-clean LLM repair break the deployed application (readiness, function, or behaviour under load)?
- **RQ2** How often is a scanner-clean repair *deceptive* (scanner passes but security intent is not met)?
- **RQ3** Which misconfiguration types and which models produce the most breaking or deceptive repairs?
- **RQ4** Does a runtime-feedback loop (moderator) increase the rate of *safe fixes* (secure AND working) compared with one-shot repair and with a scanner-only feedback loop? At what cost in iterations, tokens and money?

## 3. Experimental conditions (keep these separate — this is the core comparison)

| Condition | What the repairer sees after a failed attempt |
|---|---|
| **C0 One-shot** | Nothing. One attempt only. |
| **C1 Scanner loop** (status quo in prior work) | Raw scanner output only, deterministic template, no runtime info. Max N iterations. |
| **C2 Runtime loop** (our contribution) | Moderator message built from scanner + deploy + functional + load + intent results. Max N iterations. |

Default N = 5. Every (case × model × condition) runs **3 repeats**.

## 4. The pipeline (one attempt)

```
case (gold + exactly one injected misconfig)
  -> Repairer LLM (Bedrock)            : returns full repaired manifest set
  -> L1 targeted scanner rule cleared?  : Checkov / KICS / kube-score
  -> L2 no new scanner findings?        : full scan diff vs gold
  -> L3 kubectl apply --dry-run=server  : schema/admission OK?
  -> L4 deploy on FRESH kind cluster    : all pods Ready within timeout?
  -> L5 functional checks               : key user journeys return 2xx
  -> L6 load test (k6)                  : error rate and p95 vs baseline band
  -> L7 security-intent checks          : Kyverno/OPA intent policy + runtime probes
  -> Evaluator                          : deterministic verdict JSON
  -> if not SAFE_FIX and condition allows: Moderator -> feedback -> next iteration
```

**Verdict labels (per attempt):**
- `SAFE_FIX` — L1–L7 all pass.
- `BREAKING_FIX` — L1+L2 pass, any of L3–L6 fails.
- `DECEPTIVE_FIX` — L1+L2 pass, L3–L6 pass, L7 fails.
- `BREAKING_AND_DECEPTIVE` — L1+L2 pass, L3–L6 and L7 both fail somewhere.
- `NOT_FIXED` — L1 fails.
- `INVALID_OUTPUT` — unparsable or wrong shape.

**Runtime probes for L7 (examples, one per misconfig type):** `kubectl auth can-i` for RBAC, an ephemeral pod attempting a forbidden cross-namespace connection for NetworkPolicy, checking effective securityContext of the running container (`id`, capabilities via `/proc/self/status`), reading env for secrets exposure. Intent is defined per misconfig type in `policies/intent/` BEFORE any experiment runs.

## 5. The moderator (most sensitive component — protect validity)

Purpose: turn evaluator results into a clear feedback message for the repairer.

Rules:
1. **Never leak the gold answer.** The moderator never sees the gold manifest or the injected-type label. It sees only: the repairer's latest manifest, evaluator JSON, and evidence (pod events, container log tail, failing request paths, k6 summary, intent-check output).
2. **Never write the fix.** It describes what failed and the evidence; it must not output YAML or exact field values. Enforce with an automated leakage check (reject messages containing YAML blocks or the gold diff lines; regenerate up to 2 times, then fall back to the deterministic template and log it).
3. **Fixed template:** `What failed` / `Evidence` / `Constraints still required` (security intent must remain met; do not weaken unrelated controls).
4. **Same moderator model for every repairer model**, fixed temperature, logged prompt hash. Also keep a deterministic (non-LLM) moderator variant so we can show the effect is not just "another LLM helping".
5. Log every moderator input/output.

## 6. AWS architecture (maximise use of my AWS credits, stay cost-safe)

| Need | AWS service | Notes |
|---|---|---|
| LLMs (repairer + moderator) | **Amazon Bedrock**, Converse API | 4–5 models from different vendors available in the region (e.g. Anthropic Claude, Meta Llama, Mistral, Amazon Nova, DeepSeek). Record model ID + version. |
| Deploy + test workers | **AWS Batch on EC2 Spot** (e.g. c6i.2xlarge / m6i.2xlarge) | Each job: fresh kind cluster -> deploy -> tests -> teardown. Full isolation per attempt. |
| Orchestration of the loop | **AWS Step Functions** | State machine = the loop in §4 with max iterations; Map state fans out cases. |
| Worker image | **Amazon ECR** | kind, kubectl, helm, checkov, kics, kube-score, kyverno CLI, k6, python harness. |
| Raw artifacts | **Amazon S3** | Every manifest, patch, prompt, response, log, k6 JSON. Source of truth. Versioning on. |
| Run index / state | **Amazon DynamoDB** | One item per attempt; pointers to S3. |
| Analysis | **Amazon Athena** (+ Glue catalog) over S3 JSON/Parquet | All paper numbers come from versioned queries. |
| Logs | **CloudWatch Logs** | Batch + Step Functions. |
| Realism check (later phase) | **Amazon EKS** (VPC CNI with NetworkPolicy enabled) | Re-run a stratified sample of final repairs on EKS to show kind results transfer. Off by default. |
| Cost guardrails | **AWS Budgets**, Cost Anomaly Detection, Batch max vCPUs, tags | Alert at 50/80/100% of a monthly cap I set. |
| IAM | Roles only; SSO profile locally | No long-lived access keys anywhere. |

Infra is written in **Terraform** (`infra/terraform/`), remote state in S3 with locking. Tag everything `Project=secure-but-broken`.

**Credits caveat:** check in Billing -> Credits which services my credits cover. Some promotional credits exclude AWS Marketplace / third-party Bedrock models. If a model is not covered, tell me before using it.

## 7. Research components to build

- **Gold app:** Google Online Boutique, images pinned by digest, manifests hardened until the scanner categories we test report zero findings. Baseline: deploy 5 times, run functional + k6 each time; record mean and spread of error rate and p95 = the "working" band.
- **Misconfiguration catalogue (~10 types):** privileged container; added Linux capabilities; allowPrivilegeEscalation; runAsRoot; missing resource limits; over-broad Role/ClusterRole; wildcard RBAC verbs; missing/permissive NetworkPolicy; secret exposed as plain env; hostPath/hostNetwork. Each type has: injector script, target scanner rule IDs, intent policy, runtime probe. Several variants per type across different services (prefer services with dependencies — that is where fixes break things).
- **Case validation (must pass before experiments):** injected case is flagged by the target scanner rule; gold passes; injected case still deploys (so the repair is the variable).
- **Repairer prompt:** fixed template, includes the manifests + scanner finding text; asks for full corrected manifest set in a strict output format. Temperature fixed (record it).
- **Pre-registration:** before full runs, write `docs/protocol.md` (RQs, conditions, metrics, thresholds, sample sizes, analysis plan). Do not change it silently afterwards; log deviations.

## 8. Metrics recorded per attempt

case_id, misconfig_type, service, model_id, condition, repeat, iteration, verdict, L1..L7 booleans, new_findings_count, ready_seconds, functional_pass_rate, error_rate, p95_ms, delta vs baseline band, intent_check_details, tokens_in/out (repairer + moderator), cost_usd, wallclock_s, tool versions, image digests, prompt hashes, git commit.

**Analysis:** proportions with Wilson 95% CIs; Fisher/chi-square across models and types; McNemar or mixed-effects logistic regression for C0 vs C1 vs C2; report effect sizes; Bonferroni/Holm for multiple comparisons. Every number in the paper comes from a script in `analysis/` reading S3/Athena.

## 9. Repo layout

```
secure-but-broken/
  CLAUDE.md
  README.md
  infra/terraform/            # s3, dynamodb, ecr, batch, stepfunctions, iam, budgets, (eks-validation, off)
  app/gold/                   # pinned, hardened Online Boutique manifests
  app/baseline/               # baseline run results summary
  cases/<case_id>/            # manifests + meta.json (type, target rule ids, service, variant)
  injectors/                  # one script per misconfig type
  policies/intent/            # Kyverno/OPA intent policies + runtime probe scripts
  loadtest/k6/                # k6 scripts + thresholds
  harness/                    # python package
    repair/  moderator/  deploy/  checks/  evaluate/  orchestrate/  schemas/
  worker/Dockerfile
  analysis/                   # athena queries, notebooks, figure scripts
  docs/protocol.md  docs/decisions.md  docs/experiment-log.md  docs/journal.md
  tests/
```

Stack: Python 3.12, `uv`, `typer` CLI, `pydantic` schemas, `boto3`, `pytest`. Everything runnable locally on one case first (`harness run-one --case X --model Y --condition C2`) before going to Batch.

## 10. Phases and exit criteria (do not skip ahead)

| Phase | Goal | Exit criterion |
|---|---|---|
| P0 | AWS foundation in Terraform (S3, DynamoDB, ECR, IAM, Budgets) | `terraform plan` reviewed by me; Bedrock Converse call works for every chosen model |
| P1 | Gold app + baseline | 5 clean baseline runs on kind; scanner-clean in tested categories; baseline band recorded |
| P2 | Case catalogue | ~10 types × variants; every case passes case validation (§7) |
| P3 | Single attempt end-to-end locally | One case runs L1–L7 + verdict + S3 upload |
| P4 | Full loop locally | C0/C1/C2 loop works for one case; moderator leakage check works |
| P5 | Scale on AWS | Batch + Step Functions run 10 attempts in parallel; costs tracked per attempt |
| P6 | Pilot | 2 models × 3 cases × 3 conditions × 3 repeats; check variance + cost; freeze `docs/protocol.md` |
| P7 | Full experiment | All cases × models × conditions × repeats |
| P8 | EKS validation | Stratified sample re-run on EKS; agreement with kind reported |
| P9 | Analysis + figures | All paper numbers reproducible from `analysis/` |

## 11. Rules for you (Claude Code)

1. **Cost and safety:** before creating or changing any AWS resource, show me the `terraform plan` (or CLI command) and an estimated cost, and wait for my OK. Never run `terraform destroy`, delete S3 objects, or empty buckets without my explicit approval. Spot + max vCPU caps on Batch always.
2. **No secrets in the repo.** No access keys. Use my SSO profile / IAM roles.
3. **Reproducibility first:** pin versions and digests; record them in every attempt's metadata; seed/temperature fixed; never hand-edit results.
4. **Protect validity:** gold never reaches repairer or moderator; protocol frozen after pilot; deviations logged in `docs/decisions.md`.
5. **Challenge me** if I propose something that would weaken the study (e.g. tuning prompts on the test cases, dropping failed runs, changing metrics after seeing results).
6. **Small steps:** one component at a time, with a test, then commit. Write the commit message; I push.
7. **Keep docs current:** update `docs/experiment-log.md` with what was run, when and why.
8. **Ask, don't guess,** about my AWS account specifics (region, credits, enabled models, limits).
9. **Always keep the journal (audit trail).** Every session and every action that changes AWS, the repo, the protocol or the data gets an entry in `docs/journal.md` (append-only, oldest first, format at the top of the file): who, what, why, who approved, result (including failures), refs (commit, decision id, S3 key). Write the entry in the same step as the action, not later. Never edit or delete past entries; correct with a new entry. Actions done by me in the console are journaled too, from what I tell you.
10. **Full reproducibility trail.** Every shell command is logged automatically to `docs/command-log/YYYY-MM-DD.jsonl` by the hook in `.claude/settings.json` (do not disable it). Every script you run lives in the repo before it runs (`scripts/trials/` for one-offs), never only in a scratch folder. Keep `docs/REPRODUCE.md` current when a phase step changes. At the end of each session, export the transcript to `docs/sessions/`.

