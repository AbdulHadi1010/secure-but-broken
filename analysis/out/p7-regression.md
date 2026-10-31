# P7 sensitivity: mixed-effects logistic regression of SAFE_FIX

Variational Bayes (statsmodels BinomialBayesMixedGLM); random intercept per case; references C1, kimi-k3, privileged, W0.

## All chains (n=1440)

| term | log-odds | SD | OR | OR 95% interval | excludes 1 |
|---|---|---|---|---|---|
| Intercept | 6.149 | 0.153 | 468 | [347, 632] | True |
| C(condition, Treatment('C1'))[T.C0] | 0.242 | 0.266 | 1.27 | [0.756, 2.15] | False |
| C(condition, Treatment('C1'))[T.C2-LLM] | 1.663 | 0.335 | 5.27 | [2.74, 10.2] | True |
| C(condition, Treatment('C1'))[T.C2-template] | 2.830 | 0.439 | 16.9 | [7.17, 40] | True |
| C(model, Treatment('kimi-k3'))[T.deepseek-v3-2] | -2.910 | 0.214 | 0.0544 | [0.0358, 0.0828] | True |
| C(model, Treatment('kimi-k3'))[T.glm-5] | -0.790 | 0.279 | 0.454 | [0.262, 0.784] | True |
| C(type, Treatment('privileged'))[T.added-capabilities] | 2.478 | 1.236 | 11.9 | [1.06, 134] | True |
| C(type, Treatment('privileged'))[T.allow-privilege-escalation] | 0.520 | 0.705 | 1.68 | [0.423, 6.69] | False |
| C(type, Treatment('privileged'))[T.missing-limits] | -0.005 | 0.600 | 0.995 | [0.307, 3.22] | False |
| C(type, Treatment('privileged'))[T.netpol] | -3.021 | 0.167 | 0.0487 | [0.0351, 0.0676] | True |
| C(type, Treatment('privileged'))[T.run-as-root] | 2.478 | 1.236 | 11.9 | [1.06, 134] | True |
| C(wording, Treatment('W0'))[T.W1] | -0.060 | 0.215 | 0.942 | [0.618, 1.43] | False |
| case random-intercept SD (log scale param) | 0.285 | 0.163 | | | |

## W0 only (n=720)

| term | log-odds | SD | OR | OR 95% interval | excludes 1 |
|---|---|---|---|---|---|
| Intercept | 6.082 | 0.218 | 438 | [286, 671] | True |
| C(condition, Treatment('C1'))[T.C0] | -0.297 | 0.367 | 0.743 | [0.362, 1.52] | False |
| C(condition, Treatment('C1'))[T.C2-LLM] | 1.272 | 0.474 | 3.57 | [1.41, 9.04] | True |
| C(condition, Treatment('C1'))[T.C2-template] | 2.080 | 0.556 | 8 | [2.69, 23.8] | True |
| C(model, Treatment('kimi-k3'))[T.deepseek-v3-2] | -2.939 | 0.290 | 0.0529 | [0.03, 0.0935] | True |
| C(model, Treatment('kimi-k3'))[T.glm-5] | -0.293 | 0.435 | 0.746 | [0.318, 1.75] | False |
| C(type, Treatment('privileged'))[T.added-capabilities] | 2.157 | 1.245 | 8.65 | [0.753, 99.3] | False |
| C(type, Treatment('privileged'))[T.allow-privilege-escalation] | 0.967 | 0.903 | 2.63 | [0.448, 15.4] | False |
| C(type, Treatment('privileged'))[T.missing-limits] | 0.967 | 0.903 | 2.63 | [0.448, 15.4] | False |
| C(type, Treatment('privileged'))[T.netpol] | -2.507 | 0.242 | 0.0815 | [0.0507, 0.131] | True |
| C(type, Treatment('privileged'))[T.run-as-root] | 2.157 | 1.245 | 8.65 | [0.753, 99.3] | False |
| case random-intercept SD (log scale param) | 0.429 | 0.163 | | | |
