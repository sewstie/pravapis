import { initConverter } from './converter.js';

let converter = initConverter();
let navigation = 0;
let activeURL = location.pathname;

function initTheme() {
  document.getElementById('theme')?.addEventListener('click', () => {
    const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem('pravapis-theme', theme); } catch { /* Optional preference. */ }
  });
}
initTheme();

// Keep submitted text only in memory. Real links remain the no-JavaScript fallback.
async function switchLanguage(url, push) {
  const id = ++navigation;
  try {
    const response = await fetch(url, { headers: { Accept: 'text/html' } });
    if (!response.ok) throw new Error('Language page unavailable');
    const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
    if (!doc.getElementById('converter')) throw new Error('Not a converter page');
    if (id !== navigation) return;
    const saved = converter?.snapshot();
    converter?.dispose();
    const scroll = window.scrollY;
    document.documentElement.lang = doc.documentElement.lang;
    document.title = doc.title;
    for (const selector of ['meta[name="description"]', 'meta[property^="og:"]', 'link[rel="canonical"]', 'link[rel="alternate"]']) {
      document.head.querySelectorAll(selector).forEach(node => node.remove());
      doc.head.querySelectorAll(selector).forEach(node => document.head.append(document.importNode(node, true)));
    }
    document.body.replaceWith(document.importNode(doc.body, true));
    if (push) history.pushState(null, '', url);
    activeURL = new URL(url, location.href).pathname;
    converter = initConverter(saved);
    initTheme();
    const current = document.querySelector('[data-language][aria-current="page"]');
    current?.focus({ preventScroll: true });
    window.scrollTo({ top: scroll, behavior: 'instant' });
  } catch {
    if (id !== navigation) return;
    if (!push) history.replaceState(null, '', activeURL);
    converter?.languageFailed();
  }
}

document.addEventListener('click', event => {
  const link = event.target.closest('a[data-language]');
  if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  if (new URL(link.href).pathname !== activeURL) switchLanguage(link.href, true);
});
window.addEventListener('popstate', () => {
  if (location.pathname !== activeURL) switchLanguage(location.href, false);
});
