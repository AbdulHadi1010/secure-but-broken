# P7 results — W0 (primary)

Chains: 720. Proportions: k/n = % [Wilson 95% CI].

## Overall

- SAFE_FIX: 680/720 = 94.4% [92.5, 95.9]
- Scanner-clean: 714/720 = 99.2% [98.2, 99.6]
- RQ1 breaking among scanner-clean: 29/714 = 4.1% [2.8, 5.8]
- RQ2 deceptive among scanner-clean: 8/714 = 1.1% [0.6, 2.2]

## C0: what a scanner-only evaluation would call success

- Scanner-clean: 178/180 = 98.9% [96.0, 99.7]
- of which actually SAFE: 164/178 = 92.1% [87.2, 95.3]
- of which breaking: 12/178 = 6.7% [3.9, 11.4]
- of which deceptive: 2/178 = 1.1% [0.3, 4.0]

## By model

| | SAFE_FIX | breaking among clean | deceptive among clean |
|---|---|---|---|
| deepseek-v3-2 | 210/240 = 87.5% [82.7, 91.1] | 27/237 = 11.4% [7.9, 16.1] | 3/237 = 1.3% [0.4, 3.7] |
| glm-5 | 233/240 = 97.1% [94.1, 98.6] | 2/240 = 0.8% [0.2, 3.0] | 5/240 = 2.1% [0.9, 4.8] |
| kimi-k3 | 237/240 = 98.8% [96.4, 99.6] | 0/237 = 0.0% [0.0, 1.6] | 0/237 = 0.0% [0.0, 1.6] |

## By condition

| | SAFE_FIX | breaking among clean | deceptive among clean |
|---|---|---|---|
| C0 | 164/180 = 91.1% [86.0, 94.5] | 12/178 = 6.7% [3.9, 11.4] | 2/178 = 1.1% [0.3, 4.0] |
| C1 | 167/180 = 92.8% [88.0, 95.7] | 10/180 = 5.6% [3.0, 9.9] | 3/180 = 1.7% [0.6, 4.8] |
| C2-LLM | 173/180 = 96.1% [92.2, 98.1] | 4/177 = 2.3% [0.9, 5.7] | 0/177 = 0.0% [0.0, 2.1] |
| C2-template | 176/180 = 97.8% [94.4, 99.1] | 3/179 = 1.7% [0.6, 4.8] | 3/179 = 1.7% [0.6, 4.8] |

## By type

| | SAFE_FIX | breaking among clean | deceptive among clean |
|---|---|---|---|
| added-capabilities | 108/108 = 100.0% [96.6, 100.0] | 0/108 = 0.0% [0.0, 3.4] | 0/108 = 0.0% [0.0, 3.4] |
| allow-privilege-escalation | 107/108 = 99.1% [94.9, 99.8] | 0/107 = 0.0% [0.0, 3.5] | 0/107 = 0.0% [0.0, 3.5] |
| missing-limits | 107/108 = 99.1% [94.9, 99.8] | 0/107 = 0.0% [0.0, 3.5] | 0/107 = 0.0% [0.0, 3.5] |
| netpol | 143/180 = 79.4% [73.0, 84.7] | 29/177 = 16.4% [11.7, 22.5] | 8/177 = 4.5% [2.3, 8.7] |
| privileged | 107/108 = 99.1% [94.9, 99.8] | 0/107 = 0.0% [0.0, 3.5] | 0/107 = 0.0% [0.0, 3.5] |
| run-as-root | 108/108 = 100.0% [96.6, 100.0] | 0/108 = 0.0% [0.0, 3.4] | 0/108 = 0.0% [0.0, 3.4] |

## By model x condition

