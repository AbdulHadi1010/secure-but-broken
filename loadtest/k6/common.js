// Shared user journeys for functional (L5) and load (L6) tests against Online Boutique.
import http from 'k6/http';
import { check } from 'k6';

export const BASE = __ENV.BASE_URL || 'http://frontend.boutique.svc.cluster.local';

// Product IDs from upstream productcatalogservice/products.json (v0.10.7).
export const PRODUCTS = ['0PUK6V6EV0', '1YMWWN1N4O', '2ZYFJ3GM2N', '66VCHSJNUP', '6E92ZMYYFZ',
  '9SIQT8TOJO', 'L9ECAV7KIM', 'LS4PSXUNUM', 'OLJCESPC7Z'];
export const CURRENCIES = ['EUR', 'USD', 'JPY', 'CAD', 'GBP', 'TRY'];

// Upstream demo checkout data (same values as upstream loadgenerator).
export const CHECKOUT = {
  email: 'someone@example.com', street_address: '1600 Amphitheatre Parkway', zip_code: '94043',
  city: 'Mountain View', state: 'CA', country: 'United States', credit_card_number: '4432801561520454',
  credit_card_expiration_month: '1', credit_card_expiration_year: '2039', credit_card_cvv: '672',
};

const pick = (a) => a[Math.floor(Math.random() * a.length)];
const ok = (res, name, extra) => check(res, { [`${name} 200`]: (r) => r.status === 200, ...(extra || {}) });

export function index() { return ok(http.get(`${BASE}/`, { tags: { journey: 'index' } }), 'index'); }

export function setCurrency(c) {
  return ok(http.post(`${BASE}/setCurrency`, { currency_code: c || pick(CURRENCIES) }, { tags: { journey: 'setCurrency' } }), 'setCurrency');
}

export function browseProduct(p) {
  const res = http.get(`${BASE}/product/${p || pick(PRODUCTS)}`, { tags: { journey: 'browseProduct' } });
  // The frontend hides failures of these two services (page still 200), so check the content:
  // recommendations block, and the text ad (upstream templates/ad.html renders <strong>Ad</strong> only if adservice answered).
  return ok(res, 'browseProduct', {
    'browseProduct has recommendations': (r) => r.body && r.body.includes('You May Also Like'),
    'browseProduct has ad': (r) => r.body && r.body.includes('<strong>Ad</strong>'),
  });
}

export function addToCart(p) {
  return ok(http.post(`${BASE}/cart`, { product_id: p || pick(PRODUCTS), quantity: String(1 + Math.floor(Math.random() * 3)) },
    { tags: { journey: 'addToCart' } }), 'addToCart');
}

export function viewCart() { return ok(http.get(`${BASE}/cart`, { tags: { journey: 'viewCart' } }), 'viewCart'); }

export function checkout() {
  addToCart();
  const res = http.post(`${BASE}/cart/checkout`, CHECKOUT, { tags: { journey: 'checkout' } });
  return ok(res, 'checkout', { 'checkout order complete': (r) => r.body && r.body.toLowerCase().includes('order') && r.body.includes('Confirmation') });
}

export function summaryToStdout(data) {
  return { stdout: `\n===K6_SUMMARY_BEGIN===\n${JSON.stringify(data)}\n===K6_SUMMARY_END===\n` };
}
