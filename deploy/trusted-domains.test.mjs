import assert from 'node:assert/strict';
import test from 'node:test';
import { parseTrustedDomains } from '../website/client/src/libs/trustedDomains.mjs';

test('legacy personal configuration accepts a bare IP without breaking module initialization', () => {
  const urls = parseTrustedDomains('localhost,127.0.0.1,http://127.0.0.1:8317');
  assert.deepEqual(urls.map(url => url.hostname), ['localhost', '127.0.0.1', '127.0.0.1']);
  assert.equal(urls[2].port, '8317');
});

test('empty or malformed entries do not stop the application loading', () => {
  const urls = parseTrustedDomains(' ,not a url,https://,[invalid],https://example.com/habitica,');
  assert.deepEqual(urls.map(url => url.origin), ['https://example.com']);
  assert.deepEqual(parseTrustedDomains(), []);
});

test('only HTTP URLs without embedded credentials become trusted entries', () => {
  const urls = parseTrustedDomains('ftp://example.com,https://user:pass@example.com, example.org ');
  assert.deepEqual(urls.map(url => url.origin), ['https://example.org']);
});
