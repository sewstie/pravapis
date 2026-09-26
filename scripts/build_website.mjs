// Bundles the browser engine and assembles the static Vercel deployment.
import { build } from '../website/node_modules/esbuild/lib/main.js';
import { cp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
await build({
  absWorkingDir: root,
  entryPoints: ['website/engine-worker.ts'],
  outfile: 'public/assets/engine-worker.js',
  bundle: true, format: 'esm', platform: 'browser', target: 'es2022',
  minify: true, legalComments: 'eof', logLevel: 'info',
});
await mkdir(new URL('../public/assets/licenses', import.meta.url), { recursive: true });
await cp(new URL('../LICENSE', import.meta.url), new URL('../public/assets/licenses/CODE.txt', import.meta.url));
await cp(new URL('../data/LICENSE', import.meta.url), new URL('../public/assets/licenses/DATA.txt', import.meta.url));
await cp(new URL('../data/morphology/README.md', import.meta.url), new URL('../public/assets/licenses/MORPHOLOGY.txt', import.meta.url));
await cp(new URL('../data/morphology/SOURCE', import.meta.url), new URL('../public/assets/licenses/MORPHOLOGY-SOURCE.txt', import.meta.url));
const output = new URL('../.vercel/output/', import.meta.url);
// Clear only this workspace's generated output, including the retired Sheets function.
if (!fileURLToPath(output).startsWith(root)) throw new Error('Output must stay within the workspace');
await rm(output, { recursive: true, force: true });
await mkdir(new URL('static/', output), { recursive: true });
await cp(new URL('../public/', import.meta.url), new URL('static/', output), { recursive: true });
await writeFile(new URL('static/assets/feedback-config.json', output), JSON.stringify({
  accessKey: (process.env.WEB3FORMS_ACCESS_KEY || '').trim(),
}) + '\n');
for (const path of ['index.html', 'en/index.html', 'developers/index.html']) {
  const target = new URL(`static/${path}`, output);
  let html = await readFile(target, 'utf8');
  html = html.replace(/<span>(?:By Vladislav Hushcha|Аўтар: Уладзіслаў Гушча)<\/span>/gu, '');
  html = html.replace(/<a href="https:\/\/github\.com\/sewstie\/pravapis\/blob\/main\/data\/LICENSE">(?:Data: source-specific licenses|Даныя: ліцэнзіі крыніц)<\/a>/gu, '');
  await writeFile(target, html);
}
const preview = process.env.VERCEL_ENV === 'preview';
if (preview) {
  for (const path of ['index.html', 'en/index.html', 'developers/index.html']) {
    const target = new URL(`static/${path}`, output);
    const html = await readFile(target, 'utf8');
    await writeFile(target, html.replace('<head>', '<head><meta name="robots" content="noindex, nofollow">'));
  }
}
const routes = [
  { src: '^/api(?:/.*)?$', status: 404 },
  { src: '^/en/?$', dest: '/en/index.html' },
  { src: '^/developers/?$', dest: '/developers/index.html' },
];
if (preview) routes.push({ src: '/(.*)', headers: { 'X-Robots-Tag': 'noindex, nofollow' }, continue: true });
routes.push({ handle: 'filesystem' });
await writeFile(new URL('config.json', output), JSON.stringify({ version: 3, routes }, null, 2) + '\n');
console.log(`Static website built (${preview ? 'preview: noindex' : 'production/local'}).`);
