import assert from 'node:assert/strict';
import { chromium } from '../work/browser/node_modules/playwright/index.mjs';

if (process.env.GITHUB_ACTIONS !== 'true') throw new Error('Isolated CI only');
const origin = 'http://127.0.0.1:8317';
const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  const badPaths = [];
  const errors = [];
  page.on('pageerror', error => { errors.push(error.message); console.error('Browser error:', error.message); });
  await page.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin !== origin) return route.abort();
    if (!url.pathname.startsWith('/habitica/')) badPaths.push(url.pathname);
    return route.continue();
  });
  for (const path of ['/habitica/login', '/habitica/register', '/habitica/login']) {
    await page.goto(origin + path);
    console.log(`Checking browser route: ${path}`);
    await page.locator(path.endsWith('/register') ? '#emailInput' : '#usernameInput').waitFor();
    assert.ok(new URL(page.url()).pathname.startsWith('/habitica/'));
  }
  await page.locator('#usernameInput').fill('nonexistent_ci_account');
  await page.locator('#passwordInput').fill('fixture-password');
  const response = page.waitForResponse(res => res.url().includes('/user/auth/local/login'));
  await page.locator('#continue-button').click();
  const login = await response;
  assert.equal(new URL(login.url()).pathname, '/habitica/api/v4/user/auth/local/login');
  assert.equal(login.status(), 401);
  assert.deepEqual(badPaths, [], 'All same-origin resources and API calls must stay inside the prefix');
  assert.deepEqual(errors, [], 'No browser JavaScript errors');
  console.log('PASS: browser boot, login/register deep links, prefixed Axios login and resources');
} finally {
  await browser.close();
}
