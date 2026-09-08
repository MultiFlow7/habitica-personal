import assert from 'node:assert/strict';
import { randomBytes } from 'node:crypto';
import { chromium } from '../work/browser/node_modules/playwright/index.mjs';

if (process.env.GITHUB_ACTIONS !== 'true') throw new Error('Isolated CI only');
const origin = 'http://127.0.0.1:8317';
const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  const badPaths = [];
  const errors = [];
  page.on('pageerror', error => { errors.push(error.message); console.error('Browser error:', error.message); });
  page.on('console', message => {
    if (message.type() === 'error') console.error('Browser console:', message.text().slice(0, 300));
  });
  page.on('request', req => {
    if (req.method() === 'POST') console.log('Browser POST:', new URL(req.url()).pathname);
  });
  page.on('requestfailed', req => {
    if (new URL(req.url()).origin === origin) console.error('Request failed:', new URL(req.url()).pathname, req.failure()?.errorText);
  });
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
    const privacyChoice = page.locator('#privacy-banner .btn-secondary');
    if (await privacyChoice.isVisible()) await privacyChoice.click();
    assert.ok(new URL(page.url()).pathname.startsWith('/habitica/'));
  }
  await page.locator('#usernameInput').fill('ci_missing_user');
  await page.locator('#passwordInput').fill('fixture-password');
  console.log('Login form validity:', await page.locator('#login-form').evaluate(form => ({
    valid: form.checkValidity(),
    invalidInputs: [...form.querySelectorAll(':invalid')].map(el => el.id),
  })));
  const [login] = await Promise.all([
    page.waitForResponse(res => res.url().includes('/user/auth/local/login')),
    page.locator('#login-form button[type=submit]').click({ timeout: 10000 }),
  ]);
  assert.equal(new URL(login.url()).pathname, '/habitica/api/v4/user/auth/local/login');
  assert.equal(login.status(), 401);
  const username = `web_${randomBytes(6).toString('hex')}`;
  await page.goto(`${origin}/habitica/register`);
  await page.locator('#emailInput').fill(`${username}@example.com`);
  await page.locator('#passwordInput').fill('isolated-fixture-password');
  await page.locator('#confirmPasswordInput').fill('isolated-fixture-password');
  await page.locator('#continue-button').click();
  await page.locator('#usernameInput').fill(username);
  await page.locator('label[for=privacyTOS]').click();
  const [registration] = await Promise.all([
    page.waitForResponse(res => res.url().includes('/user/auth/local/register')),
    page.locator('button[type=submit]').click(),
  ]);
  assert.equal(registration.status(), 200);
  await page.waitForURL(`${origin}/habitica/`);
  await page.locator('#loading-screen-inapp').waitFor({ state: 'hidden', timeout: 30000 });
  console.log('PASS: browser registration reaches authenticated application');
  await page.reload();
  await page.locator('#loading-screen-inapp').waitFor({ state: 'hidden', timeout: 30000 });
  console.log('PASS: authenticated refresh');
  assert.deepEqual(badPaths, [], 'All same-origin resources and API calls must stay inside the prefix');
  assert.deepEqual(errors, [], 'No browser JavaScript errors');
  console.log('PASS: browser boot, login/register deep links, prefixed Axios login and resources');
} finally {
  await browser.close();
}
