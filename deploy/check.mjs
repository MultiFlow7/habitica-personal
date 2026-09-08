// Read-only production checks. No account, task, or database mutations.
import assert from 'node:assert/strict';

const origin = 'http://127.0.0.1:3000';
const headers = { 'x-forwarded-proto': 'https' };
const config = JSON.parse(await (await import('node:fs/promises')).readFile('config.json', 'utf8'));
headers.host = new URL(config.BASE_URL).host;
async function get(path) {
  return fetch(origin + path, { headers, redirect: 'manual', signal: AbortSignal.timeout(30000) });
}
const status = await get('/habitica/api/v3/status');
assert.equal(status.status, 200);
assert.equal((await status.json()).success, true);
const root = await get('/habitica');
assert.equal(root.status, 308);
assert.equal(root.headers.get('location'), '/habitica/');
for (const path of ['/habitica/', '/habitica/login', '/habitica/tasks']) {
  const res = await get(path);
  assert.equal(res.status, 200, path);
  const html = await res.text();
  const asset = html.match(/src="(\/habitica\/assets\/[^" ]+\.js)"/);
  assert.ok(asset, 'Built entry must use the application base path');
  const js = await get(asset[1]);
  assert.equal(js.status, 200);
  assert.match(js.headers.get('content-type'), /javascript/);
  assert.ok(html.includes('/habitica/api/v4/i18n/core'));
}
const i18n = await get('/habitica/api/v4/i18n/core');
assert.equal(i18n.status, 200);
assert.match(i18n.headers.get('content-type'), /javascript/);
assert.equal((await get('/habitica/api/v3/not-a-real-endpoint')).status, 404);
console.log('PASS: read-only status, subpath redirect, deep links, JavaScript and translations');
