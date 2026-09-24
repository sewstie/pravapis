// Run `npm ci --prefix website` first. No Python needed to build or serve the site.
import { build } from '../website/node_modules/esbuild/lib/main.js';
import { cp, mkdir, readFile, readdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
await build({
  absWorkingDir: root,
  entryPoints: ['website/engine-worker.ts'],
  outfile: 'public/assets/engine-worker.js',
  bundle: true, format: 'esm', platform: 'browser', target: 'es2022',
  minify: true, legalComments: 'eof', logLevel: 'info',
});
// Ship attribution beside the bundled data, including source-specific data licenses.
await mkdir(new URL('../public/assets/licenses', import.meta.url), { recursive: true });
await cp(new URL('../LICENSE', import.meta.url), new URL('../public/assets/licenses/CODE.txt', import.meta.url));
await cp(new URL('../data/LICENSE', import.meta.url), new URL('../public/assets/licenses/DATA.txt', import.meta.url));
await cp(new URL('../data/morphology/README.md', import.meta.url), new URL('../public/assets/licenses/MORPHOLOGY.txt', import.meta.url));
await cp(new URL('../data/morphology/SOURCE', import.meta.url), new URL('../public/assets/licenses/MORPHOLOGY-SOURCE.txt', import.meta.url));

// Vercel serves only this static output. No Python runtime or functions are built.
// Build Output API also sets noindex only on previews, leaving production indexable.
const output = new URL('../.vercel/output/', import.meta.url);
await mkdir(new URL('static/', output), { recursive: true });
await cp(new URL('../public/', import.meta.url), new URL('static/', output), { recursive: true });
const preview = process.env.VERCEL_ENV === 'preview';
if (preview) {
  for (const path of ['index.html', 'en/index.html', 'developers/index.html']) {
    const target = new URL(`static/${path}`, output);
    const html = await readFile(target, 'utf8');
    await writeFile(target, html.replace('<head>', '<head><meta name="robots" content="noindex, nofollow">'));
  }
}
// Keep clean public URLs while serving the index files generated above.
const routes = [
  { src: '^/api(?:/.*)?$', status: 404 },
  { src: '^/en/?$', dest: '/en/index.html' },
  { src: '^/developers/?$', dest: '/developers/index.html' },
];
if (preview) routes.push({ src: '/(.*)', headers: { 'X-Robots-Tag': 'noindex, nofollow' }, continue: true });
routes.push({ handle: 'filesystem' });
await writeFile(new URL('config.json', output), JSON.stringify({ version: 3, routes }, null, 2) + '\n');
console.log(`Static website built (${preview ? 'preview: noindex' : 'production/local'}).`);
