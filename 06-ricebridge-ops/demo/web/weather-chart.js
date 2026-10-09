/* Local, dependency-free weather explorer. Values remain the archive's daily measurements. */
window.RiceWeather = (() => {
  let selectedDate = null;
  let serial = 0;
  const copy = {
    vi: {title: 'Nhịp mưa trên đồng', total: 'Tổng mưa trong kỳ', peak: 'Ngày mưa nhiều nhất', rain: 'Lượng mưa', et: 'Bốc hơi ET0', browse: 'Khám phá từng ngày', hint: 'Rê chuột trên biểu đồ hoặc kéo thanh ngày', dry: 'Không mưa', wet: 'Có mưa', heavy: 'Ngày mưa nổi bật', today: 'Ngày trong demo', pause: 'Dừng chuyển động', play: 'Bật chuyển động', empty: 'Chưa có dữ liệu thời tiết', day: 'Chọn ngày xem số liệu', archive: 'Dữ liệu lịch sử'},
    en: {title: 'The rhythm of the rains', total: 'Rain across this period', peak: 'Wettest day', rain: 'Rainfall', et: 'ET0 evaporation', browse: 'Explore day by day', hint: 'Hover over the chart or move the date slider', dry: 'No rain', wet: 'Rain recorded', heavy: 'Rainfall highlight', today: 'Demo date', pause: 'Pause motion', play: 'Enable motion', empty: 'No weather data available', day: 'Select a date to inspect', archive: 'Historical data'},
    ja: {title: '田んぼを潤す雨のリズム', total: '期間中の総雨量', peak: '最も雨が多かった日', rain: '降水量', et: '蒸発散量 ET0', browse: '日ごとのデータを見る', hint: 'グラフにカーソルを合わせるか、スライダーで日付を選択', dry: '降雨なし', wet: '降雨あり', heavy: '雨量の多い日', today: 'デモ内の日付', pause: '動きを止める', play: '動きを再開', empty: '気象データがありません', day: '確認する日付を選択', archive: '過去の観測データ'},
  };
  const escape = s => String(s).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const number = n => Number(n).toFixed(1);
  let paused = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const states = new WeakMap();

  function render(data, today, width, height, rem, context) {
    const c = copy[context.lang] || copy.vi;
    if (!data.length) return `<div class="weather-empty">${c.empty}</div>`;
    const id = `weather-${++serial}`;
    const rows = data.map(d => ({...d, rain_mm: Math.max(0, Number(d.rain_mm) || 0), et0_mm: Math.max(0, Number(d.et0_mm) || 0)}));
    const maxIndex = rows.reduce((a, d, i) => d.rain_mm > rows[a].rain_mm ? i : a, 0);
    const sum = rows.reduce((a, d) => a + d.rain_mm, 0);
    const fs = Math.max(10, rem * .88);
    const compact = height < rem * 24;
    const W = width, H = Math.max(50, height - rem * (compact ? 6.6 : 10));
    const left = fs * 3, right = fs * 3.2, top = fs * 2.4, base = H - fs * 2;
    const plotWidth = W - left - right, step = plotWidth / rows.length;
    const maxRain = Math.max(40, Math.ceil(rows[maxIndex].rain_mm / 10) * 10);
    const maxEt = Math.max(8, Math.ceil(Math.max(...rows.map(d => d.et0_mm)) / 2) * 2);
    const x = i => left + (i + .5) * step;
    const yr = v => base - v / maxRain * (base - top);
    const ye = v => base - v / maxEt * (base - top);
    let index = rows.findIndex(d => d.date === selectedDate);
    if (index < 0) index = Math.max(0, rows.findIndex(d => d.date === today));
    const points = rows.map((d, i) => `${x(i)},${ye(d.et0_mm)}`).join(' ');
    const rainWidth = step * .64;
    const fmtDate = d => escape(context.date(d));
    const svg = `<svg class="wx wx-explorer" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="${escape(c.title + '. ' + c.hint)}">
      <defs>
        <linearGradient id="${id}-rain" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#a6eeff"/><stop offset=".35" stop-color="#4cc4e5" stop-opacity=".85"/><stop offset="1" stop-color="#269cb5" stop-opacity=".15"/></linearGradient>
        <linearGradient id="${id}-peak" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#d5fbff"/><stop offset=".22" stop-color="#6ce0ec"/><stop offset="1" stop-color="#36baa7" stop-opacity=".28"/></linearGradient>
        <linearGradient id="${id}-et" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#efc973" stop-opacity=".14"/><stop offset="1" stop-color="#efc973" stop-opacity="0"/></linearGradient>
      </defs>
      <rect class="wx-peak-zone" x="${x(maxIndex)-step*.65}" y="${top}" width="${step*1.3}" height="${base-top}" rx="4" fill="#5dd5d3" fill-opacity=".07"/>
      ${[0,.5,1].map(f => `<line x1="${left}" x2="${W-right}" y1="${yr(maxRain*f)}" y2="${yr(maxRain*f)}" class="wx-grid"/><text x="${left-fs*.6}" y="${yr(maxRain*f)+fs*.35}" text-anchor="end" font-size="${fs}" class="wx-axis">${maxRain*f}</text><text x="${W-right+fs*.6}" y="${yr(maxRain*f)+fs*.35}" font-size="${fs}" class="wx-axis wx-gold">${maxEt*f}</text>`).join('')}
      <text x="${left-fs*.6}" y="${top-fs}" text-anchor="end" font-size="${fs*.85}" class="wx-axis">mm</text><text x="${W-right+fs*.6}" y="${top-fs}" font-size="${fs*.85}" class="wx-axis wx-gold">mm</text>
      <polygon points="${x(0)},${base} ${points} ${x(rows.length-1)},${base}" fill="url(#${id}-et)"/>
      ${rows.map((d,i) => `<g><rect class="wx-rainbar${i===maxIndex?' is-peak':''}" data-day="${i}" x="${x(i)-rainWidth/2}" y="${yr(d.rain_mm)}" width="${rainWidth}" height="${Math.max(1,base-yr(d.rain_mm))}" rx="3" fill="url(#${id}-${i===maxIndex?'peak':'rain'})" style="--bar-delay:${i*16}ms"><title>${fmtDate(d.date)}: ${number(d.rain_mm)} mm</title></rect>${d.rain_mm>=10?`<text x="${x(i)}" y="${yr(d.rain_mm)-fs*.7}" text-anchor="middle" font-size="${fs*1.2}" class="wx-peak-value">${number(d.rain_mm)}</text>`:''}${i%Math.max(1,Math.ceil(rows.length/7))===0?`<text x="${x(i)}" y="${H-fs*.4}" text-anchor="middle" font-size="${fs}" class="wx-axis">${fmtDate(d.date)}</text>`:''}</g>`).join('')}
      <polyline class="wx-et-shadow" points="${points}"/><polyline class="wx-et-line" pathLength="1" points="${points}"/>
      ${rows.map((d,i)=>`<circle cx="${x(i)}" cy="${ye(d.et0_mm)}" r="2" class="wx-et-node"/>`).join('')}
      ${rows.some(d=>d.date===today)?`<line class="wx-today" x1="${x(rows.findIndex(d=>d.date===today))}" x2="${x(rows.findIndex(d=>d.date===today))}" y1="${top}" y2="${base}"/><text x="${x(rows.findIndex(d=>d.date===today))+fs*.6}" y="${top-fs*.8}" font-size="${fs}" class="wx-today-label">${escape(c.today)}</text>`:''}
      <g class="wx-cursor" pointer-events="none"><rect class="wx-select-band" y="${top}" width="${step}" height="${base-top}"/><line class="wx-select-line" y1="${top}" y2="${base}"/><circle class="wx-select-dot" r="5"/></g>
    </svg>`;
    const html = `<section class="weather-explorer${compact?' is-compact':''}${paused?' motion-paused':''}" data-weather-id="${id}" aria-label="${c.title}">
      <div class="wx-overview"><div class="wx-heading"><span>${c.archive} · ${fmtDate(rows[0].date)}–${fmtDate(rows[rows.length-1].date)}</span><h3>${c.title}</h3></div><div class="wx-stat"><span>${c.total}</span><strong>${number(sum)}<small> mm</small></strong></div><div class="wx-stat peak"><span>${c.peak} · ${fmtDate(rows[maxIndex].date)}</span><strong>${number(rows[maxIndex].rain_mm)}<small> mm</small></strong></div></div>
      <div class="wx-plot">${svg}</div>
      <div class="wx-controls"><div class="wx-readout"><div class="wx-selected-date"><b data-wx-date></b><span data-wx-condition></span></div><div class="wx-value rain"><span>${c.rain}</span><b data-wx-rain></b></div><div class="wx-value evaporation"><span>${c.et}</span><b data-wx-et></b></div><button type="button" class="wx-motion" aria-pressed="${!paused}">${paused?c.play:c.pause}</button></div><div class="wx-scrubber"><span>${c.browse}</span><input type="range" min="0" max="${rows.length-1}" value="${index}" step="1" aria-label="${c.day}"/><span class="wx-scrub-hint">${c.hint}</span></div></div>
    </section>`;
    // Retain only the most recent render descriptors; detached nodes are weakly held after binding.
    pending.set(id, {rows,index,c,x,ye,left,step,W,date:context.date});
    if (pending.size > 8) pending.delete(pending.keys().next().value);
    return html;
  }
  const pending = new Map();
  function bind(box) {
    const root = box.querySelector('.weather-explorer');
    if (!root || states.has(root)) return;
    const state = pending.get(root.dataset.weatherId);
    pending.delete(root.dataset.weatherId);
    if (!state) return;
    states.set(root,state);
    const svg = root.querySelector('svg');
    const slider = root.querySelector('input');
    const panel = root.closest('.chartpanel');
    const select = index => {
      const i = Math.max(0,Math.min(state.rows.length-1,Math.round(index)));
      const d = state.rows[i];
      state.index = i;
      selectedDate = d.date;
      root.querySelector('[data-wx-date]').textContent = state.date(d.date);
      root.querySelector('[data-wx-condition]').textContent = d.rain_mm>=10?state.c.heavy:d.rain_mm>0?state.c.wet:state.c.dry;
      root.querySelector('[data-wx-rain]').textContent = number(d.rain_mm)+' mm';
      root.querySelector('[data-wx-et]').textContent = number(d.et0_mm)+' mm';
      slider.value = i;
      slider.setAttribute('aria-valuetext', `${state.date(d.date)}. ${state.c.rain}: ${number(d.rain_mm)} mm. ${state.c.et}: ${number(d.et0_mm)} mm.`);
      root.dataset.selectedDate = d.date;
      if (panel) panel.dataset.weatherWet = String(d.rain_mm>=10);
      root.querySelector('.wx-select-band').setAttribute('x',state.x(i)-state.step/2);
      const line = root.querySelector('.wx-select-line');
      line.setAttribute('x1',state.x(i));line.setAttribute('x2',state.x(i));
      const dot = root.querySelector('.wx-select-dot');dot.setAttribute('cx',state.x(i));dot.setAttribute('cy',state.ye(d.et0_mm));
      root.querySelectorAll('.wx-rainbar').forEach(el=>el.classList.toggle('is-selected',Number(el.dataset.day)===i));
    };
    const point = ev => {
      const rect=svg.getBoundingClientRect();
      select(((ev.clientX-rect.left)/rect.width*state.W-state.left)/state.step-.5);
    };
    svg.addEventListener('pointermove',ev=>{if(ev.pointerType==='mouse')point(ev);});
    svg.addEventListener('click',point);
    slider.addEventListener('input',()=>select(Number(slider.value)));
    slider.addEventListener('keydown',ev=>ev.stopPropagation());
    root.querySelector('.wx-motion').addEventListener('click',()=>{
      paused=!paused;
      document.querySelectorAll('.weather-explorer').forEach(el=>{
        el.classList.toggle('motion-paused',paused);
        const button=el.querySelector('.wx-motion');const own=states.get(el);
        if(own){button.textContent=paused?own.c.play:own.c.pause;button.setAttribute('aria-pressed',String(!paused));}
        el.closest('.chartpanel')?.classList.toggle('wx-motion-paused',paused);
      });
    });
    panel?.classList.toggle('wx-motion-paused',paused);
    select(state.index);
  }
  return {render,bind};
})();
