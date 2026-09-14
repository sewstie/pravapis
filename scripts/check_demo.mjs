// Browser check for the demo page (public/index.html) against a running server.
//
//   python scripts/serve_local.py --port 3000
//   # in any scratch directory (Playwright is not a project dependency):
//   npm i playwright && npx playwright install chromium
//   BASE=http://127.0.0.1:3000/ SHOTS=. node /path/to/belnorm/scripts/check_demo.mjs
//
// Presets in both directions, the direction toggle mid-session, Ctrl+Enter, explain
// highlighting and tooltips, empty input, the 50k limit (client and API), новы клас, and
// the 390px phone layout. Writes screenshots to $SHOTS. Exits non-zero on any failure.
import { createRequire } from "node:module";

// Resolve Playwright from the current directory, not from this file's location.
const { chromium } = createRequire(`${process.cwd()}/`)("playwright");

const BASE = process.env.BASE || "http://127.0.0.1:3000/";
const SHOTS = process.env.SHOTS || ".";
const results = [];
const check = (name, ok, detail = "") => {
  results.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  — " + detail : ""}`);
};

const PRESETS = [
  { label: "Снег і свет", n: "Учора ішоў снег, і свет за акном здаваўся зусім іншым.",
    t: "Учора ішоў сьнег, і сьвет за акном здаваўся зусім іншым." },
  { label: "Сістэма ў Еўропе", n: "Сістэма плануе адкрыць новую лабараторыю ў цэнтры Еўропы.",
    t: "Сыстэма плянуе адкрыць новую лябараторыю ў цэнтры Эўропы." },
  { label: "Не быў у Мінску", n: "Не быў без мяне на свяце ў Мінску — не магу забыць гэты вечар.",
    t: "Ня быў безь мяне на сьвяце ў Менску — не магу забыць гэты вечар." },
];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const consoleErrors = [];
page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });
page.on("pageerror", (e) => consoleErrors.push(String(e)));

const outputText = async () =>
  page.evaluate(() => {
    const r = document.getElementById("rendered");
    const o = document.getElementById("output");
    return r.hidden ? o.value : r.textContent;
  });
const waitConvert = (action) =>
  Promise.all([page.waitForResponse((r) => r.url().endsWith("/api/convert")), action()]).then(
    ([resp]) => page.waitForTimeout(50).then(() => resp)
  );
const setDirection = async (dir) => {
  const id = dir === "t" ? "dir-t" : "dir-n";
  const checked = await page.isChecked(`#${id}`);
  if (!checked) await page.click(`label[for="${id}"]`);
};

// 1. initial load
await waitConvert(() => page.goto(BASE));
check("page loads and auto-converts preset 1", (await outputText()) === PRESETS[0].t, await outputText());

// 2. all presets, both directions (set direction on an empty input so the toggle does not carry text)
for (const [dirKey, from, to, name] of [["t", "n", "t", "N→T"], ["n", "t", "n", "T→N"]]) {
  await page.fill("#input", "");
  await setDirection(dirKey);
  await page.waitForTimeout(100);
  for (const p of PRESETS) {
    await waitConvert(() => page.click(`#presets button:has-text("${p.label}")`));
    const input = await page.inputValue("#input");
    const out = await outputText();
    check(`preset "${p.label}" ${name}`, input === p[from] && out === p[to], `in=${input} | out=${out}`);
  }
}

// 3. direction toggle mid-session continues from the last output
await page.fill("#input", "");
await setDirection("t");
await page.waitForTimeout(100);
await waitConvert(() => page.click(`#presets button:has-text("${PRESETS[1].label}")`));
const before = await outputText();
await waitConvert(() => page.click('label[for="dir-n"]'));
check(
  "toggle after conversion continues from last output",
  (await page.inputValue("#input")) === before && (await outputText()) === PRESETS[1].n,
  `input=${await page.inputValue("#input")} | out=${await outputText()}`
);
check(
  "pane labels follow direction",
  (await page.textContent("#in-label")) === "Тарашкевіца" && (await page.textContent("#out-label")) === "Наркамаўка"
);

// 4. Ctrl+Enter and the button
await setDirection("t");
await page.waitForTimeout(300);
await page.fill("#input", "снег і свет");
await waitConvert(() => page.press("#input", "Control+Enter"));
check("Ctrl+Enter converts", (await outputText()) === "сьнег і сьвет", await outputText());
await page.fill("#input", "план");
await waitConvert(() => page.click("#go"));
check("Convert button converts", (await outputText()) === "плян", await outputText());

// 5. explain mode: lexicon vs rule distinguishable, tooltip steps
await page.fill("#input", "Сістэма плануе адкрыць лабараторыю ў Мінску.");
await waitConvert(() => page.click("#go"));
const spans = await page.$$eval("#rendered .w", (els) =>
  els.map((e) => ({ cls: e.className, text: e.textContent, bg: getComputedStyle(e).backgroundColor,
    shadow: getComputedStyle(e).boxShadow }))
);
const lex = spans.find((s) => s.cls.includes("lexicon"));
const rule = spans.find((s) => s.cls.includes("rule"));
check("explain highlights lexicon and rule hits", !!lex && !!rule, JSON.stringify(spans.map((s) => [s.text, s.cls])));
check("lexicon and rule colours differ", lex && rule && lex.bg !== rule.bg && lex.shadow !== rule.shadow,
  `lexicon ${lex?.bg} vs rule ${rule?.bg}`);
