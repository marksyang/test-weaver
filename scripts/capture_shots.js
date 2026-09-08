/**
 * 用無頭 Chrome（puppeteer-core，套用系統已裝的 Chrome）為 TestWeaver 抓五張 UI 截圖。
 * 由 scripts/capture-shots.sh 呼叫（起好前端後）。也可單獨跑：
 *   BASE=http://localhost:5173 OUT=shots CHROME_PATH="/Applications/Google Chrome.app/..." \
 *     node scripts/capture_shots.js
 * 產物：$OUT/{login,plan,defect,report,teams}.png（供 一頁摘要.html 的「產品畫面」）。
 */
const path = require('path');
const fs = require('fs');
const pcore = require('puppeteer-core');
const puppeteer = pcore.puppeteer || pcore;

const BASE = process.env.BASE || 'http://localhost:5173';
const OUT = process.env.OUT || 'shots';
const CHROME =
  process.env.CHROME_PATH ||
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function clickByText(page, sel, text) {
  return page.evaluate(
    (sel, text) => {
      const el = [...document.querySelectorAll(sel)].find((e) =>
        (e.textContent || '').includes(text)
      );
      if (!el) return false;
      el.click();
      return true;
    },
    sel,
    text
  );
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await puppeteer.launch({
    headless: true,
    executablePath: CHROME,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--force-color-profile=srgb'],
    defaultViewport: { width: 1440, height: 960, deviceScaleFactor: 2 },
  });
  const page = await browser.newPage();
  const log = (m) => console.log('[shot]', m);

  // 1) login page (not logged in)
  await page.goto(BASE + '/login', { waitUntil: 'networkidle0', timeout: 60000 });
  if (!page.url().includes('/login')) {
    await page.goto(BASE + '/login', { waitUntil: 'networkidle0' });
  }
  await sleep(900);
  await page.screenshot({ path: path.join(OUT, 'login.png') });
  log('login captured -> ' + page.url());

  // login via API + store token (robust vs antd form timing)
  const loginRes = await page.evaluate(async () => {
    const r = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'admin', password: 'admin123' }),
    });
    if (!r.ok) return { ok: false, status: r.status };
    const data = await r.json();
    localStorage.setItem('tw_token', data.access_token);
    return { ok: true, role: data.user && data.user.role };
  });
  if (!loginRes.ok) throw new Error('LOGIN_FAILED status=' + loginRes.status);
  log('login ok role=' + loginRes.role);
  await page.goto(BASE + '/', { waitUntil: 'networkidle0' });
  await sleep(1800);
  log('logged in -> ' + page.url());

  // 2) plan tree: switch to the 3rd-layer tab
  await page.goto(BASE + '/plan', { waitUntil: 'networkidle0' });
  await sleep(600);
  await clickByText(page, '.ant-tabs-tab-btn', '測試計畫結構');
  await page.waitForFunction(
    () => document.querySelectorAll('.ant-table-tbody tr').length >= 3,
    { timeout: 20000 }
  );
  await sleep(1400);
  await page.screenshot({ path: path.join(OUT, 'plan.png'), fullPage: true });
  log('plan captured');

  // 3) defect page (default tab = defects list)
  await page.goto(BASE + '/defect', { waitUntil: 'networkidle0' });
  await sleep(700);
  await page.waitForFunction(
    () => document.querySelectorAll('.ant-table-tbody tr').length > 1,
    { timeout: 20000 }
  );
  await sleep(500);
  await page.screenshot({ path: path.join(OUT, 'defect.png'), fullPage: true });
  log('defect captured');

  // 4) report: select the plan (real mouse — antd Select needs mousedown) -> generate -> capture
  await page.goto(BASE + '/report', { waitUntil: 'networkidle0' });
  await page.waitForFunction(
    () =>
      [...document.querySelectorAll('.ant-select')].some(
        (s) => (s.textContent || '').includes('選測試計畫')
      ),
    { timeout: 20000 }
  );
  await sleep(500);
  const selC = await page.evaluate(() => {
    const sel = [...document.querySelectorAll('.ant-select')].find(
      (s) => (s.textContent || '').includes('選測試計畫')
    );
    const b = sel.querySelector('.ant-select-selector').getBoundingClientRect();
    return { x: b.x + b.width / 2, y: b.y + b.height / 2 };
  });
  await page.mouse.click(selC.x, selC.y);
  await page.waitForFunction(
    () => !!document.querySelector('.ant-select-item-option'),
    { timeout: 15000 }
  );
  await sleep(300);
  const optC = await page.evaluate(() => {
    const o = document.querySelector('.ant-select-item-option');
    const b = o.getBoundingClientRect();
    return { x: b.x + b.width / 2, y: b.y + b.height / 2 };
  });
  await page.mouse.click(optC.x, optC.y);
  await sleep(900);
  const needComplete = await page.evaluate(() =>
    [...document.querySelectorAll('button')].some(
      (b) => b.textContent.includes('完成計畫並生成報表')
    )
  );
  if (needComplete) {
    await clickByText(page, 'button', '完成計畫並生成報表');
    log('clicked complete button');
  } else {
    log('report already present');
  }
  await page.waitForFunction(
    () => document.body.innerText.includes('AI 分析建議'),
    { timeout: 40000 }
  );
  await sleep(2400); // let ECharts animation settle
  await page.setViewport({ width: 1440, height: 1300, deviceScaleFactor: 2 });
  await sleep(700);
  await page.screenshot({ path: path.join(OUT, 'report.png') });
  log('report captured');

  // 5) teams：成員管理頁（admin 可見全部團隊 + 可管理）
  await page.goto(BASE + '/teams', { waitUntil: 'networkidle0' });
  await sleep(700);
  await page.waitForFunction(
    () => document.querySelectorAll('.ant-table-tbody tr').length >= 3,
    { timeout: 20000 }
  );
  await sleep(800);
  await page.screenshot({ path: path.join(OUT, 'teams.png'), fullPage: true });
  log('teams captured');

  await browser.close();
  console.log('ALL_DONE');
})().catch((e) => {
  console.error('CAPTURE_FAIL', e && e.stack ? e.stack : e);
  process.exit(1);
});
