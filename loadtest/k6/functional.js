// L5 functional checks: every key user journey once, in order, by one user.
import { index, setCurrency, browseProduct, addToCart, viewCart, checkout, summaryToStdout } from './common.js';

export const options = { vus: 1, iterations: 1 };

export default function () {
  index();
  setCurrency('EUR');
  browseProduct('OLJCESPC7Z');
  addToCart('OLJCESPC7Z');
  viewCart();
  checkout();
}

export function handleSummary(data) { return summaryToStdout(data); }
