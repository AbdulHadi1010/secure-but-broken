# Secure but Broken?

Replication package for *Secure but Broken? Deployment-Validated Evaluation of LLM Security Repairs for Kubernetes*
(Abdul Hadi, 2026). Every LLM repair of a Kubernetes security misconfiguration is deployed on a fresh cluster and judged
by seven gates: targeted scanner rules, no new findings, server-side dry run, readiness, functional user journeys,
load test against a measured baseline band, and the security intent (static policies plus a runtime probe).

## What is here

| Path | Contents |
|---|---|
| `docs/protocol.md` | pre-registered protocol (frozen v1) |
| `docs/decisions.md`, `docs/journal.md`, `docs/experiment-log.md` | every design decision, deviation and action, in order |
| `app/gold/` | hardened Online Boutique manifests (images pinned by digest) |
| `cases/`, `injectors/`, `policies/intent/` | the 18 cases, their injectors, intent policies and runtime probes |
| `harness/` | the pipeline (Python): repair, moderator, deploy, checks, evaluator, orchestration |
| `worker/`, `infra/terraform/` | worker image and AWS infrastructure (Bedrock, S3, DynamoDB, VMs; EKS for the replay) |
| `analysis/` | scripts producing every number, table and figure in the paper; `analysis/out/` their outputs |
| `paper/` | LaTeX source; numbers and tables are generated (`scripts/build_paper.ps1`) |
| `docs/lit-review/` | systematic review: search strings, raw hits, records, screening, extraction, PRISMA, scripts in `scripts/lit/` |
| `docs/command-log/` | every shell command run during the study (automatic log) |
| `data/` (archive only) | per-attempt artifacts exported from the run bucket: manifests, prompts, responses, gate evidence |

`docs/REPRODUCE.md` lists the steps to rebuild everything from scratch, phase by phase.

## Quick start

```bash
uv sync
uv run pytest
uv run --group analysis python analysis/p7_analysis.py      # needs the chain table (see REPRODUCE.md)
powershell -ExecutionPolicy Bypass -File scripts/build_paper.ps1
```

Running new repairs needs an AWS account with Amazon Bedrock access; nothing in this repository creates AWS
resources by itself (see `infra/terraform/` and `docs/REPRODUCE.md`).

## Notes on the public snapshot

The public snapshot is produced by `scripts/release/make_public_snapshot.py`. Account-specific values are replaced
by placeholders (`<AWS_ACCOUNT_ID>`, `<SSO_START_URL>`, `<CONTACT_EMAIL>`); full session transcripts are not included.
Full-text PDFs of the reviewed papers are not redistributed; their SHA-256 hashes are in
`docs/lit-review/fulltext-manifest.csv`.

## Licence

Code: MIT (`LICENSE`). Data, documents and figures: CC BY 4.0 (`LICENSE-DATA`). Third-party material keeps its own
licence (Online Boutique: Apache 2.0).

## Citation

See `CITATION.cff`.
