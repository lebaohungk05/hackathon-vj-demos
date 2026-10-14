// Runs one of the capture scripts against the ALREADY-RUNNING Chrome
// (started separately with --remote-debugging-port=9222).
//
// The browser is never launched or closed here, and this script never touches
// the sign-in flow: if the session is not already signed in to Fabric it exits
// and asks the human to sign in.
//
//   node driver.js <script.js> [output.json]

const fs = require('fs');
const path = require('path');

// Tim playwright: uu tien bien moi truong, roi den ban cai trong may.
// Go cung mot duong dan npx thi may khac khong chay duoc.
const PW_DIR = process.env.FRC_PLAYWRIGHT || (() => {
  const cands = [];
  try { cands.push(require.resolve('playwright')); } catch (e) {}
  const os = require('os'), path = require('path'), fs = require('fs');
  const npx = path.join(os.homedir(), 'AppData/Local/npm-cache/_npx');
  try {
    for (const d of fs.readdirSync(npx)) {
      const c = path.join(npx, d, 'node_modules/playwright');
      if (fs.existsSync(c)) cands.push(c);
    }
  } catch (e) {}
  if (!cands.length) {
    console.error('KHONG_TIM_THAY_PLAYWRIGHT: cai bang "npm i -g playwright" ' +
                  'hoac dat bien moi truong FRC_PLAYWRIGHT tro toi thu muc playwright.');
    process.exit(5);
  }
  return cands[0];
})();
const CDP = 'http://127.0.0.1:9222';
// The sign-in probe just needs ANY workspace list to render - it does not have to be one this
// run's inventory touches. Hardcoding one project's workspace id here meant every other project
// using this skill got a false NOT_SIGNED_IN (the probe 404s into /groups/me/list, which never
// renders fluentListCell). FRC_PROBE_WORKSPACE lets each project point this at a workspace it
// actually has, with the original id kept only as a last-resort default.
const PROBE_WS = process.env.FRC_PROBE_WORKSPACE || 'f54ae67e-24ad-4468-baf6-5a56f3345b3d';
const FABRIC = `https://app.fabric.microsoft.com/groups/${PROBE_WS}/list?experience=fabric-developer`;

const { chromium } = require(PW_DIR);

(async () => {
  const scriptPath = process.argv[2];
  const outPath = process.argv[3];
  if (!scriptPath) {
    console.error('usage: node driver.js <script.js> [output.json]');
    process.exit(2);
  }

  let browser;
  try {
    browser = await chromium.connectOverCDP(CDP);
  } catch (e) {
    console.error('NO_BROWSER: cannot reach Chrome on ' + CDP + ' — is it still running?');
    process.exit(3);
  }

  const ctx = browser.contexts()[0];
  const page = ctx.pages()[0] || (await ctx.newPage());

  // Gate: require an already-authenticated Fabric session. Never drive the login.
  const probe = await ctx.newPage();
  let signedIn = false;
  try {
    await probe.goto(FABRIC, { waitUntil: 'domcontentloaded', timeout: 90000 });
    // Cho DUNG DAU HIEU thay vi ngu mot khoang co dinh. Fabric co the mat hon
    // 6 giay de dung xong danh sach workspace, khi do phien dang nhap that van
    // bi bao nham la chua dang nhap.
    try {
      await probe.waitForSelector('[data-testid="fluentListCell.name"]', { timeout: 45000 });
    } catch (e) { /* de doan kiem ben duoi ket luan */ }
    signedIn = await probe.evaluate(
      () => /app\.fabric\.microsoft\.com/.test(location.host) &&
            !!document.querySelector('[data-testid="fluentListCell.name"]')
    );
    if (!signedIn) {
      const onLogin = await probe.evaluate(
        () => !!document.querySelector('input[type="email"], #i0116') ||
              /login\.microsoftonline\.com/.test(location.host)).catch(() => false);
      if (!onLogin)
        console.error('LUU_Y: trinh duyet dang o Fabric nhung danh sach workspace chua dung xong ' +
                      'sau 45 giay. Kiem tra capacity da bat chua.');
    }
  } catch (e) { /* leave signedIn false */ }
  await probe.close().catch(() => {});

  if (!signedIn) {
    console.error('NOT_SIGNED_IN: the Fabric session is not authenticated. ' +
                  'Sign in manually in the open Chrome window, then re-run.');
    process.exit(4);
  }

  let code = 0;
  try {
    const src = fs.readFileSync(scriptPath, 'utf8');
    const fn = eval('(' + src + ')');
    const t0 = Date.now();
    const out = await fn(page);
    const secs = ((Date.now() - t0) / 1000).toFixed(1);
    if (outPath) {
      fs.writeFileSync(outPath, typeof out === 'string' ? out : JSON.stringify(out));
      console.log(`OK  ${path.basename(scriptPath)}  ${secs}s  ->  ${outPath}`);
    } else {
      console.log(`OK  ${path.basename(scriptPath)}  ${secs}s`);
      console.log(typeof out === 'string' ? out.slice(0, 2000) : out);
    }
  } catch (e) {
    console.error('FAILED:', String(e).split('\n').slice(0, 4).join(' | ').slice(0, 400));
    code = 1;
  }
  // Deliberately do NOT close the browser — it must survive between runs.
  process.exit(code);
})();
