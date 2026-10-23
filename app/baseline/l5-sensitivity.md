# L5 functional-check sensitivity (validation of the measuring instrument)

Question: does L5 fail when a dependency of the app is broken? Method: deploy gold on a fresh kind
cluster, run `functional.js` healthy, then scale each backend service to 0 in turn, re-run L5, restore.
Trials 2-5 on 2026-10-03 (not part of the baseline; tooling validation only).

| Service scaled to 0 | L5 pass rate | Failed checks | Detected |
|---|---|---|---|
| (none, healthy) | 1.00 | — | — |
| adservice | 0.90 | browseProduct has ad | yes (after adding ad content check) |
| cartservice | 0.00 | all | yes |
| checkoutservice | 0.80 | checkout 200, checkout order complete | yes |
| currencyservice | 0.00 | all | yes |
| emailservice | 0.91 | checkout email sent (checkoutservice log) | yes (after adding log check) |
| paymentservice | 0.80 | checkout 200, checkout order complete | yes |
| productcatalogservice | 0.30 | index, setCurrency, browseProduct, addToCart | yes |
| recommendationservice | 0.90 | browseProduct has recommendations | yes |
| redis-cart | 0.00 | all | yes |
| shippingservice | 0.50 | addToCart, viewCart, checkout | yes |

Two blind spots were found and fixed before any baseline run: the frontend hides adservice failures (page
still 200) and checkout still succeeds when emailservice is down (failure only logged by checkoutservice).
Fixes: content check for the rendered text ad (upstream `templates/ad.html`) and a checkoutservice log check
for the upstream confirmation-email log lines (`checkoutservice/main.go` v0.10.7 lines 274/276).
Scope: L5 detects a service being unavailable; partial degradation is the job of L6 (load).