| | SAFE_FIX | breaking among clean | deceptive among clean |
|---|---|---|---|
| deepseek-v3-2 · C0 | 50/60 = 83.3% [72.0, 90.7] | 10/60 = 16.7% [9.3, 28.0] | 0/60 = 0.0% [0.0, 6.0] |
| deepseek-v3-2 · C1 | 50/60 = 83.3% [72.0, 90.7] | 10/60 = 16.7% [9.3, 28.0] | 0/60 = 0.0% [0.0, 6.0] |
| deepseek-v3-2 · C2-LLM | 53/60 = 88.3% [77.8, 94.2] | 4/57 = 7.0% [2.8, 16.7] | 0/57 = 0.0% [0.0, 6.3] |
| deepseek-v3-2 · C2-template | 57/60 = 95.0% [86.3, 98.3] | 3/60 = 5.0% [1.7, 13.7] | 3/60 = 5.0% [1.7, 13.7] |
| glm-5 · C0 | 56/60 = 93.3% [84.1, 97.4] | 2/60 = 3.3% [0.9, 11.4] | 2/60 = 3.3% [0.9, 11.4] |
| glm-5 · C1 | 57/60 = 95.0% [86.3, 98.3] | 0/60 = 0.0% [0.0, 6.0] | 3/60 = 5.0% [1.7, 13.7] |
| glm-5 · C2-LLM | 60/60 = 100.0% [94.0, 100.0] | 0/60 = 0.0% [0.0, 6.0] | 0/60 = 0.0% [0.0, 6.0] |
| glm-5 · C2-template | 60/60 = 100.0% [94.0, 100.0] | 0/60 = 0.0% [0.0, 6.0] | 0/60 = 0.0% [0.0, 6.0] |
| kimi-k3 · C0 | 58/60 = 96.7% [88.6, 99.1] | 0/58 = 0.0% [0.0, 6.2] | 0/58 = 0.0% [0.0, 6.2] |
| kimi-k3 · C1 | 60/60 = 100.0% [94.0, 100.0] | 0/60 = 0.0% [0.0, 6.0] | 0/60 = 0.0% [0.0, 6.0] |
| kimi-k3 · C2-LLM | 60/60 = 100.0% [94.0, 100.0] | 0/60 = 0.0% [0.0, 6.0] | 0/60 = 0.0% [0.0, 6.0] |
| kimi-k3 · C2-template | 59/60 = 98.3% [91.1, 99.7] | 0/59 = 0.0% [0.0, 6.1] | 0/59 = 0.0% [0.0, 6.1] |

## RQ3 tests

| test | method | p |
|---|---|---|
| breaking_by_type | exact (Monte Carlo, seed 20261016) | 1e-05 |
| deceptive_by_type | exact (Monte Carlo, seed 20261016) | 0.00027 |
| safe_by_type | chi-square | 1.157e-20 |
| breaking_by_model | chi-square | 2.137e-11 |
| deceptive_by_model | exact (Monte Carlo, seed 20261016) | 0.1068 |
| safe_by_model | chi-square | 4.754e-08 |

H-FC (one-sided Fisher, breaking among clean, classes b+c vs a): b+c 29/392, a 0/322, OR inf, p = 1.727e-08

## RQ4 primary family (exact McNemar, Holm)

| comparison | pairs | safe A | safe B | A only | B only | risk diff [95% CI] | p | p Holm | reject |
|---|---|---|---|---|---|---|---|---|---|
| C2-LLM vs C1 | 180 | 173 | 167 | 6 | 0 | +3.3 pp [-1.6, +8.5] | 0.03125 | 0.03125 | True |
| C2-LLM vs C0 | 180 | 173 | 164 | 9 | 0 | +5.0 pp [-0.2, +10.4] | 0.003906 | 0.01172 | True |
| C2-template vs C1 | 180 | 176 | 167 | 10 | 1 | +5.0 pp [+0.5, +9.9] | 0.01172 | 0.02344 | True |

Secondary:

- C2-LLM vs C2-template: safe 173 vs 176 of 180 pairs, A only 3, B only 6, risk diff -1.7 pp, p = 0.5078

## RQ4 effort per condition

| condition | chains | safe | mean iterations | tokens/chain | USD/chain | tokens/SAFE_FIX | USD/SAFE_FIX |
|---|---|---|---|---|---|---|---|
| C0 | 180 | 164 | 1.00 | 15,646 | 0.069 | 17,172 | 0.076 |
| C1 | 180 | 167 | 1.01 | 15,770 | 0.070 | 16,997 | 0.076 |
| C2-LLM | 180 | 173 | 1.23 | 23,350 | 0.079 | 24,295 | 0.082 |
| C2-template | 180 | 176 | 1.19 | 21,441 | 0.085 | 21,929 | 0.087 |
