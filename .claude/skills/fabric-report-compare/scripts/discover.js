async (page) => {
  const ctx = page.context();
  const fs0 = require('fs');
  const CFG = JSON.parse(fs0.readFileSync(process.env.FRC_CONFIG, 'utf8'));
  const INV = JSON.parse(fs0.readFileSync(CFG.inventory, 'utf8'));
  const V0 = INV.versions.find(v => v.id === 'v0');

  const p = await ctx.newPage();
  const cdp = await ctx.newCDPSession(p);
  try { await cdp.send('Emulation.clearDeviceMetricsOverride'); } catch (e) {}
  const { windowId } = await cdp.send('Browser.getWindowForTarget');
  await cdp.send('Browser.setWindowBounds', { windowId, bounds: { windowState: 'maximized' } });
  await p.waitForTimeout(900);
  const mm = await p.evaluate(() => ({ iw: innerWidth, ih: innerHeight }));
  await p.setViewportSize({ width: mm.iw, height: mm.ih });

  const waitReady = async (mx) => {
    const t0 = Date.now(); let last = null, st = 0;
    while (Date.now() - t0 < mx) {
      let s;
      try {
        s = await p.evaluate(() => {
          const da = document.querySelector('.displayArea');
          let busy = 0;
          document.querySelectorAll('[class*="circularProgress"],[class*="spinner"]').forEach(e => {
            const r = e.getBoundingClientRect();
            if (r.width > 2 && r.height > 2 && e.offsetParent !== null) busy++;
          });
          return { busy, len: da ? da.innerText.length : -1, ready: !!da };
        });
      } catch (e) { await p.waitForTimeout(500); continue; }
      const k = s.busy + '|' + s.len;
      if (s.ready && s.busy === 0 && k === last) { st++; if (st >= 2) return true; } else { st = 0; last = k; }
      await p.waitForTimeout(500);
    }
    return false;
  };
  const popOpts = () => p.evaluate(() => {
    const pops = [...document.querySelectorAll('.slicer-dropdown-popup')].filter(e => e.getBoundingClientRect().width > 10);
    if (!pops.length) return null;
    return [...pops[0].querySelectorAll('[role="option"], .slicerItemContainer')]
      .map(e => (e.textContent || '').trim()).filter(t => t).slice(0, 14);
  });
  const closePop = async () => {
    for (let i = 0; i < 6; i++) {
      const n = await p.evaluate(() => [...document.querySelectorAll('.slicer-dropdown-popup')]
        .filter(e => e.getBoundingClientRect().width > 10).length);
      if (!n) return true;
      if (i % 2 === 0) await p.keyboard.press('Escape').catch(() => {});
      else {
        const k = await p.evaluate(() => [...document.querySelectorAll('.slicer-dropdown-menu[role="combobox"]')]
          .findIndex(e => e.getAttribute('aria-expanded') === 'true'));
        if (k >= 0) await p.locator('.slicer-dropdown-menu[role="combobox"]').nth(k).click({ timeout: 6000 }).catch(() => {});
      }
      await p.waitForTimeout(450);
    }
    return false;
  };

  const out = [];
  for (const R of INV.reports) {
    for (const PG of R.pages) {
      const rec = { rk: R.key, rn: R.name, pk: PG.k, pn: PG.nm, hidden: !!PG.hidden, slicers: [], other: [], date: null, err: null };
      try {
        await p.goto('https://app.fabric.microsoft.com/groups/' + V0.ws + '/reports/' + R.ids.v0 + '/' + PG.pid + '?experience=fabric-developer',
                     { waitUntil: 'domcontentloaded', timeout: 180000 });
        await p.waitForSelector('.displayArea', { timeout: 180000 });
        await waitReady(60000);
        await p.waitForTimeout(2500);

        rec.date = await p.evaluate(() => {
          const t = document.querySelector('.displayArea').innerText;
          const m = t.match(/26\/\d\d\/\d\d\(.\)[~～]26\/\d\d\/\d\d\(.\)/);
          return m ? m[0] : null;
        });
        // slicer dang dropdown
        const meta = await p.evaluate(() => {
          const da = document.querySelector('.displayArea'); const dr = da.getBoundingClientRect();
          return [...document.querySelectorAll('.slicer-dropdown-menu[role="combobox"]')].map((e, i) => {
            const vc = e.closest('[class*="visualContainer"]');
            const r = (vc || e).getBoundingClientRect();
            const t = vc ? vc.querySelector('.title, [class*="titleText"], .visualTitle, h3') : null;
            return { i, aria: (e.getAttribute('aria-label') || '').trim(), title: t ? t.textContent.trim() : '',
                     at: Math.round(r.x) + ',' + Math.round(r.y),
                     cur: (e.textContent || '').trim().slice(0, 32) };
          });
        });
        for (const s of meta.slice(0, 6)) {
          try {
            await p.locator('.slicer-dropdown-menu[role="combobox"]').nth(s.i).click({ timeout: 9000 });
            let vals = null;
            for (let k = 0; k < 14; k++) { await p.waitForTimeout(400); vals = await popOpts(); if (vals && vals.length) break; }
            s.vals = vals || [];
            await closePop();
          } catch (e) { s.vals = []; s.err = String(e).slice(0, 60); }
          rec.slicers.push(s);
        }
        // slicer khong phai dropdown: nut bam / tile / o ngay
        rec.other = await p.evaluate(() => {
          const da = document.querySelector('.displayArea');
          const res = [];
          da.querySelectorAll('[class*="visualContainer"]').forEach(vc => {
            const t = vc.querySelector('.title, [class*="titleText"], .visualTitle');
            const tiles = [...vc.querySelectorAll('.slicerItemContainer, .ui-role-button-text, .slicerText')]
              .map(e => (e.textContent || '').trim()).filter(x => x).slice(0, 10);
            const hasInput = !!vc.querySelector('input.duration-input, input.item-fill');
            if ((tiles.length && !vc.querySelector('.slicer-dropdown-menu')) || hasInput)
              res.push({ title: t ? t.textContent.trim() : '', tiles, dateSlicer: hasInput });
          });
          return res.slice(0, 10);
        });
      } catch (e) { rec.err = String(e).slice(0, 110); }
      out.push(rec);
    }
  }
  await p.close();
  return JSON.stringify(out, null, 1);
}
