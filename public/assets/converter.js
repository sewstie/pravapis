import { createEngineClient } from './engine-client.js';

const MAX_CHARS = 50000;
const COPY = {
  en: {
    n: 'Narkamaŭka', t: 'Taraškievica', c: 'Belarusian Cyrillic', l: 'Łacinka', o: 'Official romanisation',
    ready: 'Ready when you are.', empty: 'Enter some Belarusian text to convert.',
    loading: 'Converting your text…', success: 'Conversion complete. Review your result.',
    outdated: 'Your text or mode changed. Convert again to update the result.',
    limit: 'The limit is 50,000 Unicode characters. Shorten your text and try again.',
    engine: 'Could not load or run the converter. Check your connection for the initial download and try again. Your input is still here.',
    timeout: 'Conversion took too long. Try a shorter passage. Your input is still here.',
    copied: 'Result copied to the clipboard.', copyFailed: 'Copy was unavailable. Select the result and copy it manually.',
    used: 'Result moved to the input. Choose a suitable mode before converting again.',
    languageFailed: 'Could not switch languages. Your text is preserved; please try again.',
    cleared: 'Input and result cleared.', dictionary: 'Dictionary', rule: 'Spelling rule',
    noChanges: 'No orthographic changes reported.', noHighlights: 'This script mode does not return word-level change data.',
  },
  be: {
    n: 'Наркамаўка', t: 'Тарашкевіца', c: 'Беларуская кірыліца', l: 'Лацінка', o: 'Афіцыйная транслітарацыя',
    ready: 'Усё гатова да працы.', empty: 'Увядзіце беларускі тэкст для пераўтварэння.',
    loading: 'Пераўтварэнне тэксту…', success: 'Пераўтварэнне завершана. Праверце вынік.',
    outdated: 'Тэкст або рэжым зменены. Пераўтварыце яшчэ раз, каб абнавіць вынік.',
    limit: 'Ліміт — 50 000 сімвалаў Unicode. Скараціце тэкст і паспрабуйце яшчэ раз.',
    engine: 'Не ўдалося загрузіць або запусціць канвертар. Праверце злучэнне для першай загрузкі і паспрабуйце яшчэ раз. Ваш тэкст застаўся на месцы.',
    timeout: 'Пераўтварэнне заняло занадта шмат часу. Паспрабуйце карацейшы ўрывак. Ваш тэкст застаўся на месцы.',
    copied: 'Вынік скапіяваны ў буфер абмену.', copyFailed: 'Капіяванне недаступнае. Вылучыце вынік і скапіруйце яго ўручную.',
    used: 'Вынік перанесены ва ўваход. Выберыце адпаведны рэжым перад наступным пераўтварэннем.',
    languageFailed: 'Не ўдалося змяніць мову. Ваш тэкст захаваны; паспрабуйце яшчэ раз.',
    cleared: 'Уваход і вынік ачышчаны.', dictionary: 'Слоўнік', rule: 'Правіла правапісу',
    noChanges: 'Змен правапісу не выяўлена.', noHighlights: 'Гэты рэжым транслітарацыі не вяртае звестак пра змены асобных слоў.',
  },
};

// The engine's change offsets and this interface's limit count Unicode code points.
export function changeSegments(text, changes) {
  const points = Array.from(text);
  const segments = [];
  let cursor = 0;
  for (const change of changes) {
    const { start, end } = change;
    if (!Number.isInteger(start) || !Number.isInteger(end) || start < cursor || end <= start || end > points.length) continue;
    segments.push({ text: points.slice(cursor, start).join('') });
    segments.push({ text: points.slice(start, end).join(''), change });
    cursor = end;
  }
  segments.push({ text: points.slice(cursor).join('') });
  return segments;
}

