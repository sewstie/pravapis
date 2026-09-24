import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const preview = process.argv[2] === 'preview';
const output = '.vercel/output';
for (const path of ['index.html', 'en/index.html', 'developers/index.html']) {
  const html = await readFile(`${output}/static/${path}`, 'utf8');
  assert.equal(html.includes('name="robots" content="noindex, nofollow"'), preview, `${path}: preview robots tag`);
  for (const retired of ['Аўтар: Уладзіслаў Гушча', 'By Vladislav Hushcha', 'Даныя: ліцэнзіі крыніц', 'Data: source-specific licenses']) {
    assert.ok(!html.includes(retired), `${path}: retired footer label ${retired}`);
  }
}
const config = JSON.parse(await readFile(`${output}/config.json`, 'utf8'));
assert.ok(config.routes.some(route => route.src === '^/api(?:/.*)?$' && route.status === 404), 'API route stays removed');
assert.equal(config.routes.some(route => route.headers?.['X-Robots-Tag'] === 'noindex, nofollow'), preview, 'preview response header');
console.log(`${preview ? 'Preview' : 'Production'} HTML, footer, API, and indexing checks passed.`);
