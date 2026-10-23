# Trial scripts (tooling validation, never part of the counted data)

Each file is the exact script that was run, copied from the session scratch folder on 2026-10-04.
Run from the repo root with Docker running: `uv run python scripts/trials/<file>.py`.

| Script | Date | What it tested | Result | Refs |
|---|---|---|---|---|
| 2026-10-03_l5_sensitivity_all_services.py | 2026-10-03 | Trial 3: scale each of 10 backends to 0, run L5 | 8 of 10 results captured (output truncated by the console; see `.result.partial.txt`); ad/cart re-run below | D-014 |
| 2026-10-03_l5_sensitivity_ad_cart_rerun.py | 2026-10-03 | Trial 4: healthy, no adservice, no cartservice | ad check catches adservice; cart breaks all | D-014 |
| 2026-10-03_l5_sensitivity_email_check.py | 2026-10-03 | Trial 5: checkoutservice log check with emailservice down | caught (pass rate 0.91) | D-014 |
| 2026-10-04_p2_coupled_fields_and_netpol.py | 2026-10-04 | privileged + APE false rejected by API; kindnet NetworkPolicy enforcement | rejected; BLOCKED/OPEN as expected | D-016, D-017 |

Known gap (recorded honestly): trial 2 (recommendation/payment/ad only) used an earlier version of
`l5_sensitivity_all_services.py` that was edited in place to become trial 3, so the exact trial-2 script
was not preserved. Its output is in `2026-10-03_l5_sensitivity_trial2.result.txt`. From 2026-10-04 on,
every script is written into this folder before it is run.
