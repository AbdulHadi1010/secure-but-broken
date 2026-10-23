# Experiment log

Oldest first, append-only. What was run, when, why, and where the artifacts are. The full audit trail is in `docs/journal.md`.

## 2026-10-03 — P0 scaffold
- Scaffolded repo layout (CLAUDE.md §9).
- Wrote Terraform: bootstrap (state bucket), S3 artifacts, DynamoDB attempts, ECR worker repo, IAM roles, Budgets ($100/month, 50/80/100% + forecast) and cost anomaly monitor. **Nothing applied.**
- Wrote Bedrock smoke test (`harness bedrock-smoke`) and unit tests. **Not yet run against AWS.**

## 2026-10-03 — Bedrock smoke test (SSO profile secure-but-broken)
- Working: Sonnet 4.6, GPT-OSS 120B, DeepSeek V3.2, Haiku 4.5 (moderator), Llama 3.3 70B, Mistral Large 3, Qwen3-coder-next, Sonnet 4.5.
- Blocked on this account: Sonnet 5/5.5, Opus 5.5/4.8, Fable 5.1, GPT-5.4/5.5/5.6/6, Grok 4.6, Kimi K3 (see D-008). Support case to be filed by the researcher.
- Note for P3: GPT-OSS 120B is a reasoning model; with maxTokens=64 it spent all tokens on reasoning and returned empty text. Use a large maxTokens and parse out reasoning blocks.
- SSO login works (assumed role AdministratorAccess). Static key of IAM user `claude-bedrocl` to be deactivated by the researcher.
- Terraform bootstrap plan: 5 to add, 0 to change, 0 to destroy. Not applied.

## 2026-10-03 — Bootstrap applied
- Applied bootstrap stack: state bucket sbb-tfstate-<AWS_ACCOUNT_ID> (5 resources). State migrated into the bucket (secure-but-broken/bootstrap.tfstate).
- Main stack plan: 16 to add, 0 change, 0 destroy. NOT applied; awaiting researcher OK after cost estimate.

## 2026-10-03 — Main stack applied
- 14 resources created (S3 artifacts, DynamoDB, ECR, IAM roles, Budget). Anomaly monitor dropped (D-009). Re-plan: no changes. See journal.

## 2026-10-03 — Baseline local-20261003 (P1)
- 5 clean runs of gold on fresh kind clusters; all ok, 0 restarts, L5 100%, error rate 0.
- p95 177.5 ± 24.5 ms -> L6 thresholds: p95 ≤ 251.2 ms, error rate ≤ 1.0%. Ready 37.6 s mean.
- Summary `app/baseline/local-20261003.json`; raw in `runs/baseline/local-20261003/`.
