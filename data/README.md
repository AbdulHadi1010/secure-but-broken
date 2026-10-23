# Run artifacts

`run-artifacts.tar.gz` (17.4 MB, SHA-256 `ced851513681d6144407a809de02187e9c46688c1414e6349e1df82633d486d5`) holds every
artifact the study wrote to its run bucket, exported read-only on 2026-10-23 with `scripts/release/export_run_data.py`
(account-specific values replaced by the same placeholders as the rest of this snapshot; nothing withheld).

| Folder | Contents |
|---|---|
| `chains/<run_id>/` | one folder per repair chain (pilot, P7 full run): `summary.json`, and per iteration `iter-<n>/` the prompt messages, model response, repaired manifests, every gate result with its evidence (scanner output, dry run, pod events, functional checks, k6 summary, intent policies and runtime probes), the verdict, and C2 feedback with the moderator's input/output |
| `p8/` | the EKS replay of 88 sampled final repairs and its EKS baseline band |
| `baseline/` | the gold-application baseline runs that define the working band |
| `vm-results/` | baseline and case-validation results measured on the dedicated measurement VM |
| `batches/` | which chains ran in which batch on which worker |

The chain table used by the paper is rebuilt from `chains/*/summary.json` (`analysis/pilot_summary.py`; see
`docs/REPRODUCE.md`). Licence: CC BY 4.0 (`LICENSE-DATA`).