export function initConverter(saved = {}) {
  const $ = id => document.getElementById(id);
  if (!$('input')) return null;
  const lang = document.documentElement.lang;
  const c = COPY[lang] || COPY.en;
  const input = $('input'), mode = $('mode'), source = $('source'), latin = $('latin-output'), output = $('output');
  let result = saved.result || null;
  let stale = saved.stale || false;
  let resultMode = saved.resultMode || 'taraskievica';
  let statusKey = saved.statusKey || 'ready';
  const engine = createEngineClient();
  let requestId = 0, busy = false;
  input.value = saved.input || '';
  mode.value = saved.mode || 'taraskievica';
  source.value = saved.source || 'narkamauka';
  latin.checked = saved.latin ?? false;
  $('show-changes').checked = saved.showChanges ?? true;

  function status(key, error = false) {
    statusKey = key;
    $('status').textContent = c[key];
    $('status').classList.toggle('error', error);
  }
  function count() {
    const length = Array.from(input.value).length;
    $('counter').textContent = `${length.toLocaleString(lang)} / ${MAX_CHARS.toLocaleString(lang)}`;
    $('counter').classList.toggle('over-limit', length > MAX_CHARS);
    input.setAttribute('aria-invalid', String(length > MAX_CHARS));
  }
  function selectedMode() {
    if (source.value === mode.value) return latin.checked ? 'lacinka-only' : 'unchanged';
    return latin.checked ? (mode.value === 'taraskievica' ? 'lacinka' : 'narkamauka-latin') : mode.value;
  }
  function labels() {
    const name = value => value === 'taraskievica' ? c.t : c.n;
    const scriptName = latin.checked ? c.l : (lang === 'be' ? 'кірыліца' : 'Cyrillic');
    $('source-name').textContent = `${name(source.value)} · ${lang === 'be' ? 'кірыліца' : 'Cyrillic'}`;
    $('target-name').textContent = `${name(mode.value)} · ${scriptName}`;
    const same = source.value === mode.value;
    $('mode-note').textContent = lang === 'be'
      ? (same ? 'Правапіс захоўваецца.' : `Правапіс: ${name(source.value)} → ${name(mode.value)}.`) + (latin.checked ? ' Вынік лацінкай: снег → snieh, сьнег → śnieh.' : 'Вынік кірыліцай. Уключыце лацінку пры патрэбе.')
      : (same ? 'Orthography stays the same.' : `Spelling: ${name(source.value)} → ${name(mode.value)}.`) + (latin.checked ? ' Latin output uses Łacinka: снег → snieh, сьнег → śnieh.' : 'Output stays in Cyrillic. Enable Latin output if needed.');
    $('output-badge').textContent = latin.checked ? 'Aa' : 'Аа';
    $('show-changes').disabled = latin.checked;
    $('show-changes').title = latin.checked ? c.noHighlights : '';
  }
  function render() {
    output.replaceChildren();
    $('change-list').replaceChildren();
    $('copy').disabled = !result?.text || stale;
    $('use-result').hidden = !result?.text;
    $('use-result').disabled = stale;
    output.classList.toggle('outdated', stale);
    $('change-details').hidden = true;
    if (!result) return;
    const changes = Array.isArray(result.changes) ? result.changes : [];
    output.lang = resultMode === 'taraskievica' || resultMode === 'narkamauka' || resultMode === 'unchanged' ? 'be' : 'be-Latn';
    if ($('show-changes').checked && !stale) {
      for (const segment of changeSegments(result.text, changes)) {
        if (!segment.change) output.append(document.createTextNode(segment.text));
        else {
          const mark = document.createElement('mark');
          mark.textContent = segment.text;
          mark.title = `${segment.change.from} → ${segment.change.to}`;
          output.append(mark);
        }
      }
    } else output.textContent = result.text;
    if (changes.length && !stale && $('show-changes').checked) {
      $('change-details').hidden = false;
      $('change-count').textContent = `(${changes.length})`;
      for (const change of changes) {
        const item = document.createElement('li');
        const words = document.createElement('span');
        words.textContent = `${change.from} → ${change.to}`;
        words.lang = 'be';
        const evidence = document.createElement('small');
        evidence.textContent = [change.stage === 'lexicon' ? c.dictionary : c.rule, change.rule, change.citation].filter(Boolean).join(' · ');
        item.append(words, evidence);
        $('change-list').append(item);
      }
    }
  }
  function stop() {
    requestId++;
    engine.cancel();
    busy = false;
    $('convert').disabled = false;
    output.setAttribute('aria-busy', 'false');
  }
  function changed() {
    stop();
    stale = Boolean(result);
    count(); labels(); render();
    status(stale ? 'outdated' : 'ready');
  }
  async function convert() {
    stop();
    const text = input.value;
    if (!text.trim()) { status('empty', true); input.focus(); return; }
    if (Array.from(text).length > MAX_CHARS) { status('limit', true); input.focus(); return; }
    const id = requestId;
    const selected = selectedMode();
    let timedOut = false;
    const timeout = setTimeout(() => { timedOut = true; engine.cancel(); }, 20000);
    busy = true;
    $('convert').disabled = true;
    output.setAttribute('aria-busy', 'true');
    status('loading');
    try {
      const body = await engine.run(text, selected);
      if (id !== requestId) return;
      result = body; stale = false; resultMode = selected;
      render();
      status('success');
      if (!Array.isArray(body.changes)) $('status').textContent += ` ${c.noHighlights}`;
      else if (!body.changes.length) $('status').textContent += ` ${!latin.checked ? c.noChanges : c.noHighlights}`;
    } catch (error) {
      if (id !== requestId) return;
      status(timedOut ? 'timeout' : 'engine', true);
    } finally {
      clearTimeout(timeout);
      if (id === requestId) {
        busy = false;
        $('convert').disabled = false;
        output.setAttribute('aria-busy', 'false');
      }
    }
  }
  input.addEventListener('input', changed);
  mode.addEventListener('change', changed);
  source.addEventListener('change', changed);
  latin.addEventListener('change', changed);
  input.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') { event.preventDefault(); convert(); }
  });
  $('convert').addEventListener('click', convert);
  $('show-changes').addEventListener('change', render);
  $('clear').addEventListener('click', () => {
    input.value = ''; result = null; stale = false;
    changed(); status('cleared'); input.focus();
  });
  $('example').addEventListener('click', () => {
    // Insert at the selection rather than silently overwrite the user's draft.
    const example = source.value === 'taraskievica' ? 'Сьнег і плян сыстэмы.' : 'Снег і план сістэмы.';
    input.setRangeText((input.value ? '\n' : '') + example, input.selectionStart, input.selectionEnd, 'end');
    changed(); input.focus();
  });
  $('copy').addEventListener('click', async () => {
    if (!result || stale) return;
    const copyId = requestId;
    try {
      await navigator.clipboard.writeText(result.text);
      if (copyId === requestId) status('copied');
    } catch {
      if (copyId === requestId) { status('copyFailed', true); output.focus(); }
    }
  });
  $('use-result').addEventListener('click', () => {
    if (!result || stale) return;
    input.value = result.text;
    changed(); status('used'); input.focus();
  });
  count(); labels(); render(); status(statusKey);
  return {
    snapshot: () => ({ input: input.value, mode: mode.value, source: source.value, latin: latin.checked, result, resultMode, stale, showChanges: $('show-changes').checked, statusKey: busy ? (stale ? 'outdated' : 'ready') : statusKey }),
    dispose: () => { stop(); engine.dispose(); },
    languageFailed: () => status('languageFailed', true),
  };
}
