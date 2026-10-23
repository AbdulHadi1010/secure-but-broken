# P7 results — W1 (secondary)

Chains: 720. Proportions: k/n = % [Wilson 95% CI].

## Overall

- SAFE_FIX: 677/720 = 94.0% [92.1, 95.5]
- Scanner-clean: 716/720 = 99.4% [98.6, 99.8]
- RQ1 breaking among scanner-clean: 34/716 = 4.7% [3.4, 6.6]
- RQ2 deceptive among scanner-clean: 6/716 = 0.8% [0.4, 1.8]

## C0: what a scanner-only evaluation would call success

- Scanner-clean: 180/180 = 100.0% [97.9, 100.0]
- of which actually SAFE: 166/180 = 92.2% [87.4, 95.3]
- of which breaking: 11/180 = 6.1% [3.4, 10.6]
- of which deceptive: 3/180 = 1.7% [0.6, 4.8]

## By model

| | SAFE_FIX | breaking among clean | deceptive among clean |
|---|---|---|---|
| deepseek-v3-2 | 214/240 = 89.2% [84.6, 92.5] | 26/240 = 10.8% [7.5, 15.4] | 1/240 = 0.4% [0.1, 2.3] |
| glm-5 | 228/240 = 95.0% [91.5, 97.1] | 7/240 = 2.9% [1.4, 5.9] | 5/240 = 2.1% [0.9, 4.8] |
| kimi-k3 | 235/240 = 97.9% [95.2, 99.1] | 1/236 = 0.4% [0.1, 2.4] | 0/236 = 0.0% [0.0, 1.6] |

## By condition

| | SAFE_FIX | breaking among clean | deceptive among clean |
|---|---|---|---|
| C0 | 166/180 = 92.2% [87.4, 95.3] | 11/180 = 6.1% [3.4, 10.6] | 3/180 = 1.7% [0.6, 4.8] |
| C1 | 160/180 = 88.9% [83.5, 92.7] | 15/177 = 8.5% [5.2, 13.5] | 2/177 = 1.1% [0.3, 4.0] |
| C2-LLM | 173/180 = 96.1% [92.2, 98.1] | 6/179 = 3.4% [1.5, 7.1] | 0/179 = 0.0% [0.0, 2.1] |
| C2-template | 178/180 = 98.9% [96.0, 99.7] | 2/180 = 1.1% [0.3, 4.0] | 1/180 = 0.6% [0.1, 3.1] |

## By type

| | SAFE_FIX | breaking among clean | deceptive among clean |
|---|---|---|---|
| added-capabilities | 108/108 = 100.0% [96.6, 100.0] | 0/108 = 0.0% [0.0, 3.4] | 0/108 = 0.0% [0.0, 3.4] |
| allow-privilege-escalation | 107/108 = 99.1% [94.9, 99.8] | 0/107 = 0.0% [0.0, 3.5] | 0/107 = 0.0% [0.0, 3.5] |
| missing-limits | 106/108 = 98.1% [93.5, 99.5] | 2/108 = 1.9% [0.5, 6.5] | 0/108 = 0.0% [0.0, 3.4] |
| netpol | 140/180 = 77.8% [71.2, 83.2] | 32/177 = 18.1% [13.1, 24.4] | 6/177 = 3.4% [1.6, 7.2] |
| privileged | 108/108 = 100.0% [96.6, 100.0] | 0/108 = 0.0% [0.0, 3.4] | 0/108 = 0.0% [0.0, 3.4] |
| run-as-root | 108/108 = 100.0% [96.6, 100.0] | 0/108 = 0.0% [0.0, 3.4] | 0/108 = 0.0% [0.0, 3.4] |

## By model x condition

