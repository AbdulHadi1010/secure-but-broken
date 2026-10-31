// L6 load test. 30 s warm-up (excluded from metrics) then 120 s measured at 10 virtual users.
// Journey mix follows the upstream loadgenerator task weights.
import { sleep } from 'k6';
import { index, setCurrency, browseProduct, addToCart, viewCart, checkout, summaryToStdout } from './common.js';

const WEIGHTED = [[index, 1], [setCurrency, 2], [browseProduct, 10], [addToCart, 2], [viewCart, 3], [checkout, 1]];
const TOTAL = WEIGHTED.reduce((s, [, w]) => s + w, 0);

export const options = {
  scenarios: {
    warmup: { executor: 'constant-vus', vus: 5, duration: '30s', tags: { phase: 'warmup' } },
    main: { executor: 'constant-vus', vus: 10, duration: '120s', startTime: '30s', tags: { phase: 'main' } },
  },
  // Thresholds that always pass: they only make k6 report the measured-phase sub-metrics.
  thresholds: {
    'http_req_duration{phase:main}': ['p(95)>=0'],
    'http_req_failed{phase:main}': ['rate>=0'],
    'checks{phase:main}': ['rate>=0'],
  },
  summaryTrendStats: ['avg', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
};

export default function () {
  let r = Math.random() * TOTAL;
  for (const [fn, w] of WEIGHTED) {
    if ((r -= w) < 0) { fn(); break; }
  }
  sleep(1);
}

export function handleSummary(data) { return summaryToStdout(data); }
