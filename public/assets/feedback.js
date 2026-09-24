// Builds feedback drafts for users to review and submit on GitHub. Copies drafts locally without sending their contents or placing them in URLs.
const COPY = {
  en: {
    feedbackTitle: 'Share feedback',
    feedbackIntro: 'Found a bug, an incorrect spelling, or something we could improve? Send us a report.',
    categories: { bug: 'A bug', word: 'An incorrect word or conversion', proposal: 'A proposal to improve Pravapis' },
    wordRequired: 'Enter the spelling you want reviewed in both fields.',
    copied: 'Your draft is copied. Use its first line as the title, paste the rest into the description, then review and submit it yourself.',
    copyFailed: 'GitHub is open. Clipboard access failed; select and copy your draft below, then paste and review it before submitting.',
    popupFailed: 'Your draft is copied, but the browser blocked the GitHub tab. Open GitHub Issues and paste your report there.',
    clipboard: 'Report draft to copy',
    title: 'Pravapis website feedback',
    kind: 'Feedback type', summary: 'Short summary', summaryHint: 'For example: “The word снег was not changed”',
    original: 'Word or spelling you entered', suggested: 'Suggested spelling',
    details: 'What happened, or what would you improve?',
    detailsHint: 'Add context that would help us understand or reproduce this.',
    privacy: 'Reports are copied to your clipboard and opened as a GitHub issue draft. Nothing is sent automatically. GitHub issues are public when you submit them; remove personal or sensitive information.',
    submit: 'Prepare report on GitHub',
    reportType: 'Type', page: 'Page', word: 'Word entered', suggestedWord: 'Suggested spelling', description: 'Details',
  },
  be: {
    feedbackTitle: 'Пакінуць водгук',
    feedbackIntro: 'Знайшлі памылку, недакладнае напісанне або маеце прапанову? Напішыце нам.',
    categories: { bug: 'Памылка ў праграме', word: 'Памылковае слова ці пераўтварэнне', proposal: 'Прапанова палепшыць Pravapis' },
    wordRequired: 'Для праверкі ўвядзіце абодва варыянты напісання.',
    copied: 'Чарнавік скапіяваны. Выкарыстайце першы радок як тэму, астатні тэкст устаўце ў апісанне, праверце і адпраўце самастойна.',
    copyFailed: 'GitHub адкрыты. Не ўдалося скапіраваць тэкст; вылучыце чарнавік ніжэй, скапіруйце, устаўце і праверце яго перад адпраўкай.',
    popupFailed: 'Чарнавік скапіяваны, але браўзер не адкрыў укладку GitHub. Адкрыйце GitHub Issues і ўстаўце паведамленне.',
    clipboard: 'Чарнавік паведамлення',
    title: 'Водгук пра сайт Pravapis',
    kind: 'Тып паведамлення', summary: 'Кароткая тэма', summaryHint: 'Напрыклад: «Слова снег не пераўтварылася»',
    original: 'Уведзенае слова ці правапіс', suggested: 'Прапанаваны варыянт',
    details: 'Што адбылося або што варта палепшыць?',
    detailsHint: 'Дадайце звесткі, якія дапамогуць разабрацца або паўтарыць праблему.',
    privacy: 'Тэкст паведамлення капіюецца ў буфер абмену, а на GitHub адкрываецца чарнавік. Нічога не адпраўляецца аўтаматычна. Адпраўленыя паведамленні на GitHub будуць публічнымі; не ўключайце асабістыя ці адчувальныя звесткі.',
    submit: 'Падрыхтаваць паведамленне на GitHub',
    reportType: 'Тып паведамлення', page: 'Старонка', word: 'Уведзенае слова', suggestedWord: 'Прапанаваны варыянт', description: 'Падрабязнасці',
  },
};

