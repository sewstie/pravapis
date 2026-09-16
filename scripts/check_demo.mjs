// Browser check for the demo page (public/index.html) against a running server.
//
//   python scripts/serve_local.py --port 3000
//   # in any scratch directory (Playwright is not a project dependency):
//   npm i playwright && npx playwright install chromium
//   BASE=http://127.0.0.1:3000/ SHOTS=. node /path/to/pravapis/scripts/check_demo.mjs
//
// The page is a bare form: direction toggle, input, output, Convert. This checks both
// directions, the toggle mid-session, Ctrl+Enter, empty input, the 50k limit (client and
// API), and the 390px phone layout. Writes screenshots to $SHOTS. Exits non-zero on any
// failure.
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

const SAMPLES = [
  { n: "Учора ішоў снег, і свет за акном здаваўся зусім іншым.",
    t: "Учора ішоў сьнег, і сьвет за акном здаваўся зусім іншым." },
  { n: "Сістэма плануе адкрыць новую лабараторыю ў цэнтры Еўропы.",
    t: "Сыстэма плянуе адкрыць новую лябараторыю ў цэнтры Эўропы." },
  { n: "Не быў без мяне на свяце ў Мінску — не магу забыць гэты вечар.",
    t: "Ня быў безь мяне на сьвяце ў Менску — не магу забыць гэты вечар." },
];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const consoleErrors = [];
page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });
page.on("pageerror", (e) => consoleErrors.push(String(e)));

const outputText = () => page.inputValue("#output");
const waitConvert = (action) =>
  Promise.all([page.waitForResponse((r) => r.url().endsWith("/api/convert")), action()]).then(
    ([resp]) => page.waitForTimeout(50).then(() => resp)
  );
const setDirection = async (dir) => {
  const id = dir === "t" ? "dir-t" : "dir-n";
  if (!(await page.isChecked(`#${id}`))) await page.click(`label[for="${id}"]`);
};

// 1. initial load: empty form, nothing requested
let requested = false;
const onLoad = (r) => { if (r.url().endsWith("/api/convert")) requested = true; };
page.on("request", onLoad);
await page.goto(BASE);
await page.waitForTimeout(300);
page.off("request", onLoad);
check("page loads empty and converts nothing",
  !requested && (await page.inputValue("#input")) === "" && (await outputText()) === "");
check("N→T is the default direction", await page.isChecked("#dir-t"));

// 2. both directions
for (const [dirKey, from, to, name] of [["t", "n", "t", "N→T"], ["n", "t", "n", "T→N"]]) {
  await setDirection(dirKey);
  for (const s of SAMPLES) {
    await page.fill("#input", s[from]);
    await waitConvert(() => page.click("#go"));
    const out = await outputText();
    check(`${name}: ${s[from].slice(0, 24)}…`, out === s[to], out);
  }
}

// 3. direction toggle mid-session continues from the last output
await setDirection("t");
await page.fill("#input", SAMPLES[1].n);
await waitConvert(() => page.click("#go"));
await waitConvert(() => page.click('label[for="dir-n"]'));
check(
  "toggle after conversion continues from last output",
  (await page.inputValue("#input")) === SAMPLES[1].t && (await outputText()) === SAMPLES[1].n,
  `input=${await page.inputValue("#input")} | out=${await outputText()}`
);

// 4. Ctrl+Enter and the button
await setDirection("t");
await page.fill("#input", "снег і свет");
await waitConvert(() => page.press("#input", "Control+Enter"));
check("Ctrl+Enter converts", (await outputText()) === "сьнег і сьвет", await outputText());
await page.fill("#input", "план");
await waitConvert(() => page.click("#go"));
check("Convert button converts", (await outputText()) === "плян", await outputText());

// 5. the output pane is read-only
check("output is read-only", (await page.getAttribute("#output", "readonly")) !== null);

// 6. empty input
await page.fill("#input", "   ");
requested = false;
const onEmpty = (r) => { if (r.url().endsWith("/api/convert")) requested = true; };
page.on("request", onEmpty);
await page.click("#go");
await page.waitForTimeout(300);
page.off("request", onEmpty);
check("empty input: no request, output cleared",
  !requested && (await outputText()) === "" && (await page.textContent("#error")) === "");

// 7. over 50k characters: the page refuses before uploading; the API answers a clean 413
for (const n of [12_000, 80_000]) {  // 60k and 400k characters
  await page.fill("#input", "снег ".repeat(n));
  let sent = false;
  const spy = (r) => { if (r.url().endsWith("/api/convert")) sent = true; };
  page.on("request", spy);
  await page.click("#go");
  await page.waitForTimeout(300);
  page.off("request", spy);
  const msg = await page.textContent("#error");
  check(`${n * 5} chars → message, no upload`, !sent && /максімум 50000/.test(msg), msg);
}
for (const n of [12_000, 80_000]) {
  const res = await page.evaluate(async (n) => {
    try {
      const r = await fetch("/api/convert", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: "снег ".repeat(n) }),
      });
      return { status: r.status, body: await r.text() };
    } catch (e) { return { status: 0, body: String(e) }; }
  }, n);
  check(`API direct: ${n * 5} chars → clean JSON 413`,
    res.status === 413 && res.body.startsWith("{") && !/Traceback/.test(res.body),
    `${res.status} ${res.body.slice(0, 90)}`);
}

// 8. desktop screenshot
await page.fill("#input", SAMPLES[0].n);
await waitConvert(() => page.click("#go"));
await page.screenshot({ path: `${SHOTS}/desktop.png` });

// 9. narrow viewport
await page.setViewportSize({ width: 390, height: 844 });
await page.fill("#input", SAMPLES[2].n);
await setDirection("t");
await waitConvert(() => page.click("#go"));
const layout = await page.evaluate(() => {
  const panes = [...document.querySelectorAll("textarea")].map((p) => p.getBoundingClientRect());
  const seg = document.querySelector(".seg").getBoundingClientRect();
  return {
    scrollW: document.documentElement.scrollWidth,
    clientW: document.documentElement.clientWidth,
    stacked: panes[1].top >= panes[0].bottom - 1,
    segRight: seg.right,
  };
});
check("390px: no horizontal scroll", layout.scrollW <= layout.clientW, JSON.stringify(layout));
check("390px: panes stacked", layout.stacked);
check("390px: direction toggle fits", layout.segRight <= layout.clientW,
  `seg right ${layout.segRight} / ${layout.clientW}`);
// tap targets: the two direction halves and the Convert button are at least 32px tall
const taps = await page.evaluate(() =>
  [...document.querySelectorAll(".seg label, #go")].map((e) => Math.round(e.getBoundingClientRect().height))
);
check("390px: tap targets ≥ 32px", taps.every((h) => h >= 32), taps.join(","));
await waitConvert(() => page.click('label[for="dir-n"]'));
check("390px: direction toggle works", (await outputText()) === SAMPLES[2].n, await outputText());
await setDirection("t");
await page.waitForTimeout(200);
await page.screenshot({ path: `${SHOTS}/mobile-390.png`, fullPage: true });

// The deliberate direct 413 requests above log "Failed to load resource … 413"; anything else is a bug.
const unexpected = consoleErrors.filter((e) => !/status of 413/.test(e));
check("no unexpected console errors", unexpected.length === 0, unexpected.join(" | "));
await browser.close();
const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} passed`);
process.exit(failed.length ? 1 : 0);
