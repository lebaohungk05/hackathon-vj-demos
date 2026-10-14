async (page) => {
  // ---------------------------------------------------------------------
  // Doc cau hinh tu file, KHONG nhung cung vao script.
  // run.py ghi run_config.json truoc khi goi driver.
  // ---------------------------------------------------------------------
  const fs0 = require('fs');
  const CFGPATH = process.env.FRC_CONFIG;
  if (!CFGPATH || !fs0.existsSync(CFGPATH))
    throw new Error('THIEU_CAU_HINH: dat bien moi truong FRC_CONFIG tro toi run_config.json');
  const CFG = JSON.parse(fs0.readFileSync(CFGPATH, 'utf8'));
  const INV = JSON.parse(fs0.readFileSync(CFG.inventory, 'utf8'));
  const FIL = JSON.parse(fs0.readFileSync(CFG.filters, 'utf8'));
  const OUT = CFG.out;
  const ONLY = CFG.reports && CFG.reports.length ? CFG.reports
             : INV.reports.map(r => r.key);
  const DATE_FROM_CFG = CFG.dateFrom || null;
  const DATE_TO_CFG = CFG.dateTo || null;
  // PICK rong = chup het; co PICK thi chi chup dung nhung o do ("v3|R1|P2")
  const PICK = CFG.pick || [];
  const ctx = page.context();

  // Cua so Chrome phai o full man hinh, va viewport emulation phai lay DUNG
  // kich thuoc cua so that do duoc — khong duoc ghi cung. Ghi cung 1920x993
  // trong khi cua so dang o man hinh 1536x960 se lam trang render rong hon
  // cua so va bi cat ben phai.
  const measureView = async (p) => {
    const cdp = await p.context().newCDPSession(p);
    try { await cdp.send('Emulation.clearDeviceMetricsOverride'); } catch (e) {}
    const { windowId } = await cdp.send('Browser.getWindowForTarget');
    // dua cua so sang man hinh rong nhat roi phong to het co
    try {
      await cdp.send('Browser.setWindowBounds', { windowId, bounds: { windowState: 'normal' } });
      await cdp.send('Browser.setWindowBounds', { windowId, bounds: { left: 1920, top: 0, width: 1920, height: 1080 } });
    } catch (e) {}
    await cdp.send('Browser.setWindowBounds', { windowId, bounds: { windowState: 'maximized' } });
    await p.waitForTimeout(1200);
    await cdp.detach().catch(() => {});
    const m = await p.evaluate(() => ({ iw: innerWidth, ih: innerHeight,
                                        aw: screen.availWidth, ah: screen.availHeight, dpr: devicePixelRatio }));
    if (!m.iw || !m.ih) throw new Error('MEASURE_FAILED');
    return { width: m.iw, height: m.ih, screen: m.aw + 'x' + m.ah, dpr: m.dpr };
  };

  const waitReady = async (p, maxMs) => {
    const t0 = Date.now(); let last = null, stable = 0;
    while (Date.now() - t0 < maxMs) {
      let sig;
      try {
        sig = await p.evaluate(() => {
          const da = document.querySelector('.displayArea');
          let busy = 0;
          document.querySelectorAll('[class*="circularProgress"],[class*="progressBar"],[class*="spinner"],[class*="Spinner"]').forEach(e => {
            if (/spinner-background/.test(String(e.className))) return;
            const r = e.getBoundingClientRect();
            if (r.width > 2 && r.height > 2 && e.offsetParent !== null) busy++;
          });
          return { busy: busy, len: da ? da.innerText.length : -1,
                   vis: document.querySelectorAll('[class*="visualContainer"]').length, ready: !!da };
        });
      } catch (e) { await p.waitForTimeout(600); continue; }
      const k = sig.busy + '|' + sig.len + '|' + sig.vis;
      if (sig.ready && sig.busy === 0 && k === last) { stable++; if (stable >= 2) return true; }
      else { stable = 0; last = k; }
      await p.waitForTimeout(450);
    }
    return false;
  };


  // Fabric chi cho mo toi da 20 item cung luc ("Only 20 items can be opened at
  // one time"). 5 version x 5 report = 25 item -> tu item thu 21 se bao
  // "Unable to open Report". Chup xong report nao thi dong item do ngay.
  const closeItem = async (p, rid) => {
    for (let i = 0; i < 4; i++) {
      const st = await p.evaluate((id) => {
        const it = document.querySelector('[data-testid="horizontal-navbar-item-' + id + '"]');
        if (!it) return 'closed';
        const b = it.querySelector('[data-testid="tab-close"]');
        if (!b) return 'no-btn';
        b.click();
        return 'clicked';
      }, rid).catch(() => 'err');
      if (st === 'closed') return 'closed';
      await p.waitForTimeout(700);
    }
    return 'stuck';
  };

  // Ep moi vung cuon ve goc truoc khi chup. Report rong hon khung nhin nen co
  // thanh cuon ngang; hai ban o vi tri cuon khac nhau se lech ~185px va diff
  // pixel bao do toan trang du noi dung giong het.
  const normScroll = async (p) => {
    for (let i = 0; i < 3; i++) {
      // Keo visual nam trai nhat / tren nhat ve dung mep. scrollIntoView tac dong
      // len DUNG cai scroller that su dang cuon, khong can biet no la element nao.
      await p.evaluate(() => {
        const da = document.querySelector('.displayArea');
        if (!da) return;
        const dr = da.getBoundingClientRect();
        const vs = [...da.querySelectorAll('[class*="visualContainer"]')]
          .filter(e => { const r = e.getBoundingClientRect(); return r.width > 4 && r.height > 4; });
        if (!vs.length) return;
        let best = vs[0], bx = 1e9;
        vs.forEach(e => { const r = e.getBoundingClientRect(); const d = (r.x - dr.x) + (r.y - dr.y);
                          if (d < bx) { bx = d; best = e; } });
        if (bx < -2) best.scrollIntoView({ block: 'nearest', inline: 'start' });
      }).catch(() => {});
      await p.evaluate(() => {
        const da = document.querySelector('.displayArea');
        if (!da) return;
        const els = [da, ...da.querySelectorAll('*')];
        let n = da.parentElement;
        while (n && n !== document.body) { els.push(n); n = n.parentElement; }
        els.forEach(e => {
          if (e.scrollWidth  > e.clientWidth  + 1) e.scrollLeft = 0;
          if (e.scrollHeight > e.clientHeight + 1) e.scrollTop  = 0;
        });
        window.scrollTo(0, 0);
      });
      await p.waitForTimeout(300);
    }
  };

  // Ep khoang ngay giong het nhau cho moi version. Slicer nay o che do tuong doi
  // ("Last 16 Days"), ma cac model lai co mocdu lieu khac nhau (v3 den 02/09,
  // bon ban kia den 27/08) -> cung mot cua so tuong doi van ra so khac. Chuyen
  // sang che do tuyet doi va dat cung 19/08-27/08 thi hai ben tinh tren dung
  // mot tap du lieu. Khong ghi gi vao workspace.
  const DATE_FROM = DATE_FROM_CFG, DATE_TO = DATE_TO_CFG;   // dung cua so 14 ngay import, ket thuc 03/09

  const dateInputs = async (p) => p.evaluate(() => {
    const da = document.querySelector('.displayArea');
    if (!da) return 0;
    return [...da.querySelectorAll('input')]
      .filter(e => /item-fill/.test(String(e.className)) && /^\d+\/\d+\/\d{4}$/.test(e.value || '')).length;
  });

  const forceDateRange = async (p) => {
    const has = await p.evaluate(() => {
      const da = document.querySelector('.displayArea');
      if (!da) return false;
      return [...da.querySelectorAll('.ui-role-button-text')]
        .some(e => (e.textContent || '').trim() === '期間');
    });
    if (!DATE_FROM || !DATE_TO) return 'khong-ep-ngay';
    if (!has) return 'no-date-slicer';

    for (let attempt = 0; attempt < 3; attempt++) {
      // Chuyen sang che do tuyet doi. PHAI bam bang chuot that cua Playwright —
      // element.click() trong JS thi Power BI khong nhan.
      if ((await p.locator('.displayArea input.item-fill').count()) < 2) {
        // Tren nhieu page co NHIEU chu 期間 (vua la nhan, vua la nut che do).
        // Bam dai cuoi cung se trung nham nhan -> khong bao gio hien o nhap ngay.
        // Vi vay thu lan luot tung ung vien cho den khi hai o nhap xuat hien.
        const cands = p.locator('.displayArea .ui-role-button-text', { hasText: /^\s*期間\s*$/ });
        const nc = await cands.count().catch(() => 0);
        for (let ci = 0; ci < nc; ci++) {
          await cands.nth(ci).click({ timeout: 8000 }).catch(() => {});
          await p.waitForTimeout(2200);
          if ((await p.locator('.displayArea input.item-fill').count()) >= 2) break;
        }
        if ((await p.locator('.displayArea input.item-fill').count()) < 2) {
          try {
            await p.locator('.displayArea').locator('text="期間"').last().click({ timeout: 12000 });
          } catch (e) { /* thu lai */ }
          await p.waitForTimeout(3000);
        }
      }
      if ((await p.locator('.displayArea input.item-fill').count()) < 2) continue;

      // Dat ca ngay dau va ngay cuoi. fill() moi commit duoc; go bang keyboard
      // hoac gan .value truc tiep thi Angular khong nhan.
      for (const [k, want] of [[0, DATE_FROM], [1, DATE_TO]]) {
        const box = p.locator('.displayArea input.item-fill').nth(k);
        await box.click({ timeout: 8000 }).catch(() => {});
        await box.fill(want).catch(() => {});
        await p.keyboard.press('Tab').catch(() => {});
        await p.waitForTimeout(1800);
      }
      await waitReady(p, 60000);

      const got = await p.evaluate(() => [...document.querySelectorAll('.displayArea input.item-fill')]
        .map(e => e.value).slice(0, 2));
      const same = (a, b) => new Date(a).getTime() === new Date(b).getTime();
      if (got.length === 2 && same(got[0], DATE_FROM) && same(got[1], DATE_TO))
        return got.join(' -> ');
      await p.waitForTimeout(1500);
    }
    return 'date-force-failed';
  };

  const readZoom = async (p) => p.evaluate(() => {
    const e = document.querySelector('.zoomValue');
    return e ? (e.textContent || '').trim() : null;
  }).catch(() => null);

  // Ep muc zoom ve "Fit to page" cho MOI version. Fabric tu tinh lai muc fit sau
  // khi noi dung load xong, luc kip luc khong -> cung mot page ban thi 114% ban
  // thi 127%, lech pixel ca chuc phan tram du so lieu y het. Fit to page con
  // lam ca canvas nam gon trong khung nhin nen khong con thanh cuon de lech.
  const setZoomFit = async (p) => {
    for (let i = 0; i < 3; i++) {
      try {
        await p.locator('.zoomValue').first().click({ timeout: 12000 });
        await p.waitForSelector('[role="dialog"],.mat-mdc-dialog-surface', { timeout: 12000 });
        await p.waitForTimeout(900);
        const pick = async (label) => {
          const n = await p.evaluate((lb) => {
            const roots = [...document.querySelectorAll('[role="dialog"],.mat-mdc-dialog-surface')]
              .filter(e => e.getBoundingClientRect().width > 60);
            if (!roots.length) return -1;
            const r = roots[roots.length - 1];
            const els = [...r.querySelectorAll('button,[role="radio"],[role="option"],label,li')];
            const i2 = els.findIndex(e => (e.textContent || '').trim() === lb);
            if (i2 < 0) return -1;
            els[i2].click();
            return i2;
          }, label);
          return n >= 0;
        };
        if (!(await pick('Fit to page'))) { await p.keyboard.press('Escape'); continue; }
        await p.waitForTimeout(500);
        await pick('Apply');
        await p.waitForTimeout(1600);
        const open = await p.evaluate(() =>
          [...document.querySelectorAll('[role="dialog"],.mat-mdc-dialog-surface')]
            .filter(e => e.getBoundingClientRect().width > 60).length);
        if (!open) return await readZoom(p);
      } catch (e) { /* thu lai */ }
      await p.keyboard.press('Escape').catch(() => {});
      await p.waitForTimeout(900);
    }
    return 'fit-failed';
  };

  // Ep zoom ve **100% co dinh** cho moi version. Day la mac dinh khi chup.
  //
  // "Fit to page" khong dung duoc lam chuan: Fabric TU TINH muc fit tu kich thuoc khung, nen hai
  // ban copy cua cung mot report ra hai muc khac nhau. Do duoc trong lan chay v0-vs-v1:
  // v0=114% / v1=113% tren R1|P5, R1|P6, R2|P2, va v0=128% / v1=127% tren R3|P1, R3|P3.
  // Lech 1% lam MOI phan tu doi kich thuoc -> 39.030 pixel khac tren 844 vung roi rac, trong khi
  // moi con so tren trang y het. 15 o bi cham "khac" ma khong co gi khac that.
  //
  // norm_sig() trong check_layout.py khong cuu duoc: no tru di do DICH CHUNG cua canvas, con
  // zoom la phep TI LE nen w/h cung doi theo.
  //
  // 100% la con so tuyet doi, khong phu thuoc khung nhin hay do dai ten report, nen moi version
  // chac chan bang nhau. Ket qua that su duoc ghi vao rec.zoomSet de con doi chieu duoc.
  const ZOOM_WANT = 100;
  const zoomNum = async (p) => {
    const t = await readZoom(p);
    const n = parseInt(String(t == null ? '' : t).replace(/[^0-9]/g, ''), 10);
    return Number.isFinite(n) ? n : null;
  };

  const setZoom100 = async (p) => {
    if ((await zoomNum(p)) === ZOOM_WANT) return '100%';

    // Cach 1: hop thoai zoom (co muc "100%" san).
    for (let i = 0; i < 2; i++) {
      try {
        await p.locator('.zoomValue').first().click({ timeout: 8000 });
        await p.waitForSelector('[role="dialog"],.mat-mdc-dialog-surface', { timeout: 8000 });
        await p.waitForTimeout(700);
        const clickIn = async (labels) => p.evaluate((lbs) => {
          const roots = [...document.querySelectorAll('[role="dialog"],.mat-mdc-dialog-surface')]
            .filter(e => e.getBoundingClientRect().width > 60);
          if (!roots.length) return false;
          const r = roots[roots.length - 1];
          const els = [...r.querySelectorAll('button,[role="radio"],[role="option"],label,li')];
          const hit = els.find(e => lbs.includes((e.textContent || '').trim()));
          if (!hit) return false;
          hit.click();
          return true;
        }, labels);
        if (await clickIn(['100%', '100 %', '100'])) {
          await p.waitForTimeout(400);
          await clickIn(['Apply', 'OK', 'Ap dung']);
          await p.waitForTimeout(1500);
          if ((await zoomNum(p)) === ZOOM_WANT) return '100%';
        }
      } catch (e) { /* thu cach 2 */ }
      await p.keyboard.press('Escape').catch(() => {});
      await p.waitForTimeout(600);
    }

    // Cach 2: bam nut zoom out/in o goc duoi phai, buoc dan ve 100.
    // Co chan lap: neu muc zoom quay lai gia tri da di qua (buoc nhay bo qua 100) thi dung,
    // chu khong bam qua lai vo han.
    try {
      const seen = new Set();
      for (let step = 0; step < 30; step++) {
        const z = await zoomNum(p);
        if (z == null) break;
        if (z === ZOOM_WANT) return '100%';
        if (seen.has(z)) break;
        seen.add(z);
        const dir = z > ZOOM_WANT ? 'out' : 'in';
        const clicked = await p.evaluate((d) => {
          const re = new RegExp('zoom\\s*' + d, 'i');
          const b = [...document.querySelectorAll('button,[role="button"]')]
            .find(e => re.test(e.getAttribute('aria-label') || e.title || ''));
          if (!b) return false;
          b.click();
          return true;
        }, dir);
        if (!clicked) break;
        await p.waitForTimeout(280);
      }
    } catch (e) { /* bo qua, tra ve muc thuc te */ }

    // Khong ep duoc thi tra ve muc THUC TE kem dau hieu that bai, chu khong bao la da 100%.
    // check_layout.py se doi chieu zoom giua cac version va cham o neu lech.
    const z = await readZoom(p);
    return 'zoom100-failed:' + (z == null ? '?' : z);
  };

  // Truoc khi chup phai xoa hai thu do CHINH MINH gay ra chu khong phai report:
  //  - focus ring den quanh o slicer (do slicer con giu con tro ban phim)
  //  - thanh cong cu hover cua visual (do con tro chuot dang nam tren visual)
  // Hai thu nay lam hai ban khac nhau ve pixel du so lieu y het.
  const neutralize = async (p) => {
    // blur() khong du: Power BI ve lai vien focus ngay sau do. Chan thang bang CSS,
    // ap giong het nhau cho ca 5 version nen khong lam sai lech phep so sanh.
    await p.evaluate(() => {
      if (!document.getElementById('__nofocus')) {
        const st = document.createElement('style');
        st.id = '__nofocus';
        st.textContent = '*:focus,*:focus-visible,*:focus-within{outline:none !important;' +
                         'box-shadow:none !important}';
        document.head.appendChild(st);
      }
    }).catch(() => {});
    await p.evaluate(() => {
      const a = document.activeElement;
      if (a && a !== document.body && typeof a.blur === 'function') a.blur();
      if (document.body) document.body.focus && document.body.focus();
    }).catch(() => {});
    await p.mouse.move(2, 2).catch(() => {});
    await p.waitForTimeout(450);
  };

  // Dong dropdown slicer con mo. Escape khong phai luc nao cung an; khi do bam
  // lai dung cai combobox dang mo (aria-expanded=true) de dong, cach nay khong
  // lam thay doi lua chon. TUYET DOI khong bam bua vao canvas vi se cross-filter.
  const closePop = async (p) => {
    for (let i = 0; i < 8; i++) {
      const open = await p.evaluate(() =>
        [...document.querySelectorAll('.slicer-dropdown-popup')]
          .filter(e => e.getBoundingClientRect().width > 10).length);
      // Lop phu CDK (menu cua Fabric) cung lam ban anh chup nhung Escape
      // khong phai luc nao cung dong duoc -> bam thang vao lop phu.
      const backdrop = await p.evaluate(() =>
        [...document.querySelectorAll('.cdk-overlay-backdrop')]
          .filter(e => e.offsetParent !== null).length);
      if (backdrop) {
        await p.keyboard.press('Escape').catch(() => {});
        await p.waitForTimeout(300);
        await p.locator('.cdk-overlay-backdrop').first()
               .click({ timeout: 4000, force: true }).catch(() => {});
        await p.waitForTimeout(500);
        continue;
      }
      if (!open) return true;
      if (i % 2 === 0) {
        await p.keyboard.press('Escape').catch(() => {});
      } else {
        const n = await p.evaluate(() =>
          [...document.querySelectorAll('.slicer-dropdown-menu[role="combobox"]')]
            .findIndex(e => e.getAttribute('aria-expanded') === 'true'));
        if (n >= 0)
          await p.locator('.slicer-dropdown-menu[role="combobox"]').nth(n)
                 .click({ timeout: 8000 }).catch(() => {});
      }
      await p.waitForTimeout(500);
    }
    return false;
  };

  // Chot an toan: khong bao gio chup khi con hop thoai / lop phu lam mo trang.
  const assertClean = async (p) => {
    const bad = await p.evaluate(() => {
      const hits = [];
      document.querySelectorAll(
        '.mat-mdc-dialog-surface,.cdk-overlay-backdrop,[role="dialog"],[data-testid="dailog-ok-btn"],.slicer-dropdown-popup'
      ).forEach(e => {
        const r = e.getBoundingClientRect();
        if (r.width > 40 && r.height > 20 && e.offsetParent !== null) {
          hits.push(String(e.className).slice(0, 40) || e.getAttribute('data-testid'));
        }
      });
      return hits;
    });
    if (bad.length) throw new Error('DIRTY_OVERLAY: ' + bad.slice(0, 3).join(' | '));
    // Vi tri cuon phai that su bang 0. Neu khong, hai ban se lech ngang vai chuc
    // pixel va bi bao "khac" oan — da tung xay ra o page 全社比較_P.
    const scr = await p.evaluate(() => {
      const da = document.querySelector('.displayArea');
      if (!da) return [];
      const els = [da, ...da.querySelectorAll('*')];
      let n = da.parentElement;
      while (n && n !== document.body) { els.push(n); n = n.parentElement; }
      const off = [];
      els.forEach(e => {
        if (e.scrollWidth > e.clientWidth + 1 && e.scrollLeft > 1) off.push('L' + e.scrollLeft);
        if (e.scrollHeight > e.clientHeight + 1 && e.scrollTop > 1) off.push('T' + e.scrollTop);
      });
      return off.slice(0, 4);
    });
    if (scr.length) throw new Error('NOT_SCROLLED_HOME: ' + scr.join(','));
    // Kiem bang toa do that: visual nam trai/tren nhat phai o dung mep cua
    // displayArea. Neu am nghia la canvas dang bi day di, chup se lech ngang.
    const geo = await p.evaluate(() => {
      const da = document.querySelector('.displayArea');
      if (!da) return null;
      const dr = da.getBoundingClientRect();
      const vs = [...da.querySelectorAll('[class*="visualContainer"]')]
        .filter(e => { const r = e.getBoundingClientRect(); return r.width > 4 && r.height > 4; });
      if (!vs.length) return null;
      let mx = 1e9, my = 1e9;
      vs.forEach(e => { const r = e.getBoundingClientRect();
                        mx = Math.min(mx, r.x - dr.x); my = Math.min(my, r.y - dr.y); });
      return { mx: Math.round(mx), my: Math.round(my) };
    });
    if (geo && (geo.mx < -2 || geo.my < -2))
      throw new Error('CANVAS_SHIFTED: ' + geo.mx + ',' + geo.my);
  };

  const resetDefault = async (p) => {
    try {
      let st = 'no-btn';
      for (let k = 0; k < 20; k++) {          // wait for the toolbar button to render
        st = await p.evaluate(() => {
          const b = document.querySelector('[data-testid="reset-to-default-btn"]');
          if (!b) return 'no-btn';
          return (b.disabled || b.getAttribute('aria-disabled') === 'true') ? 'already-default' : 'dirty';
        });
        if (st !== 'no-btn') break;
        await p.waitForTimeout(500);
      }
      if (st !== 'dirty') return st;
      await p.locator('[data-testid="reset-to-default-btn"]').click({ timeout: 12000 });
      // BAT BUOC: xac nhan trong hop thoai, neu khong thi khong reset gi ca
      // va hop thoai + overlay mo se dinh nguyen vao anh chup.
      await p.waitForSelector('[data-testid="dailog-ok-btn"]', { timeout: 20000 });
      await p.locator('[data-testid="dailog-ok-btn"]').click({ timeout: 12000 });
      // cho hop thoai bien mat han
      await p.waitForFunction(
        () => !document.querySelector('[data-testid="dailog-ok-btn"]') &&
              ![...document.querySelectorAll('.mat-mdc-dialog-surface,.cdk-overlay-backdrop')]
                .some(e => e.getBoundingClientRect().width > 40),
        null, { timeout: 30000 });
      await waitReady(p, 90000);
      await p.waitForTimeout(1500);
      // XAC MINH that su da reset: nut phai chuyen sang disabled
      const after = await p.evaluate(() => {
        const b = document.querySelector('[data-testid="reset-to-default-btn"]');
        if (!b) return 'no-btn';
        return (b.disabled || b.getAttribute('aria-disabled') === 'true') ? 'already-default' : 'dirty';
      });
      return after === 'already-default' ? 'reset' : 'reset-not-applied';
    } catch (e) { return 'reset-failed'; }
  };

  // Mot so trang co them nut "Bookmark" (hinh chu nhat gan action Bookmark, KHONG
  // phai slicer .slicer-dropdown-menu) dung lam bo loc/breakdown nhanh — vi du
  // "truc3 thang/1 thang/14 ngay", "khai trien theo Rate/theo Cua hang". resetDefault()
  // dua trang ve DUNG default cua RIENG report item do, va hai item v0/v1 co the
  // duoc luu voi bookmark mac dinh KHAC NHAU (da xac nhan bang anh chup that: R1|P1/P2/P3
  // — cung slicer p1/p2 nhung "期間"/"列選択"/"行選択" khac nhau -> so sai, khong phai
  // model tinh sai). Cac nut nay CO the click duoc (khong phai gioi han bookmark that
  // su), nen ep ve cung mot nhan hien thi la du, khong can sua report.
  // Mot so nhan (vi du "タイプ") trung chu voi mot NHAN TINH ("選択項目" — luon
  // hien mau xanh co dinh rgb(56,106,165), khong phai nut toggle that) dung o mot
  // cho khac tren cung trang. querySelectorAll+findIndex lay phan tu DAU TIEN nen co
  // the bat nham nhan tinh do — kiem tra "da chon" tren no LUON tra ve true (mau no
  // khong bao gio xam), khien code tuong da chon dung ma khong he click nut that.
  // Da xac nhan bang DOM that: R1|P1 co ca hai — index 12 (nhan tinh, 56,106,165,
  // x=1012) va index 25 (nut that trong panel "行選択区分", x=284, mau doi theo
  // trang thai). Loai nhan tinh truoc khi chon phan tu de kiem tra/click.
  const STATIC_LABEL_FILL = 'rgb(56, 106, 165)';
  const findBookmarkIdx = async (p, label) => p.evaluate((args) => {
    const lbl = args.lbl, staticFill = args.staticFill;
    const matches = [];
    document.querySelectorAll('.ui-role-button-text').forEach((e, i) => {
      if ((e.textContent || '').trim() !== lbl) return;
      const vc = e.closest('[class*="visualContainer"]');
      const shape = vc && vc.querySelector('path, rect');
      matches.push({ i: i, fill: shape ? getComputedStyle(shape).fill : null });
    });
    if (!matches.length) return -1;
    const real = matches.filter(m => m.fill !== staticFill);
    return (real.length ? real[0] : matches[0]).i;
  }, { lbl: label, staticFill: STATIC_LABEL_FILL });

  // DA KIEM QUA CDP THAT: moi phan tu .ui-role-button-text (chon hay khong) deu co
  // class "selected" giong het nhau — class nay VO NGHIA, khong dung duoc de biet
  // nut nao dang duoc chon. Tin hieu THAT: mau fill cua hinh (SVG path/rect) ben
  // trong. Nut CHUA duoc chon trong mot nhom loai tru lan nhau luon la mau xam
  // trung rgb(179,179,179); nut DANG duoc chon co mau khac han (vi du xanh sang
  // rgb(80,156,250)). So bang "co phai xam trung khong" thay vi khop dung 1 ma mau,
  // vi de phong truong hop theme doi sac do chut it.
  const isBookmarkSelected = async (p, idx) => p.evaluate((i) => {
    const el = [...document.querySelectorAll('.ui-role-button-text')][i];
    if (!el) return null;
    const vc = el.closest('[class*="visualContainer"]');
    const shape = vc && vc.querySelector('path, rect');
    if (!shape) return null;
    const m = getComputedStyle(shape).fill.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    if (!m) return null;
    const r = +m[1], g = +m[2], b = +m[3];
    const isNeutralGrey = Math.max(r, g, b) - Math.min(r, g, b) < 12 && r > 140 && r < 220;
    return !isNeutralGrey;
  }, idx);

  const clickBookmark = async (p, label) => {
    // Panel co the co hang chuc nut (vi du "列選択区分") va render CHAM hon phan
    // con lai cua trang — ngay sau resetDefault() no co the CHUA co trong DOM.
    // Thu lai viec TIM (khong chi viec click) truoc khi ket luan "khong thay".
    let idx = -1;
    for (let s = 0; s < 30 && idx < 0; s++) {
      idx = await findBookmarkIdx(p, label);
      if (idx < 0) await p.waitForTimeout(1000);
    }
    if (idx < 0) return { ok: false, why: 'khong thay nut bookmark: ' + label };
    if (await isBookmarkSelected(p, idx)) return { ok: true, attempts: 0 };
    for (let attempt = 0; attempt < 5; attempt++) {
      try {
        await p.locator('.ui-role-button-text').nth(idx).click({ timeout: 8000 });
      } catch (e) {
        await p.locator('.ui-role-button-text').nth(idx).click({ timeout: 8000, force: true });
      }
      await p.waitForTimeout(900);
      await waitReady(p, 30000);
      if (await isBookmarkSelected(p, idx)) return { ok: true, attempts: attempt + 1 };
      await p.waitForTimeout(500);
    }
    return { ok: false, why: 'click khong lam nut duoc chon: ' + label };
  };

  const clickBookmarks = async (p, labels) => {
    const out = [];
    for (const label of (labels || [])) {
      out.push(Object.assign({ label: label }, await clickBookmark(p, label)));
    }
    return out;
  };

  // "pin": slicer THAT (.slicer-dropdown-menu, dung chung co che voi applyFilter)
  // co gia tri mac dinh khac nhau giua v0/v1 nhung KHONG phai muc tieu loc chinh cua
  // page (vi du "機種名称" tren trang R1|P1 chi loc theo 対策区分/曜日). Ep gia tri
  // nay o MOI trang thai, khong chi rieng mot pass.
  const applyPins = async (p, pins) => {
    const out = [];
    for (const pin of (pins || [])) {
      out.push(Object.assign({ aria: pin.aria, v: pin.v }, await applyFilter(p, null, pin.v, pin.aria)));
    }
    return out;
  };

  const popOpts = async (p) => p.evaluate(() => {
    const pops = [...document.querySelectorAll('.slicer-dropdown-popup')]
      .filter(e => e.getBoundingClientRect().width > 10);
    if (!pops.length) return null;
    return [...pops[0].querySelectorAll('[role="option"], .slicerItemContainer')]
      .map(e => ({ t: (e.textContent || '').trim(), s: e.getAttribute('aria-selected') }))
      .filter(x => x.t);
  });

  const scrollPop = async (p, dir) => p.evaluate((d) => {
    const pops = [...document.querySelectorAll('.slicer-dropdown-popup')]
      .filter(e => e.getBoundingClientRect().width > 10);
    if (!pops.length) return false;
    const pop = pops[0];
    let sc = pop, best = 0;
    pop.querySelectorAll('*').forEach(e => {
      if (e.scrollHeight - e.clientHeight > best) { best = e.scrollHeight - e.clientHeight; sc = e; }
    });
    const before = sc.scrollTop;
    sc.scrollTop = d === 0 ? 0 : before + Math.max(60, sc.clientHeight * 0.7);
    return sc.scrollTop !== before;
  }, dir);

  const clickOpt = async (p, value) => {
    for (let s = 0; s < 16; s++) {
      const idx = await p.evaluate((v) => {
        const pops = [...document.querySelectorAll('.slicer-dropdown-popup')]
          .filter(e => e.getBoundingClientRect().width > 10);
        if (!pops.length) return -1;
        const opts = [...pops[0].querySelectorAll('[role="option"], .slicerItemContainer')];
        for (let i = 0; i < opts.length; i++)
          if ((opts[i].textContent || '').trim() === v) return i;
        return -1;
      }, value);
      if (idx >= 0) {
        await p.locator('.slicer-dropdown-popup:visible').first()
               .locator('[role="option"], .slicerItemContainer').nth(idx).click({ timeout: 12000 });
        return true;
      }
      const moved = await scrollPop(p, 1);
      if (!moved) return false;
      await p.waitForTimeout(300);
    }
    return false;
  };

  const openPop = async (p, idx) => {
    const dd = p.locator('.slicer-dropdown-menu[role="combobox"]').nth(idx);
    try {
      await dd.click({ timeout: 12000 });
    } catch (e) {
      await dd.click({ timeout: 12000, force: true });   // overlay stole the hit-test
    }
    for (let k = 0; k < 20; k++) {
      await p.waitForTimeout(400);
      const o = await popOpts(p);
      if (o && o.length) return o;
    }
    return null;
  };

  const applyFilter = async (p, at, value, aria) => {
    // Uu tien tim theo aria-label: dinh danh nay khong doi khi viewport doi,
    // toa do thi doi (toa do cu lay o viewport 3200 nen o 1920 la truot).
    let idx = -1;
    if (aria) {
      idx = await p.evaluate((a) =>
        [...document.querySelectorAll('.slicer-dropdown-menu[role="combobox"]')]
          .findIndex(e => (e.getAttribute('aria-label') || '').trim() === a), aria);
    }
    if (idx < 0 && at) {
      const want = at.split(',').map(Number);
      idx = await p.evaluate((w) => {
        let best = -1, bestD = 1e9;
        [...document.querySelectorAll('.slicer-dropdown-menu[role="combobox"]')].forEach((e, i) => {
          const vc = e.closest('[class*="visualContainer"]');
          const r = vc ? vc.getBoundingClientRect() : e.getBoundingClientRect();
          const d = Math.abs(r.x - w[0]) + Math.abs(r.y - w[1]);
          if (d < bestD) { bestD = d; best = i; }
        });
        return bestD < 45 ? best : -1;
      }, want);
    }
    if (idx < 0) return { ok: false, why: 'slicer not found (aria=' + aria + ', at=' + at + ')' };

    let lastWhy = null, shown = '';
    for (let attempt = 0; attempt < 5; attempt++) {
      let opts = null;
      try {
        opts = await openPop(p, idx);
      } catch (e) {
        lastWhy = 'open popup failed: ' + String(e).split(String.fromCharCode(10))[0].slice(0, 60);
        await p.keyboard.press('Escape').catch(function () {});
        await p.waitForTimeout(900);
        continue;
      }
      if (!opts) { lastWhy = 'popup did not open'; continue; }

      // clear any existing selection so the click selects instead of toggling off / adding
      const anySel = opts.some(o => o.s === 'true');
      if (anySel) {
        await scrollPop(p, 0);
        await p.waitForTimeout(200);
        for (let c = 0; c < 2; c++) {
          const ok = await clickOpt(p, 'Select all');
          if (!ok) break;
          await p.waitForTimeout(700);
          const now = await popOpts(p);
          if (now && !now.some(o => o.s === 'true')) break;
        }
        await scrollPop(p, 0);
        await p.waitForTimeout(200);
      }

      const hit = await clickOpt(p, value);
      if (!hit) { await p.keyboard.press('Escape'); lastWhy = 'value not in slicer: ' + value; await p.waitForTimeout(500); continue; }

      await p.waitForTimeout(900);
      const closed = await closePop(p);
      if (!closed) { lastWhy = 'dropdown khong dong duoc'; continue; }
      await p.waitForTimeout(400);
      await waitReady(p, 60000);

      shown = await p.evaluate((i) => {
        const e = document.querySelectorAll('.slicer-dropdown-menu[role="combobox"]')[i];
        return e ? e.textContent.trim() : '';
      }, idx);
      if (shown.indexOf(value) >= 0 && shown.indexOf('Multiple selections') < 0)
        return { ok: true, shown: shown.slice(0, 40), attempts: attempt + 1 };
      lastWhy = 'verify failed (shown=' + shown.slice(0, 24) + ')';
    }
    return { ok: false, shown: shown.slice(0, 40), why: lastWhy };
  };

  // Chup 2 lan cach nhau ~1.2s va so byte: hai lan giong het nhau moi coi la
  // trang da render xong. Khong co chot nay thi mot anh chup non van duoc luu
  // va sau do bi bao la "khac biet" oan.
  const shoot = async (p, state, tag, ZWANT) => {
    const fs = require('fs');
    // zoom co the bi Fabric tinh lai sau moi lan doi filter -> ep lai neu troi
    const zNow = await readZoom(p);   // chi ghi nhan, khong ep lai
    const el = p.locator('.displayArea').first();
    let prev = null, stable = false, tries = 0;
    let buf = null;
    for (tries = 1; tries <= 6; tries++) {
      await closePop(p);
      await neutralize(p);
      await normScroll(p);
      try {
        await assertClean(p);
      } catch (e) {
        if (tries >= 6) throw e;      // het luot thu -> bao loi that
        await p.waitForTimeout(1200); // con luot -> keo cuon / dong overlay roi thu lai
        prev = null;
        continue;
      }
      try {
        buf = await el.screenshot({ timeout: 90000 });
      } catch (e) {
        if (tries >= 6) throw e;   // ban v3 co the ve rat cham -> cho roi thu lai
        await p.waitForTimeout(4000);
        prev = null;
        continue;
      }
      if (prev && prev.length === buf.length && prev.equals(buf)) { stable = true; break; }
      prev = buf;
      await p.waitForTimeout(1500);
    }
    fs.writeFileSync(OUT + '/' + state + '/' + tag + '.png', buf);
    // Luu ca noi dung chu cua canvas. Day la can cu de phan biet
    // "khac ve so lieu" (chu khac) voi "khac ve giao dien" (chu y het, chi
    // pixel khac).
    const txt = await p.evaluate(() => {
      const d = document.querySelector('.displayArea');
      return d ? d.innerText.replace(/\s+/g, ' ').trim() : '';
    });
    // Muc zoom cua report — moi ban copy luu rieng, zoom khac nhau lam moi thu
    // to nho khac nhau du so lieu y het.
    const zoom = await p.evaluate(() => {
      const hit = [...document.querySelectorAll('*')]
        .filter(e => e.children.length === 0 && /^\d{2,3}%$/.test((e.textContent || '').trim()));
      return hit.length ? hit[hit.length - 1].textContent.trim() : null;
    }).catch(() => null);
    fs.writeFileSync(OUT + '/text/' + state + '__' + tag + '.txt', txt, 'utf8');
    // Chu ky bo cuc: toa do cua tung visual so voi mep displayArea. Neu canvas bi
    // day ngang thi visual trai nhat bi cuon ra ngoai va visual khac tut vao vi
    // tri 0 — kiem "min x >= 0" khong bat duoc, nhung so chu ky nay giua v0 va
    // ban dem so thi bat duoc ngay.
    const layout = await p.evaluate(() => {
      const da = document.querySelector('.displayArea');
      if (!da) return null;
      const dr = da.getBoundingClientRect();
      const vs = [...da.querySelectorAll('[class*="visualContainer"]')]
        .map(e => e.getBoundingClientRect())
        .filter(r => r.width > 4 && r.height > 4)
        .map(r => [Math.round(r.x - dr.x), Math.round(r.y - dr.y), Math.round(r.width), Math.round(r.height)]);
      vs.sort((a, b) => a[1] - b[1] || a[0] - b[0]);
      return { n: vs.length, sig: vs.map(v => v.join(',')).join('|') };
    }).catch(() => null);
    const dateRange = await p.evaluate(() => {
      const t = (document.querySelector('.displayArea') || {}).innerText || '';
      const m = t.match(/26\/\d\d\/\d\d\(.\)[~～]26\/\d\d\/\d\d\(.\)/);
      return m ? m[0] : null;
    }).catch(() => null);
    return { len: txt.length, stable: stable, tries: tries, zoom: zoom,
             nvis: layout ? layout.n : null, sig: layout ? layout.sig : null, dateRange: dateRange };
  };

  // Mot lan mo page -> chup ca 3 state (load, filter1, filter2). Truoc day chay
  // 3 lot rieng => 240 lan navigate; gio con 80.
  const lane = async (V, ONLY) => {
    const ZWANT = { v: null };
    const p = await ctx.newPage();
    await p.setViewportSize({ width: VIEW.width, height: VIEW.height });
    // kiem lai: viewport emulation phai khop cua so that, neu khong thi dung
    const chk = await p.evaluate(() => innerWidth + 'x' + innerHeight);
    if (chk !== VIEW.width + 'x' + VIEW.height)
      throw new Error('VIEWPORT_MISMATCH ' + chk + ' vs ' + VIEW.width + 'x' + VIEW.height);
    const res = [];
    for (const R of INV.reports) {
      if (ONLY.indexOf(R.key) < 0) continue;
      const rid = R.ids[V.id];
      for (const PG of R.pages) {
        if (PICK.length && PICK.indexOf(V.id + '|' + R.key + '|' + PG.k) < 0) continue;
        const key = R.key + '|' + PG.k;
        const f = FIL[key];
        const tag = V.id + '__' + R.key + '__' + PG.k;
        const rec = { tag: tag, rk: R.key, pk: PG.k, v: V.id, hasSlicer: !!f };
        try {
          const url = 'https://app.fabric.microsoft.com/groups/' + V.ws + '/reports/' + rid + '/' + PG.pid + '?experience=fabric-developer';
          await p.goto(url, { waitUntil: 'domcontentloaded', timeout: 180000 });
          try {
            await p.waitForSelector('.displayArea', { timeout: 180000 });
          } catch (e1) {
            await p.reload({ waitUntil: 'domcontentloaded', timeout: 180000 });
            await p.waitForSelector('.displayArea', { timeout: 180000 });
          }
          await waitReady(p, 60000);

          // ---- state 1: load (sau khi da reset ve default) ----
          rec.reset0 = await resetDefault(p);
          // Ep dong bo cac nut "Bookmark" (khong phai slicer) NGAY sau reset, truoc
          // khi chup load — de v0/v1 cung xuat phat tu 1 trang thai nhin duoc, thay vi
          // moi ban giu nguyen bookmark mac dinh rieng cua item do.
          if (f && f.bookmarks) rec.bm0 = await clickBookmarks(p, f.bookmarks);
          // Cac slicer THAT (khong phai bookmark) ngoai p1/p2 cung co the mang gia tri
          // mac dinh khac nhau giua v0/v1 (vi du R1|P1 co slicer "機種名称" rieng, khong
          // phai muc tieu loc cua page nay, nhung van hien "テスト機種M003" o v0 / "All" o
          // v1 ngay o state load). p1/p2 chi duoc ep trong dung pass cua no; "pin" ep
          // MOI trang thai (load, filter1, filter2) — dung cho slicer khong lien quan
          // truc tiep den 2 lan loc chinh nhung van anh huong so lieu hien thi.
          if (f && f.pin) rec.pin0 = await applyPins(p, f.pin);
          // Ep zoom 100% la MAC DINH. Truoc day buoc nay bi bo han ("bo-qua") vi ban ep
          // "Fit to page" that bai 80/80 o, voi ly do ghi lai la "zoom van khop giua cac
          // version (0 o lech)". Gia dinh do sai trong lan chay v0-vs-v1: 15 o lech zoom
          // dung 1%, sinh ra 15 o bao "khac giao diện" ma khong co gi khac that.
          // 100% la muc tuyet doi nen khong con phu thuoc cach Fabric tinh fit.
          rec.zoomSet = await setZoom100(p);
          ZWANT.v = await readZoom(p);
          await p.waitForTimeout(700);
          rec.load = await shoot(p, 'load', tag, ZWANT);

          if (!f) {
            // Page khong co slicer: filter1/filter2 = chinh state load.
            rec.F1 = await shoot(p, 'filter1', tag, ZWANT);
            rec.F2 = await shoot(p, 'filter2', tag, ZWANT);
            rec.note = 'page has no slicer';
          } else {
            for (const pass of [{ n: 'filter1', s: f.p1, k: 'F1' }, { n: 'filter2', s: f.p2, k: 'F2' }]) {
              // BAT BUOC reset truoc moi lan apply, de pass 2 khong cong don pass 1.
              rec['reset' + pass.k] = await resetDefault(p);
              // reset co the dua bookmark/pin ve lai mac dinh rieng cua item -> ep lai.
              if (f.bookmarks) rec['bm' + pass.k] = await clickBookmarks(p, f.bookmarks);
              if (f.pin) rec['pin' + pass.k] = await applyPins(p, f.pin);
              rec['date' + pass.k] = await forceDateRange(p);   // ep 21/08 -> 03/09 cho moi ban
              rec['slicer' + pass.k] = pass.s.aria;
              const ap = await applyFilter(p, null, pass.s.v, pass.s.aria);
              await p.waitForTimeout(800);
              rec['ap' + pass.k] = ap.ok;
              rec['shown' + pass.k] = ap.shown;
              if (!ap.ok) rec['why' + pass.k] = ap.why;
              rec['val' + pass.k] = pass.s.v;
              rec[pass.k] = await shoot(p, pass.n, tag, ZWANT);
            }
          }
          rec.ok = true;
        } catch (e) {
          rec.ok = false;
          rec.err = String(e).split(String.fromCharCode(10))[0].slice(0, 120);
        }
        res.push(rec);
      }
      await closeItem(p, rid);   // tra lai slot cho Fabric (gioi han 20 item)
    }
    await p.close();
    return res;
  };

  const VIEW = await measureView(page);
  // 5 lane: moi version mot lane, chay 16 page tuan tu.
  // Mot lane cho moi version. KHONG tang len 10 lane — da thu, khong chay duoc.
  const GROUPS = [ONLY];
  const jobs = [];
  // Chon version: CFG.versions la danh sach id (vi du ["v0","v1"]).
  // Luon phai co v0 vi moi phep so deu doi chieu voi ban goc.
  let want = CFG.versions && CFG.versions.length ? CFG.versions.slice() : INV.versions.map(v => v.id);
  if (want.indexOf('v0') < 0) want.unshift('v0');
  if (PICK.length) {
    const need = {};
    for (const k of PICK) need[k.split('|')[0]] = 1;
    want = want.filter(v => need[v]);
  }
  const chosen = INV.versions.filter(v => want.indexOf(v.id) >= 0);
  if (!chosen.length) throw new Error('KHONG_CO_VERSION_NAO_DUOC_CHON');
  for (const V of chosen) for (const G of GROUPS) jobs.push(lane(V, G));
  const all = await Promise.all(jobs);
  const flat = [];
  for (const a of all) for (const r of a) flat.push(r);
  flat.push({ _view: VIEW });
  return JSON.stringify(flat);
}