export function mountFeedback() {
  if (document.getElementById('feedback-form')) return;
  const c = COPY[document.documentElement.lang] || COPY.en;
  const main = document.getElementById('main');
  if (!main) return;
  const section = document.createElement('section');
  section.id = 'feedback';
  section.className = 'section feedback-section';
  const heading = document.createElement('h2');
  heading.textContent = c.feedbackTitle;
  const intro = document.createElement('p');
  intro.className = 'feedback-intro';
  intro.textContent = c.feedbackIntro;
  section.append(heading, intro);

  const form = document.createElement('form');
  form.id = 'feedback-form';
  const addField = (labelText, id, control, hintText = '') => {
    const wrap = document.createElement('div');
    wrap.className = 'feedback-field';
    const label = document.createElement('label');
    label.htmlFor = id;
    label.textContent = labelText;
    control.id = id;
    wrap.append(label, control);
    if (hintText) {
      const hint = document.createElement('small');
      hint.id = `${id}-hint`;
      hint.className = 'feedback-hint';
      hint.textContent = hintText;
      control.setAttribute('aria-describedby', hint.id);
      wrap.append(hint);
    }
    form.append(wrap);
  };

  const kind = document.createElement('select');
  kind.name = 'kind';
  kind.required = true;
  for (const [value, label] of Object.entries(c.categories)) {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = label;
    kind.append(option);
  }
  addField(c.kind, 'feedback-kind', kind);
  const summary = document.createElement('input');
  summary.name = 'summary';
  summary.required = true;
  summary.maxLength = 120;
  summary.autocomplete = 'off';
  addField(c.summary, 'feedback-summary', summary, c.summaryHint);

  const words = document.createElement('fieldset');
  words.id = 'feedback-words';
  words.className = 'feedback-words';
  words.hidden = true;
  const legend = document.createElement('legend');
  legend.textContent = c.wordRequired;
  words.append(legend);
  const originalField = document.createElement('div');
  originalField.className = 'feedback-field';
  const originalLabel = document.createElement('label');
  originalLabel.htmlFor = 'feedback-original';
  originalLabel.textContent = c.original;
  const original = document.createElement('input');
  original.type = 'text'; original.name = 'original'; original.autocomplete = 'off'; original.lang = 'be'; original.spellcheck = false;
  original.id = 'feedback-original';
  originalField.append(originalLabel, original);
  const suggestionField = document.createElement('div');
  suggestionField.className = 'feedback-field';
  const suggestionLabel = document.createElement('label');
  suggestionLabel.htmlFor = 'feedback-suggestion';
  suggestionLabel.textContent = c.suggested;
  const suggestion = document.createElement('input');
  suggestion.type = 'text'; suggestion.name = 'suggestion'; suggestion.autocomplete = 'off'; suggestion.lang = 'be'; suggestion.spellcheck = false;
  suggestion.id = 'feedback-suggestion';
  suggestionField.append(suggestionLabel, suggestion);
  words.append(originalField, suggestionField);
  form.append(words);

  const details = document.createElement('textarea');
  details.name = 'details'; details.rows = 5; details.required = true;
  addField(c.details, 'feedback-details', details, c.detailsHint);
  const privacy = document.createElement('p');
  privacy.className = 'feedback-privacy';
  privacy.textContent = c.privacy;
  form.append(privacy);
  const submit = document.createElement('button');
  submit.type = 'submit'; submit.className = 'primary'; submit.textContent = c.submit;
  form.append(submit);
  const message = document.createElement('p');
  message.id = 'feedback-status'; message.className = 'status'; message.setAttribute('role', 'status');
  message.setAttribute('aria-live', 'polite');
  form.append(message);
  const draftWrap = document.createElement('div');
  draftWrap.className = 'feedback-field';
  const draftLabel = document.createElement('label');
  draftLabel.htmlFor = 'feedback-draft'; draftLabel.textContent = c.clipboard;
  const draft = document.createElement('textarea');
  draft.id = 'feedback-draft'; draft.readOnly = true; draft.rows = 7; draft.hidden = true;
  draftWrap.append(draftLabel, draft);
  form.append(draftWrap);
  section.append(form);
  main.append(section);

  const footer = document.querySelector('.footer');
  const footerLinks = document.querySelector('.footer-links');
  document.querySelector('.footer-left > span')?.remove();
  document.querySelectorAll('.footer-links a[href*="/data/LICENSE"]').forEach(link => link.remove());
  if (footerLinks) {
    const link = document.createElement('a');
    link.href = '#feedback'; link.textContent = c.feedbackTitle;
    footerLinks.prepend(link);
  }
}

mountFeedback();

const form = document.getElementById('feedback-form');
if (form) {
  const $ = id => document.getElementById(id);
  const kind = $('feedback-kind');
  const words = $('feedback-words');
  const original = $('feedback-original');
  const suggestion = $('feedback-suggestion');
  const draft = $('feedback-draft');
  const message = $('feedback-status');

  kind.addEventListener('change', () => {
    const needsWords = kind.value === 'word';
    words.hidden = !needsWords;
    original.required = needsWords;
    suggestion.required = needsWords;
  });

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const c = COPY[document.documentElement.lang] || COPY.en;
    const issueType = c.categories[kind.value];
    const title = `[${issueType}] ${$('feedback-summary').value.trim()}`;
    const path = `${location.origin}${location.pathname}`;
    const fields = [
      `${c.reportType}: ${issueType}`,
      `${c.page}: ${path}`,
      kind.value === 'word' ? `${c.word}: ${original.value.trim()}\n${c.suggestedWord}: ${suggestion.value.trim()}` : '',
      `${c.description}:\n${$('feedback-details').value.trim()}`,
    ].filter(Boolean);
    const report = `${title}\n\n${fields.join('\n\n')}`;
    const issue = window.open('https://github.com/sewstie/pravapis/issues/new', '_blank');
    if (issue) issue.opener = null;
    draft.value = report;
    draft.hidden = false;
    try {
      await navigator.clipboard.writeText(report);
      message.textContent = c.copied;
    } catch {
      message.textContent = c.copyFailed;
      draft.focus();
      draft.select();
    }
    if (!issue) message.textContent = c.popupFailed;
  });
}
