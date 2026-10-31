# Full-text second screening: result and resolution (2026-10-23)

Sample: 37 of 183 decided records (20%, seed 20261023, drawn once by scripts/lit/ft_rescreen_sample.py from the 161
records whose text is on disk). Second screener: independent AI session given only the criteria, titles and full texts
(no first decisions). Decisions: ft-rescreen-second.txt.

Agreement before resolution (include/exclude): 33/37 = 89.2%, Cohen's kappa 0.75.

| Record | First | Second | Resolution |
|---|---|---|---|
| R0248 | exclude E3 (duplicate of R0470) | include | first kept: the second screener was told not to judge duplicate versions |
| R0295 | exclude E3 (duplicate of R0470) | include | first kept, same reason |
| R0033 | include | exclude E1 | **second adopted**: GenKubeSec outputs remediation steps as text only |
| R0397 | include | exclude IC1 | **second adopted**: KubeCap's patched manifests come from static analysis, not the LLM |

Excluding the two duplicate cases, which the second screener could not judge by design, agreement is 33/35 (94.3%).
