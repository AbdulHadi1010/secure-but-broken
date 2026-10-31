# Reproducing Secure but Broken? from scratch

Every step that produced data, in order. Commands are for Windows PowerShell 5.1 from the repo root
unless marked otherwise. Exact versions and digests are pinned in code; the ones below are what was used.
Audit trail: `docs/journal.md` (narrative), `docs/command-log/*.jsonl` (every shell command from
2026-10-04 on, written automatically by a Claude Code hook), `docs/decisions.md` (D-numbers).

## 0. Machine and tools

| Tool | Version used | How installed |
|---|---|---|
| Windows 11 Pro, WSL2 | 10.0.26300 | — |
| Docker Desktop | 4.63.0 (engine 29.2.1), 12 CPU / ~15 GB to Docker | docker.com |
| kind | v0.33.0 | `winget install --id Kubernetes.kind --version 0.33.0 --exact` |
| kubectl | v1.37.1 | `winget install --id Kubernetes.kubectl --exact` (harness prefers it over Docker Desktop's bundled 1.34) |
| Terraform | v1.14.8 | hashicorp.com |
| AWS CLI | v2 | aws.amazon.com/cli |
| uv | 0.11.7 | astral.sh/uv |
| git | any | git-scm.com |

Laptop used: Intel i5-1345U, 12 logical CPUs, 31 GB RAM. Baseline numbers are only comparable on the same machine type (protocol.md).

```powershell
uv sync
uv run pytest
```

## 1. AWS account (P0)

Manual, in the console (account <AWS_ACCOUNT_ID>, us-east-1):
1. IAM Identity Center → Enable with AWS Organizations → **Single-Region instance** (us-east-1).
2. Create a user; permission set `AdministratorAccess`; assign to the account.
3. CLI profile:
   ```powershell
   aws configure sso --profile secure-but-broken
   ```
   start URL `<SSO_START_URL>`, SSO region `us-east-1`, output `json`.
4. Each session: `aws sso login --profile secure-but-broken`.

Terraform (show the plan, review, then apply):
```powershell
$env:AWS_PROFILE='secure-but-broken'
cd infra\terraform\bootstrap; terraform init; terraform plan -out=tfplan; terraform apply tfplan
terraform init -migrate-state -force-copy      # after the backend block was added (D-003)
cd ..; terraform init "-backend-config=backend.hcl"; terraform plan "-out=main.tfplan"; terraform apply main.tfplan
```
Creates: state bucket, artifacts bucket, DynamoDB `sbb-attempts`, ECR `sbb-worker`, IAM roles, budget. (Anomaly monitor not managed, D-009.)

Bedrock check (model list in `harness/config/models.json`, D-008):
```powershell
uv run harness bedrock-smoke
```

## 1b. Measurement VM (all verdict-relevant measurements run here, D-023)

The laptop is only used to write code and drive the VM. Baseline, case validation, known-answer tests and every
repair attempt run on a dedicated EC2 c6i.2xlarge (fixed-performance CPUs), created by `infra/terraform/worker-vm.tf`
(first-boot setup: `infra/terraform/worker-vm-userdata.sh`; Ubuntu 24.04, Docker 29.1.3, kind 0.33.0, kubectl 1.37.1,
uv 0.11.7). No SSH, no inbound ports: everything goes through SSM.

```powershell
$env:AWS_PROFILE='secure-but-broken'
uv run harness vm start
uv run harness vm sync                                   # ships the committed HEAD as a git bundle via S3, exact checkout
uv run harness vm run "uv run harness baseline --runs 10 --label vm-c6i2xl-20261004" --timeout 7200
uv run harness vm stop
```
Each remote command's full output is stored under `s3://sbb-artifacts-<AWS_ACCOUNT_ID>/ssm/<command-id>/`.
The L6 band used for verdicts is the baseline named in `app/baseline/ACTIVE`.

## 2. Gold app (P1)

```powershell
uv run harness gold-build        # app/gold/upstream (v0.10.7, sha256-checked) + images.lock.json + harden() -> app/gold/manifests.yaml
```
Upstream inputs are committed: `app/gold/upstream/kubernetes-manifests.v0.10.7.yaml` and `app/gold/upstream/network-policies/` (fetched from the v0.10.7 tag of GoogleCloudPlatform/microservices-demo). Hardening rules: D-011, D-013. Accepted scanner findings: `app/gold/accepted-findings.md`.

Scanner images (pinned by digest in `harness/checks/scanners.py`): Checkov 3.3.22, KICS 2.1.20, kube-score 1.20.0.

## 3. Local cluster and image caches

Each run creates a fresh kind cluster (`infra/kind/cluster.yaml`, node `kindest/node:v1.37.0@sha256:a1ed56cf…`) wired to two local pull-through caches (`registry:2.8.3`, containers `sbb-cache-dockerio` and `sbb-cache-gar`). `harness/deploy/kind.py` creates both automatically. The first run fills the caches (slow); later clusters are ready in ~30–40 s.

## 4. L5 instrument validation (trials, not counted)

```powershell
uv run python scripts/trials/2026-10-03_l5_sensitivity_all_services.py
uv run python scripts/trials/2026-10-03_l5_sensitivity_ad_cart_rerun.py
uv run python scripts/trials/2026-10-03_l5_sensitivity_email_check.py
```
Expected: L5 fails for each backend scaled to 0 (table: `app/baseline/l5-sensitivity.md`, D-014).

## 5. Baseline (P1, counted)

```powershell
uv run harness baseline --runs 5 --label local-20261003
uv run harness upload runs/baseline/local-20261003 baseline/local-20261003
```
Run from a clean commit (the runner records `git_commit`; `-dirty` marks uncommitted changes). Result used in the paper: `app/baseline/local-20261003.json` (commit e63f9ac). Band rule fixed before data: protocol.md, D-013.

## 6. Case catalogue (P2)

```powershell
uv run python scripts/trials/2026-10-04_p2_coupled_fields_and_netpol.py      # D-016, D-017
uv run python scripts/trials/2026-10-04_p2_netpol_injection_options.py       # D-019
uv run python scripts/trials/2026-10-04_l7_proc_probe_privileged.py          # D-018
# for each type and service listed in docs/protocol.md "Case variants":
uv run harness case-build privileged frontend
uv run harness case-validate privileged-frontend
```
Injectors: `harness/src/harness/injectors/__init__.py`. Intent (L7): `policies/intent/README.md`, Kyverno library
policies in `policies/intent/upstream/` (kyverno/policies@ec478cb5, Kyverno CLI v1.19.1). Each case folder holds
`manifests.yaml` (shown to the repairer), `meta.json` (analysis only) and `validation.json` (V1–V4 evidence).
Batch logs: `cases/_validation-*.log`.

## 6b. Pipeline checks (P3, no LLM)

```powershell
uv run python scripts/trials/2026-10-04_p3_known_answer_tests.py
```
Six hand-made repairs with known verdicts (SAFE, NOT_FIXED, DECEPTIVE, BREAKING at L3, L4 and L6). Run alone:
L6 measures latency, so no other cluster may run at the same time.

## 6c. Repair chains (P3/P4, uses Bedrock)

```powershell
aws sso login --profile secure-but-broken
uv run harness run-one --case privileged-frontend --model deepseek-v3-2 --condition C0
uv run harness run-one --case privileged-frontend --model deepseek-v3-2 --condition C2-LLM
```
Conditions: C0, C1, C2-LLM, C2-template (stop rules in protocol.md). Records: `runs/chains/<run_id>/` and
`s3://sbb-artifacts-<AWS_ACCOUNT_ID>/chains/<run_id>/`; one DynamoDB item per iteration in `sbb-attempts`.

## 7. References

`docs/references/README.md`: Pod Security Standards (kubernetes/website commit 77db41e9…) and NSA/CISA Kubernetes Hardening Guidance v1.2, with SHA-256 hashes.

## P7 analysis (2026-10-16)
1. Chain table from S3: `cd harness; uv run python ../analysis/pilot_summary.py p7-20261014-W0-std p7-20261014-W0-netpol p7-20261014-W1-std p7-20261014-W1-netpol`
2. Pre-registered tests (protocol FROZEN v1, D-035/D-036): `uv run python ../analysis/p7_analysis.py` -> analysis/out/p7-results-W0.md (primary), -W1.md, -wording.md
3. Sensitivity regression (D-037): `uv run --group analysis python analysis/p7_regression.py` -> analysis/out/p7-regression.md
4. Figures: `uv run --group analysis python analysis/figures.py` -> analysis/figures/fig1..fig4 (.png 300 dpi, .pdf)
5. Verdict audit (30 chains, seed 20261016): `cd harness; uv run python ../scripts/trials/2026-10-16_verdict_audit.py`

## Literature review (2026-10-17/18)
Protocol and every deviation: `docs/lit-review/search-protocol.md` (change log at the end). Raw hits are committed in
`docs/lit-review/raw/`; full-text PDFs are git-ignored (`docs/lit-review/fulltext/`), their sha256 is in
`fulltext-manifest.csv`. Steps (from the repo root, `uv run --group analysis python ...` where PDFs are parsed):
1. Searches: `scripts/lit/search.py arxiv|openalex` (`SEARCH_VERSION` v1, v1.1, v1.2); IEEE Xplore and ACM DL were run in
   a browser (exact strings in `search-log.md` / `search-protocol.md`); ACM DOIs -> `scripts/lit/acm_hits.py`.
2. Records: `scripts/lit/dedupe.py` (v1), then `scripts/lit/add_records.py <label> <hits.jsonl>...` for each later run.
3. Title/abstract screening: decisions in `ta_decisions.txt`; `scripts/lit/screening.py` builds `screening.csv` and
   draws each re-screen sample once; agreement: `scripts/lit/agreement.py`.
4. Full texts: `fetch_fulltext.py`, `fetch_fulltext_pass2.py`, `fetch_fulltext_pass3.py` (manual open URLs in
   `fulltext-manual-urls.csv`), `import_browser_pdfs.py` for PDFs fetched in a browser; copies read in the browser
   without saving are marked in the manifest; `mark_unavailable.py` records why the rest are missing; request list:
   `requests_list.py`, `requests_docx.py`.
5. Extraction (one row per record, quoted evidence): `fulltext-extraction.tsv`; reading aids `snippets.py`, `kwic.py`,
   `browser_reader.js`.
6. Snowballing: `snowball.py` (OpenAlex), `snowball_s2.py` (Semantic Scholar; `snowball_s2.py <ids>` to re-run seeds),
   `snowball_manual.py` (leads in `snowball-manual-leads.csv`), then step 2 with label `snowball`.
7. Outputs: `prisma.py` (counts), `prisma_figure.py` -> `analysis/figures/prisma.{png,pdf}` + `prisma-counts.json`,
   `gap_table.py` -> `gap-table.md`, `gap_table_tex.py` -> `paper/gap_table.tex` (shortlist `gap-shortlist.tsv`),
   `lit_numbers.py` -> `paper/lit_numbers.tex`, `make_bib.py` -> `paper/references.bib` (corrections in
   `bib-overrides.json`), then `scripts/check_paper_macros.py`.

## Paper build
MiKTeX (user install: `winget install --id MiKTeX.MiKTeX --scope user`, package auto-install on), then from the repo
root `powershell -ExecutionPolicy Bypass -File scripts/build_paper.ps1`: regenerates gap_table.tex, lit_numbers.tex and
references.bib, runs scripts/check_paper_macros.py, then pdflatex -> bibtex -> pdflatex x2 (paper/main.pdf, git-ignored).
paper/numbers.tex comes from analysis/paper_numbers.py (P7/P8 section above).
