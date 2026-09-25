// Vercel Function behind the website's private feedback form. Only the server sees
// the service-account key; the browser sends its report to this same-origin route.
const { createSign } = require('node:crypto');

const MAX_BODY_BYTES = 8 * 1024;
const SCOPES = 'https://www.googleapis.com/auth/spreadsheets';
const KINDS = new Set(['bug', 'word', 'proposal']);

function send(res, status, code) {
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
  });
  res.end(JSON.stringify({ ok: status === 200, code }));
}

function field(value, limit) {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed.length <= limit ? trimmed : null;
}

function validate(body) {
  if (!body || typeof body !== 'object' || Array.isArray(body)) return null;
  if (!KINDS.has(body.kind)) return null;
  const summary = field(body.summary, 120);
  const details = field(body.details, 3000);
  const original = field(body.original ?? '', 120);
  const suggestion = field(body.suggestion ?? '', 120);
  const page = field(body.page, 20);
  if (!summary || !details || original === null || suggestion === null || !['/', '/en/'].includes(page)) return null;
  if (body.kind === 'word' && (!original || !suggestion)) return null;
  return { kind: body.kind, summary, details, original, suggestion, page };
}

async function readBody(req) {
  // Vercel may provide an already parsed body; the local server supplies a stream.
  if (req.body !== undefined) {
    const body = req.body;
    const serialized = typeof body === 'string' ? body : JSON.stringify(body);
    if (Buffer.byteLength(serialized, 'utf8') > MAX_BODY_BYTES) return null;
    try { return typeof body === 'string' ? JSON.parse(body) : body; }
    catch { return null; }
  }
  let size = 0;
  const chunks = [];
  for await (const chunk of req) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) return null;
    chunks.push(chunk);
  }
  try { return JSON.parse(Buffer.concat(chunks).toString('utf8')); }
  catch { return null; }
}

function sameOrigin(req) {
  const origin = req.headers.origin;
  if (typeof origin !== 'string') return false;
  try {
    const url = new URL(origin);
    const local = url.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(url.hostname);
    return (url.protocol === 'https:' || local) && url.host === req.headers.host;
  } catch { return false; }
}

function assertion(credentials, now) {
  const base64url = value => Buffer.from(JSON.stringify(value)).toString('base64url');
  const header = base64url({ alg: 'RS256', typ: 'JWT' });
  const payload = base64url({
    iss: credentials.client_email,
    scope: SCOPES,
    aud: 'https://oauth2.googleapis.com/token',
    iat: now,
    exp: now + 3600,
  });
  const unsigned = `${header}.${payload}`;
  const signer = createSign('RSA-SHA256');
  signer.update(unsigned);
  signer.end();
  return `${unsigned}.${signer.sign(credentials.private_key).toString('base64url')}`;
}

async function appendToSheet(report, settings, fetchImpl = fetch) {
  const credentials = JSON.parse(settings.FEEDBACK_GOOGLE_SERVICE_ACCOUNT_JSON);
  if (!credentials.client_email || !credentials.private_key) throw new Error('Missing service account credentials');
  const now = Math.floor(Date.now() / 1000);
  const tokenResponse = await fetchImpl('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer',
      assertion: assertion(credentials, now),
    }),
    signal: AbortSignal.timeout(8000),
  });
  if (!tokenResponse.ok) throw new Error(`Google token request failed (${tokenResponse.status})`);
  const token = await tokenResponse.json();
  if (typeof token.access_token !== 'string') throw new Error('Google did not return an access token');

  const range = encodeURIComponent('Feedback!A:G');
  const sheetId = encodeURIComponent(settings.FEEDBACK_SHEET_ID);
  const response = await fetchImpl(
    `https://sheets.googleapis.com/v4/spreadsheets/${sheetId}/values/${range}:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS`,
    {
      method: 'POST',
      headers: { Authorization: `Bearer ${token.access_token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ values: [[
        new Date().toISOString(), report.kind, report.summary, report.original,
        report.suggestion, report.details, report.page,
      ]] }),
      signal: AbortSignal.timeout(8000),
    },
  );
  if (!response.ok) throw new Error(`Google Sheets append failed (${response.status})`);
  const result = await response.json();
  if (result.updates?.updatedRows !== 1) throw new Error('Google Sheets did not confirm a new row');
}

async function handler(req, res, settings = process.env, fetchImpl = fetch) {
  if (req.method !== 'POST') return send(res, 405, 'method_not_allowed');
  if (!sameOrigin(req)) return send(res, 403, 'forbidden');
  if (!/^application\/json(?:\s*;|$)/i.test(req.headers['content-type'] ?? '')) return send(res, 415, 'unsupported_media_type');
  const body = await readBody(req);
  if (body === null) return send(res, 400, 'invalid_request');
  const report = validate(body);
  if (!report) return send(res, 400, 'invalid_request');
  if (!settings.FEEDBACK_GOOGLE_SERVICE_ACCOUNT_JSON || !settings.FEEDBACK_SHEET_ID) {
    return send(res, 503, 'not_configured');
  }
  try {
    await appendToSheet(report, settings, fetchImpl);
    return send(res, 200, 'received');
  } catch {
    // Keep credentials and visitor input out of deployment logs.
    console.error('Feedback delivery failed');
    return send(res, 502, 'delivery_failed');
  }
}

module.exports = handler;
module.exports.validate = validate;
module.exports.appendToSheet = appendToSheet;