| | SAFE_FIX | breaking among clean | deceptive among clean |
|---|---|---|---|
| deepseek-v3-2 · C0 | 51/60 = 85.0% [73.9, 91.9] | 9/60 = 15.0% [8.1, 26.1] | 0/60 = 0.0% [0.0, 6.0] |
| deepseek-v3-2 · C1 | 49/60 = 81.7% [70.1, 89.4] | 11/60 = 18.3% [10.6, 29.9] | 0/60 = 0.0% [0.0, 6.0] |
| deepseek-v3-2 · C2-LLM | 56/60 = 93.3% [84.1, 97.4] | 4/60 = 6.7% [2.6, 15.9] | 0/60 = 0.0% [0.0, 6.0] |
| deepseek-v3-2 · C2-template | 58/60 = 96.7% [88.6, 99.1] | 2/60 = 3.3% [0.9, 11.4] | 1/60 = 1.7% [0.3, 8.9] |
| glm-5 · C0 | 56/60 = 93.3% [84.1, 97.4] | 1/60 = 1.7% [0.3, 8.9] | 3/60 = 5.0% [1.7, 13.7] |
| glm-5 · C1 | 54/60 = 90.0% [79.9, 95.3] | 4/60 = 6.7% [2.6, 15.9] | 2/60 = 3.3% [0.9, 11.4] |
| glm-5 · C2-LLM | 58/60 = 96.7% [88.6, 99.1] | 2/60 = 3.3% [0.9, 11.4] | 0/60 = 0.0% [0.0, 6.0] |
| glm-5 · C2-template | 60/60 = 100.0% [94.0, 100.0] | 0/60 = 0.0% [0.0, 6.0] | 0/60 = 0.0% [0.0, 6.0] |
| kimi-k3 · C0 | 59/60 = 98.3% [91.1, 99.7] | 1/60 = 1.7% [0.3, 8.9] | 0/60 = 0.0% [0.0, 6.0] |
| kimi-k3 · C1 | 57/60 = 95.0% [86.3, 98.3] | 0/57 = 0.0% [0.0, 6.3] | 0/57 = 0.0% [0.0, 6.3] |
| kimi-k3 · C2-LLM | 59/60 = 98.3% [91.1, 99.7] | 0/59 = 0.0% [0.0, 6.1] | 0/59 = 0.0% [0.0, 6.1] |
| kimi-k3 · C2-template | 60/60 = 100.0% [94.0, 100.0] | 0/60 = 0.0% [0.0, 6.0] | 0/60 = 0.0% [0.0, 6.0] |

## RQ3 tests

| test | method | p |
|---|---|---|
| breaking_by_type | chi-square | 1.551e-18 |
| deceptive_by_type | exact (Monte Carlo, seed 20261016) | 0.00217 |
| safe_by_type | chi-square | 7.89e-23 |
| breaking_by_model | chi-square | 1.691e-07 |
| deceptive_by_model | exact (Monte Carlo, seed 20261016) | 0.05256 |
| safe_by_model | chi-square | 0.0002069 |

H-FC (one-sided Fisher, breaking among clean, classes b+c vs a): b+c 34/393, a 0/323, OR inf, p = 7.074e-10

## RQ4 primary family (exact McNemar, Holm)

| comparison | pairs | safe A | safe B | A only | B only | risk diff [95% CI] | p | p Holm | reject |
|---|---|---|---|---|---|---|---|---|---|
| C2-LLM vs C1 | 180 | 173 | 160 | 16 | 3 | +7.2 pp [+1.8, +13.0] | 0.004425 | 0.00885 | True |
| C2-LLM vs C0 | 180 | 173 | 166 | 8 | 1 | +3.9 pp [-1.1, +9.1] | 0.03906 | 0.03906 | True |
| C2-template vs C1 | 180 | 178 | 160 | 18 | 0 | +10.0 pp [+5.2, +15.5] | 7.629e-06 | 2.289e-05 | True |

Secondary:

- C2-LLM vs C2-template: safe 173 vs 178 of 180 pairs, A only 1, B only 6, risk diff -2.8 pp, p = 0.125

## RQ4 effort per condition

| condition | chains | safe | mean iterations | tokens/chain | USD/chain | tokens/SAFE_FIX | USD/SAFE_FIX |
|---|---|---|---|---|---|---|---|
| C0 | 180 | 166 | 1.00 | 15,532 | 0.067 | 16,842 | 0.073 |
| C1 | 180 | 160 | 1.07 | 17,115 | 0.086 | 19,254 | 0.097 |
| C2-LLM | 180 | 173 | 1.30 | 25,166 | 0.086 | 26,185 | 0.090 |
| C2-template | 180 | 178 | 1.16 | 20,592 | 0.074 | 20,823 | 0.075 |
