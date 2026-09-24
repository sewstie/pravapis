// Generates the website social-sharing image with Playwright. Saves the image to public/assets/social.png.
import { chromium } from '../website/node_modules/playwright/index.mjs';
import { fileURLToPath } from 'node:url';

const browser = await chromium.launch({
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || undefined,
});
try {
  const page = await browser.newPage({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 1 });
  await page.setContent(`<!doctype html><html lang="be"><meta charset="utf-8"><style>
*{box-sizing:border-box}body{margin:0;width:1200px;height:630px;background:#f7f6f2;color:#20231f;font-family:'Segoe UI','Noto Sans',Arial,sans-serif;display:flex;align-items:center;justify-content:center}
main{width:1020px;height:500px;border:1px solid #d9ddd3;border-radius:22px;background:#faf9f6;padding:72px 82px;position:relative;overflow:hidden}
.wordmark{font-weight:750;font-size:34px;letter-spacing:-1.7px;display:flex;align-items:center;gap:16px}.symbol{font-size:38px;color:#a1271f;letter-spacing:-7px;margin-right:8px}
.label{margin-top:49px;font-size:17px;color:#60655d;letter-spacing:3px;text-transform:uppercase;font-weight:600}
.example{font-family:Georgia,'Times New Roman',serif;font-size:79px;letter-spacing:-2px;margin-top:12px}.arrow{color:#a1271f;font-family:'Segoe UI',sans-serif;font-size:56px;padding:0 20px}
.bottom{position:absolute;left:83px;right:83px;bottom:48px;display:flex;align-items:center;justify-content:space-between;border-top:1px solid #d9ddd3;padding-top:18px;color:#60655d;font-size:14px}
.accent{position:absolute;width:210px;height:210px;border:1px solid #e8e5de;border-radius:50%;right:-59px;top:-100px}.accent:after{content:'';position:absolute;inset:21px;border:1px solid #ece9e2;border-radius:50%}
</style><main><div class="accent"></div><div class="wordmark"><span class="symbol">BY</span>pravapis</div><div class="label">Беларускі правапіс — ваш выбар</div><div class="example">Снег <span class="arrow">→</span><span style="color:#a1271f">Сьнег</span></div><div class="bottom"><span>наркамаўка &nbsp;↔&nbsp; тарашкевіца</span><span>pravapis.vercel.app</span></div></main></html>`);
  await page.screenshot({ path: fileURLToPath(new URL('../public/assets/social.png', import.meta.url)), type: 'png' });
} finally { await browser.close(); }
