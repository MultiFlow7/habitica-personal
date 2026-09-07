import assert from 'node:assert/strict';
import { randomBytes } from 'node:crypto';
import { readFileSync } from 'node:fs';
import mongoose from 'mongoose';

const base = process.env.SMOKE_URL || 'http://127.0.0.1:3000';
const headers = { 'content-type': 'application/json', 'x-client': 'habitica-personal-smoke' };
// Habitica usernames are limited to 20 characters.
const username = `smk_${randomBytes(8).toString('hex')}`;
const password = randomBytes(24).toString('base64url');
let uid;
async function api(method, path, body) {
  const res = await fetch(`${base}/api/v3${path}`, {
    method, headers, body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(30000),
  });
  const value = await res.json();
  assert.ok(res.ok && value.success, `${method} ${path}: ${res.status} ${value.message || value.error || ''}`);
  return value.data;
}
try {
  const page = await fetch(base);
  assert.equal(page.status, 200);
  const html = await page.text();
  assert.match(html, /<html/i);
  const asset = html.match(/src="(\/assets\/[^" ]+\.js)"/);
  assert.ok(asset, 'Built frontend entry must be present');
  assert.equal((await fetch(base + asset[1])).status, 200);
  const user = await api('POST', '/user/auth/local/register', {
    username, email: `${username}@example.com`, password, confirmPassword: password,
  });
  uid = user._id;
  const login = await api('POST', '/user/auth/local/login', { username, password });
  assert.equal(login._id, uid);
  headers['x-api-user'] = uid;
  headers['x-api-key'] = login.apiToken;
  const before = (await api('GET', '/user')).stats;
  const task = await api('POST', '/tasks/user', { text: 'Deployment verification', type: 'todo', priority: 1 });
  const id = task._id || task.id;
  await api('POST', `/tasks/${id}/score/up`, {});
  assert.equal((await api('GET', `/tasks/${id}`)).completed, true);
  const after = (await api('GET', '/user')).stats;
  assert.ok(after.exp > before.exp);
  assert.ok(after.gp > before.gp);
  console.log('PASS: frontend, asset, registration, login, task creation, completion, XP, gold');
} finally {
  // Only remove the randomly named fixture created by this run.
  const config = JSON.parse(readFileSync('config.json', 'utf8'));
  await mongoose.connect(config.NODE_DB_URI);
  const users = mongoose.connection.collection('users');
  const fixture = await users.findOne({ 'auth.local.username': username });
  if (fixture && (!uid || fixture._id === uid)) {
    await mongoose.connection.collection('tasks').deleteMany({ userId: fixture._id });
    await users.deleteOne({ _id: fixture._id, 'auth.local.username': username });
  }
  await mongoose.disconnect();
}