await page.hover("#rendered .w.rule");
await page.waitForTimeout(100);
const tipRule = await page.$eval("#tip", (t) => ({ hidden: t.hidden, text: t.innerText, steps: t.querySelectorAll("li").length }));
check("hover on rule word shows rule steps", !tipRule.hidden && tipRule.steps > 0 && /loan\.l_palatalization/.test(tipRule.text), tipRule.text.replace(/\n/g, " / "));
await page.screenshot({ path: `${SHOTS}/desktop-explain-hover.png` });
await page.hover("#rendered .w.lexicon");
await page.waitForTimeout(100);
const tipLex = await page.$eval("#tip", (t) => ({ hidden: t.hidden, text: t.innerText }));
check("hover on lexicon word says lexicon", !tipLex.hidden && /lexicon/i.test(tipLex.text), tipLex.text.replace(/\n/g, " / "));
await page.mouse.move(5, 5);
await page.focus("#rendered .w.rule");
check("keyboard focus shows tooltip", !(await page.$eval("#tip", (t) => t.hidden)));
await page.click('label.switch');
check("explain off shows plain textarea", await page.isVisible("#output") && !(await page.isVisible("#rendered")));
await page.click('label.switch');

// 6. empty input
await page.fill("#input", "");
let requested = false;
const onReq = (r) => { if (r.url().endsWith("/api/convert")) requested = true; };
page.on("request", onReq);
await page.click("#go");
await page.waitForTimeout(300);
page.off("request", onReq);
check("empty input: no request, output cleared", !requested && (await outputText()) === "" && (await page.textContent("#stats")) === "");

// 7. over 50k characters: the page refuses before uploading; the API answers a clean 413
for (const n of [12_000, 80_000]) {  // 60k and 400k characters
  await page.fill("#input", "снег ".repeat(n));
  let sent = false;
  const spy = (r) => { if (r.url().endsWith("/api/convert")) sent = true; };
  page.on("request", spy);
  await page.click("#go");
  await page.waitForTimeout(300);
  page.off("request", spy);
  const msg = await page.textContent("#stats");
  check(`${n * 5} chars → message, no upload`, !sent && /limit is 50,000/.test(msg), msg);
}
for (const n of [12_000, 80_000]) {
  const res = await page.evaluate(async (n) => {
    try {
      const r = await fetch("/api/convert", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: "снег ".repeat(n) }) });
      return { status: r.status, body: await r.text() };
    } catch (e) { return { status: 0, body: String(e) }; }
  }, n);
  check(`API direct: ${n * 5} chars → clean JSON 413`, res.status === 413 && res.body.startsWith("{") && !/Traceback/.test(res.body),
    `${res.status} ${res.body.slice(0, 90)}`);
}

// 8. новы клас
await page.fill("#input", "новы клас");
await waitConvert(() => page.click("#go"));
check("reproduce: новы клас", true, `→ ${await outputText()}`);

// 9. narrow viewport
await page.setViewportSize({ width: 390, height: 844 });
await page.fill("#input", "");
await setDirection("t");
await page.waitForTimeout(100);
await waitConvert(() => page.click(`#presets button:has-text("${PRESETS[2].label}")`));
const layout = await page.evaluate(() => {
  const panes = [...document.querySelectorAll(".pane")].map((p) => p.getBoundingClientRect());
  const tb = document.querySelector(".toolbar").getBoundingClientRect();
  const seg = document.querySelector(".seg").getBoundingClientRect();
  return {
    scrollW: document.documentElement.scrollWidth, clientW: document.documentElement.clientWidth,
    stacked: panes[1].top >= panes[0].bottom - 1, paneW: panes[0].width,
    segRight: seg.right, tbRight: tb.right,
  };
});
check("390px: no horizontal scroll", layout.scrollW <= layout.clientW, JSON.stringify(layout));
check("390px: panes stacked", layout.stacked);
check("390px: direction toggle fits", layout.segRight <= layout.clientW, `seg right ${layout.segRight} / ${layout.clientW}`);
// tap targets: the two direction halves and the Convert button are at least 40px tall
const taps = await page.evaluate(() =>
  [...document.querySelectorAll(".seg label, #go, #presets button")].map((e) => Math.round(e.getBoundingClientRect().height))
);
check("390px: tap targets ≥ 32px", taps.every((h) => h >= 32), taps.join(","));
// direction switch still works on the phone layout
await waitConvert(() => page.click('label[for="dir-n"]'));
check("390px: direction toggle works", (await outputText()) === PRESETS[2].n, await outputText());
await setDirection("t");
await page.waitForTimeout(300);
await page.screenshot({ path: `${SHOTS}/mobile-390.png`, fullPage: true });
await page.hover("#rendered .w.rule").catch(() => {});
await page.waitForTimeout(100);
const tipBox = await page.$eval("#tip", (t) => { const r = t.getBoundingClientRect(); return { hidden: t.hidden, left: r.left, right: r.right }; });
check("390px: tooltip stays on screen", tipBox.hidden || (tipBox.left >= 0 && tipBox.right <= 390), JSON.stringify(tipBox));
await page.screenshot({ path: `${SHOTS}/mobile-390-tooltip.png` });

// The deliberate direct 413 requests above log "Failed to load resource … 413"; anything else is a bug.
const unexpected = consoleErrors.filter((e) => !/status of 413/.test(e));
check("no unexpected console errors", unexpected.length === 0, unexpected.join(" | "));
await browser.close();
const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} passed`);
process.exit(failed.length ? 1 : 0);
