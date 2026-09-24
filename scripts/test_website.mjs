// Run `npm run dev --prefix website` first, then: node scripts/test_website.mjs
import { chromium } from '../website/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
import { changeSegments } from '../public/assets/converter.js';

const origin = process.env.WEBSITE_URL || 'http://127.0.0.1:5329';
const browser = await chromium.launch({
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || undefined,
});
const context = await browser.newContext({ viewport: { width: 1440, height: 1080 }, permissions: ['clipboard-read', 'clipboard-write'] });
const page = await context.newPage();
const errors = [];
const requests = [];
context.on('request', request => requests.push({ method: request.method(), url: request.url() }));
page.on('pageerror', error => errors.push(error.message));
const output = page.locator('#output');
const input = page.locator('#input');
const mode = page.locator('#mode');
let checks = 0;
function check(value, message) { assert.ok(value, message); checks++; }
async function convert() {
  await page.locator('#convert').click();
  await page.waitForFunction(() => document.querySelector('#output').getAttribute('aria-busy') === 'false' && document.querySelector('#output').textContent.length > 0);
  assert.equal(await page.locator('#status').getAttribute('class'), 'status', await page.locator('#status').textContent());
}
try {
  await page.goto(origin);
  check(await page.locator('html').getAttribute('lang') === 'be', 'Belarusian default');
  check(await page.locator('.brand-icon').first().textContent() === 'BY', 'BY brand mark');
  check((await page.locator('.faq').textContent()).includes('Чым адрозніваюцца лацінка'), 'Belarusian Latin-script explanation');
  await input.fill('🎉 Снег і план сістэмы. <img src=x onerror=alert(1)>');
  await convert();
  check((await output.textContent()).startsWith('🎉 Сьнег і плян сыстэмы.'), 'Real orthography conversion');
  check(await output.locator('mark').first().textContent() === 'Сьнег', 'Emoji-aware highlight');
  check(await output.locator('img').count() === 0, 'Output cannot inject HTML');
  check(await page.locator('#change-list li').count() >= 3, 'Change evidence');
  await page.locator('#copy').click();
  check(await page.evaluate(() => navigator.clipboard.readText()) === await output.textContent(), 'Plain text clipboard');
  await page.locator('[data-language][lang=en]').click();
  await page.waitForURL('**/en/');
  check((await input.inputValue()).includes('🎉 Снег'), 'Input survives language switch');
  check((await output.textContent()).includes('Сьнег'), 'Result survives language switch');
  check((await page.title()).includes('Belarusian Orthography'), 'Language metadata');
  check((await page.locator('.faq').textContent()).includes('What is the difference between Łacinka'), 'English Latin-script explanation');
  await page.goBack();
  await page.waitForFunction(() => document.documentElement.lang === 'be');
  check((await input.inputValue()).includes('🎉 Снег'), 'Back navigation retains input');
  check(await page.locator('#feedback h2').textContent() === 'Пакінуць водгук', 'Belarusian feedback form');
  await page.goForward();
  await page.waitForFunction(() => document.documentElement.lang === 'en');
  await mode.selectOption('narkamauka');
  check((await input.inputValue()).includes('🎉 Снег'), 'Mode change preserves input');
  check(await output.evaluate(el => el.classList.contains('outdated')), 'Mode marks output stale');
  check(await page.locator('#copy').isDisabled(), 'Stale output cannot be copied as current');
  const samples = [
    ['narkamauka', 'taraskievica', false, 'Снег і план', 'Сьнег і плян'],
    ['taraskievica', 'narkamauka', false, 'Сьнег і плян', 'Снег і план'],
    ['narkamauka', 'taraskievica', true, 'Снег і план', 'Śnieh i plan'],
    ['taraskievica', 'narkamauka', true, 'Сьнег і плян', 'Snieh i płan'],
    ['narkamauka', 'narkamauka', true, 'Снег і план', 'Snieh i płan'],
    ['taraskievica', 'taraskievica', true, 'Сьнег і плян', 'Śnieh i plan'],
    ['narkamauka', 'narkamauka', false, 'Снег і план', 'Снег і план'],
    ['taraskievica', 'taraskievica', false, 'Сьнег і плян', 'Сьнег і плян'],
  ];
  for (const [from, to, latin, source, expected] of samples) {
    await page.locator('#source').selectOption(from);
    await mode.selectOption(to);
    await page.locator('#latin-output').setChecked(latin);
    await input.fill(source); await convert();
    check(await output.textContent() === expected, `Browser conversion ${from} → ${to}, Latin ${latin}: ${await output.textContent()}`);
  }
  await page.locator('#latin-output').check();
  check(await page.locator('#copy').isDisabled(), 'Latin toggle invalidates result');
  await convert();
  await page.locator('[data-language][lang=be]').click();
  await page.waitForURL(origin + '/');
  check(await page.locator('#latin-output').isChecked() && await page.locator('#source').inputValue() === 'taraskievica', 'Language switch retains orthography and Latin choice');
  check(await output.textContent() === 'Śnieh i plan', 'Language switch retains Latin result');
  await page.locator('[data-language][lang=en]').click();
  await page.waitForURL('**/en/');
  await page.locator('#source').selectOption('narkamauka');
  await page.locator('#latin-output').uncheck();
  await convert(); // Load the new language page's worker before going offline.
  await context.setOffline(true);
  await mode.selectOption('taraskievica'); await input.fill('Снег і план'); await convert();
  check(await output.textContent() === 'Сьнег і плян', 'Conversion works offline after engine load');
  await context.setOffline(false);
  await page.locator('#use-result').click();
  check(await input.inputValue() === 'Сьнег і плян', 'Explicit result chaining');
  await page.locator('#clear').click();
  await page.locator('#convert').click();
  check((await page.locator('#status').textContent()).includes('Enter some'), 'Empty input feedback');
  await input.fill('😀'.repeat(50000));
  check(await input.getAttribute('aria-invalid') === 'false', 'Unicode limit counts emoji once');
  await input.fill('😀'.repeat(50001));
  await page.locator('#convert').click();
  check((await page.locator('#status').textContent()).includes('50,000'), 'Oversize feedback');
  await input.fill('Снег'); await mode.selectOption('taraskievica');
  // A blocked worker download must give localized feedback without losing input.
  await page.reload();
  await input.fill('Снег');
  await page.evaluate(() => {
    window.originalWorker = window.Worker;
    window.Worker = class { constructor() { throw new Error('Blocked'); } };
  });
  await page.locator('#convert').click();
  await page.waitForFunction(() => document.querySelector('#status').classList.contains('error'));
  check(await input.inputValue() === 'Снег', 'Worker failure preserves text');
  check((await page.locator('#status').textContent()).includes('Could not load'), 'Engine load error is useful');

  // A worker deliberately ignores termination: request IDs must still protect output.
  await page.evaluate(() => {
    window.Worker = class {
      postMessage(data) { setTimeout(() => this.onmessage?.({ data: { id: data.id, result: { text: 'STALE', changes: [] } } }), 400); }
      terminate() {}
    };
  });
  await page.locator('#convert').click();
  await input.fill('Новы тэкст');
  await page.waitForTimeout(600);
  check(!(await output.textContent()).includes('STALE'), 'Stale response rejected even without cancellation');
  await page.evaluate(() => { window.Worker = window.originalWorker; });
  await input.fill('Снег і план сістэмы.'); await convert();
  await page.locator('#show-changes').uncheck();
  check(await output.locator('mark').count() === 0, 'Hide highlights');
  await page.locator('#show-changes').check();
  await page.locator('#theme').click();
  check(await page.locator('html').getAttribute('data-theme') === 'dark', 'Dark theme');
  await page.reload();
  check(await page.locator('html').getAttribute('data-theme') === 'dark', 'Theme persists');
  check(await input.inputValue() === '', 'Text is not persisted');
  const storage = await page.evaluate(() => ({ local: Object.keys(localStorage), session: Object.keys(sessionStorage) }));
  check(storage.local.every(key => key === 'pravapis-theme') && storage.session.length === 0, 'Only theme stored');
  await page.locator('#theme').click();
  for (const path of ['/', '/en/', '/developers/']) {
    await page.setViewportSize({ width: 375, height: 812 });
    const response = await page.goto(origin + path);
    check(response.status() === 200, `Clean URL ${path}`);
    check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Mobile overflow ${path}`);
  }
  check(await page.locator('meta[name="robots"]').count() === 0, 'Production pages stay indexable');
  const api = await page.request.post(origin + '/api/convert', { data: { text: 'Снег' } });
  check([404, 405].includes(api.status()), 'Removed Python API stays absent');
  await page.goto(origin + '/en/');
  check(await page.locator('.footer-left > span:not(.brand-icon)').count() === 0, 'Author attribution removed from footer');
  check(await page.locator('.footer-links a[href*="/data/LICENSE"]').count() === 0, 'Data licence removed from footer');
  const feedback = page.locator('#feedback-form');
  check(await feedback.count() === 1, 'Feedback form appears');
  await page.locator('#feedback-kind').selectOption('word');
  check(await page.locator('#feedback-original').evaluate(el => el.required), 'Word reports require the original spelling');
  check(await page.locator('#feedback-suggestion').evaluate(el => el.required), 'Word reports require a suggestion');
  await page.locator('#feedback-summary').fill('Wrong spelling');
  await page.locator('#feedback-original').fill('снег');
  await page.locator('#feedback-suggestion').fill('сьнег');
  await page.locator('#feedback-details').fill('This form stays local until I review the public GitHub draft.');
  await page.evaluate(() => {
    window.feedbackTarget = null;
    window.open = url => { window.feedbackTarget = url; return { opener: window }; };
  });
  await feedback.locator('[type=submit]').click();
  await page.waitForFunction(() => document.querySelector('#feedback-status').textContent.includes('draft is copied'));
  check((await page.evaluate(() => navigator.clipboard.readText())).includes('снег'), 'Feedback draft copied for review');
  check(await page.evaluate(() => window.feedbackTarget) === 'https://github.com/sewstie/pravapis/issues/new', 'Feedback opens a clean issue URL with no text');
  await page.locator('#feedback-kind').selectOption('proposal');
  check(await page.locator('#feedback-words').isHidden(), 'Spelling fields are hidden for proposals');
  check(!(await page.locator('#feedback-original').evaluate(el => el.required)), 'Proposal does not require spelling fields');
  await page.locator('#example').click();
  await input.press('Control+Enter');
  await page.waitForFunction(() => document.querySelector('#output').textContent.includes('Сьнег'));
  check(true, 'Keyboard shortcut');
  const noJS = await browser.newContext({ javaScriptEnabled: false });
  const staticPage = await noJS.newPage();
  await staticPage.goto(origin + '/en/');
  check(await staticPage.locator('#how-it-works').isVisible(), 'Content is indexable without JavaScript');
  check(await staticPage.locator('noscript').isVisible(), 'No-JS explanation');
  await noJS.close();
  const segments = changeSegments('😀 Сьнег', [{ start: 2, end: 7, from: 'Снег', to: 'Сьнег' }]);
  check(segments[1].text === 'Сьнег', 'Code-point slicing unit boundary');
  check(requests.every(request => request.method === 'GET' && !request.url.includes('/api/')), 'No API requests or submitted text over the network');
  check(errors.length === 0, `No browser errors: ${errors.join(', ')}`);
  console.log(`${checks} website checks passed.`);
} finally {
  await browser.close();
}
