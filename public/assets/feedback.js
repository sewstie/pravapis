// Sends website feedback to a private same-origin endpoint backed by Google Sheets.
const COPY = {
  en: {
    feedbackTitle: 'Share feedback',
    feedbackIntro: 'Found a bug, an incorrect spelling, or something we could improve? Send us a report.',
    categories: { bug: 'A bug', word: 'An incorrect word or conversion', proposal: 'A proposal to improve Pravapis' },
    wordRequired: 'Enter the spelling you want reviewed in both fields.',
    sent: 'Thank you. Your report has been sent privately.',
    failed: 'Your report could not be sent. Please try again later; your text is still here.',
    sending: 'Sending…',
    kind: 'Feedback type', summary: 'Short summary', summaryHint: 'For example: “The word снег was not changed”',
    original: 'Word or spelling you entered', suggested: 'Suggested spelling',
    details: 'What happened, or what would you improve?',
    detailsHint: 'Add context that would help us understand or reproduce this.',
    privacy: 'Submitting sends this report and the page path to a private Google Sheet. Your converter text is not included unless you type it here. Do not include personal or sensitive information.',
    submit: 'Send feedback',
  },
  be: {
    feedbackTitle: 'Пакінуць водгук',
    feedbackIntro: 'Знайшлі памылку, недакладнае напісанне або маеце прапанову? Напішыце нам.',
    categories: { bug: 'Памылка ў праграме', word: 'Памылковае слова ці пераўтварэнне', proposal: 'Прапанова палепшыць Pravapis' },
    wordRequired: 'Для праверкі ўвядзіце абодва варыянты напісання.',
    sent: 'Дзякуй. Паведамленне адпраўлена прыватна.',
    failed: 'Не ўдалося адправіць паведамленне. Паспрабуйце пазней; ваш тэкст застаўся ў форме.',
    sending: 'Адпраўляем…',
    kind: 'Тып паведамлення', summary: 'Кароткая тэма', summaryHint: 'Напрыклад: «Слова снег не пераўтварылася»',
    original: 'Уведзенае слова ці правапіс', suggested: 'Прапанаваны варыянт',
    details: 'Што адбылося або што варта палепшыць?',
    detailsHint: 'Дадайце звесткі, якія дапамогуць разабрацца або паўтарыць праблему.',
    privacy: 'Пасля адпраўкі паведамленне і шлях старонкі трапяць у прыватную Google-табліцу. Тэкст з канвертара не перадаецца, калі вы самі не ўвядзеце яго тут. Не ўключайце асабістыя або адчувальныя звесткі.',
    submit: 'Адправіць водгук',
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
  original.type = 'text'; original.name = 'original'; original.autocomplete = 'off'; original.lang = 'be'; original.spellcheck = false; original.maxLength = 120;
  original.id = 'feedback-original';
  originalField.append(originalLabel, original);
  const suggestionField = document.createElement('div');
  suggestionField.className = 'feedback-field';
  const suggestionLabel = document.createElement('label');
  suggestionLabel.htmlFor = 'feedback-suggestion';
  suggestionLabel.textContent = c.suggested;
  const suggestion = document.createElement('input');
  suggestion.type = 'text'; suggestion.name = 'suggestion'; suggestion.autocomplete = 'off'; suggestion.lang = 'be'; suggestion.spellcheck = false; suggestion.maxLength = 120;
  suggestion.id = 'feedback-suggestion';
  suggestionField.append(suggestionLabel, suggestion);
  words.append(originalField, suggestionField);
  form.append(words);

  const details = document.createElement('textarea');
  details.name = 'details'; details.rows = 5; details.required = true; details.maxLength = 3000;
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
  section.append(form);
  main.append(section);

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
  const message = $('feedback-status');
  const submit = form.querySelector('[type=submit]');

  kind.addEventListener('change', () => {
    const needsWords = kind.value === 'word';
    words.hidden = !needsWords;
    original.required = needsWords;
    suggestion.required = needsWords;
  });

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const c = COPY[document.documentElement.lang] || COPY.en;
    if (submit.disabled) return;
    const report = {
      kind: kind.value,
      summary: $('feedback-summary').value.trim(),
      original: kind.value === 'word' ? original.value.trim() : '',
      suggestion: kind.value === 'word' ? suggestion.value.trim() : '',
      details: $('feedback-details').value.trim(),
      page: location.pathname,
    };
    submit.disabled = true;
    submit.textContent = c.sending;
    message.textContent = '';
    try {
      const response = await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(report),
      });
      if (!response.ok) throw new Error(`Feedback delivery failed (${response.status})`);
      message.textContent = c.sent;
      form.reset();
      words.hidden = true;
      original.required = false;
      suggestion.required = false;
    } catch {
      message.textContent = c.failed;
    } finally {
      submit.disabled = false;
      submit.textContent = c.submit;
    }
  });
}
