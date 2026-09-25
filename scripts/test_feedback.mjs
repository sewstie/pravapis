import assert from 'node:assert/strict';
import { generateKeyPairSync, verify } from 'node:crypto';
import { Readable } from 'node:stream';
import { test } from 'node:test';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const handler = require('../website/feedback-handler.cjs');
const { privateKey, publicKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
const settings = {
  FEEDBACK_SHEET_ID: 'test-sheet-id',
  FEEDBACK_GOOGLE_SERVICE_ACCOUNT_JSON: JSON.stringify({
    client_email: 'feedback@example.iam.gserviceaccount.com',
    private_key: privateKey.export({ type: 'pkcs8', format: 'pem' }),
  }),
};
const valid = {
  kind: 'word', summary: 'Wrong spelling', original: 'снег',
  suggestion: 'сьнег', details: '=HYPERLINK("https://example.com")', page: '/en/',
};

async function invoke(body, options = {}) {
  const bytes = typeof body === 'string' ? body : JSON.stringify(body);
  const req = Readable.from([Buffer.from(bytes)]);
  req.method = options.method ?? 'POST';
  req.headers = {
    host: 'pravapis.example',
    origin: options.origin ?? 'https://pravapis.example',
    'content-type': options.contentType ?? 'application/json',
  };
  if (options.parsedBody !== undefined) req.body = options.parsedBody;
  let status;
  let response;
  const res = {
    writeHead(code) { status = code; },
    end(data) { response = JSON.parse(data); },
  };
  await handler(req, res, options.settings ?? settings, options.fetch ?? (() => { throw new Error('unexpected network request'); }));
  return { status, response };
}

test('appends one private row and signs a Google service-account assertion', async () => {
  let calls = 0;
  const fetchMock = async (url, options) => {
    calls++;
    if (calls === 1) {
      assert.equal(url, 'https://oauth2.googleapis.com/token');
      const claim = options.body.get('assertion');
      const [header, payload, signature] = claim.split('.');
      assert.equal(JSON.parse(Buffer.from(header, 'base64url')).alg, 'RS256');
      assert.equal(JSON.parse(Buffer.from(payload, 'base64url')).scope, 'https://www.googleapis.com/auth/spreadsheets');
      assert.ok(verify('RSA-SHA256', Buffer.from(`${header}.${payload}`), publicKey, Buffer.from(signature, 'base64url')));
      return new Response(JSON.stringify({ access_token: 'test-token' }), { status: 200 });
    }
    assert.match(url, /\/spreadsheets\/test-sheet-id\/values\/Feedback!A%3AG:append\?valueInputOption=RAW&insertDataOption=INSERT_ROWS$/);
    assert.equal(options.headers.Authorization, 'Bearer test-token');
    const row = JSON.parse(options.body).values[0];
    assert.equal(row.length, 7);
    assert.deepEqual(row.slice(1), ['word', 'Wrong spelling', 'снег', 'сьнег', valid.details, '/en/']);
    assert.ok(!Number.isNaN(Date.parse(row[0])));
    return new Response(JSON.stringify({ updates: { updatedRows: 1 } }), { status: 200 });
  };
  assert.deepEqual(await invoke(valid, { fetch: fetchMock }), { status: 200, response: { ok: true, code: 'received' } });
  assert.equal(calls, 2);
});

test('rejects malformed, cross-origin, and oversized submissions before any network call', async () => {
  for (const [body, options, status] of [
    [valid, { method: 'GET' }, 405],
    [valid, { origin: 'https://another.example' }, 403],
    [valid, { contentType: 'text/plain' }, 415],
    ['{broken', {}, 400],
    [{ ...valid, kind: 'unknown' }, {}, 400],
    [{ ...valid, original: '' }, {}, 400],
    [{ ...valid, summary: '' }, {}, 400],
    [{ ...valid, page: 'https://another.example' }, {}, 400],
    [{ ...valid, details: 'a'.repeat(9000) }, {}, 400],
  ]) {
    const result = await invoke(body, options);
    assert.equal(result.status, status, JSON.stringify(body).slice(0, 50));
    assert.equal(result.response.ok, false);
  }
});

test('reports missing setup and delivery errors without claiming success', async () => {
  assert.equal((await invoke(valid, { settings: {} })).status, 503);
  const oldError = console.error;
  const logs = [];
  console.error = (...parts) => logs.push(parts.join(' '));
  try {
    const result = await invoke(valid, { fetch: async () => new Response('{}', { status: 401 }) });
    assert.equal(result.status, 502);
    assert.equal(result.response.code, 'delivery_failed');
    assert.ok(!logs.join(' ').includes(valid.details));
    assert.ok(!logs.join(' ').includes(privateKey.export({ type: 'pkcs8', format: 'pem' })));
  } finally {
    console.error = oldError;
  }
});

test('accepts Vercel parsed bodies under the same size limit', async () => {
  const result = await invoke('', { parsedBody: { ...valid, details: 'a'.repeat(9000) } });
  assert.equal(result.status, 400);
  const missing = await invoke('', { parsedBody: valid, settings: {} });
  assert.equal(missing.status, 503);
});
