const KIND = {unnamed_field: "Unnamed field", ambiguous_label: "Code instead of a label", keyboard_trap: "Keyboard trap", mouse_only: "Mouse-only button", captcha: "Image CAPTCHA"};
const STAGES = [["listen", "Listen", "screen reader"], ["navigate", "Navigate", "keyboard only"], ["blocked", "Blocked", "barrier found"], ["llm", "LLM proposes fix", "HTML/JS + explanation"], ["human", "Human approves", "developer"], ["restart", "Restart", "from step 1"], ["verified", "Verified", "deterministic checks"]];
const TONE = {listen: "#38bdf8", navigate: "#38bdf8", blocked: "#e11d48", llm: "#7c3aed", human: "#d97706", restart: "#38bdf8", verified: "#14b8a6"};
const FLAG = {
  vn: `<svg viewBox="0 0 30 20" aria-hidden="true"><rect width="30" height="20" fill="#da251d"/><polygon fill="#ffcd00" points="15,4 16.76,9.43 22.47,9.43 17.86,12.79 19.62,18.21 15,14.86 10.38,18.21 12.14,12.79 7.53,9.43 13.24,9.43"/></svg>`,
  jp: `<svg viewBox="0 0 30 20" aria-hidden="true"><rect width="30" height="20" fill="#fff"/><circle cx="15" cy="10" r="6" fill="#bc002d"/></svg>`,
};
const short = m => String(m || "").replace(/-\d{8}$/, "");
const pretty = m => { const p = short(m).replace(/^claude-/, "").split("-"); return p.length && p[0] ? p[0][0].toUpperCase() + p[0].slice(1) + (p.length > 1 ? " " + p.slice(1).join(".") : "") : ""; };
const secs = ms => fmtSecs(ms);
const isLLM = engine => String(engine || "").startsWith("LLM");
const engineName = engine => {
  const e = String(engine || "");
  if (e.startsWith("LLM")) return pretty(e.replace(/^LLM\s*/, ""));
  if (e.startsWith("rule fallback")) return t("the rule engine (LLM fallback)");
  return t("the rule engine");
};
const HOST = location.protocol.startsWith("http") ? location.host : "127.0.0.1:8765";
const PURPOSE_LABEL = {"interpret field": "read a field label", "write patch": "write a patch"};

function feedItem(e, isNew, P) {
  const n = isNew ? " new" : "";
  const step = th("step {n}", {n: e.step});
  if (e.kind === "restart") return `<div class="fi rst${n}"><span class="ic">↻</span><div class="tx"><div class="t">${ax(e.text)}</div></div><span class="r">${th("attempt {n}", {n: e.attempt})}</span></div>`;
  if (e.kind === "hear") {
    const g = /^\(.*\)$/.test(e.text) ? null : glossText(e.text, pageLang(P));
    return `<div class="fi hear${n}"><span class="ic" aria-hidden="true">🔊</span><div class="tx"><div class="k">${th("Screen reader hears")}</div><div class="t">${/^\(.*\)$/.test(e.text) ? ax(e.text) : q(e.text, pageLang(P))}</div>${g ? `<div class="s gl1"><span class="gl">${LANG.toUpperCase()}</span>${g.html}</div>` : ""}</div><span class="r">${step}</span></div>`;
  }
  if (e.kind === "action" && isLLM(e.engine)) {
    const m = e.llm, o = m && m.output;
    const typed = e.op === "fill" ? e.value : (String(e.text).match(/^type “([\s\S]*?)” \(/) || [])[1];
    const act = typed !== undefined ? th("type {value}", {value: q(typed, langOf(typed))}) : ax(e.text.replace(/\s*\(.*$/, ""));
    return `<div class="fi llm${n}"><span class="ic">✦</span><div class="tx"><div class="k">${th("LLM thought → action")}</div><div class="t">${act}</div>${o ? `<div class="s">${lx(o.field_meaning)}</div>` : ""}</div><span class="r">${m ? esc(pretty(m.model)) + " · " + esc(secs(m.ms)) : ""}</span></div>`;
  }
  if (e.kind === "action") return `<div class="fi rule${n}"><span class="ic">⌨</span><div class="tx"><div class="k">${String(e.engine || "").startsWith("rule fallback") ? th("Rule fallback · keyboard action") : th("Rule · keyboard action")}</div><div class="t">${ax(e.text)}</div></div><span class="r">${th("guard")}</span></div>`;
  if (e.kind === "advisory") return `<div class="fi adv${n}"><span class="ic">!</span><div class="tx"><div class="k">${th("LLM advisory · needs human")}</div><div class="t">${lx(e.text)}</div></div><span class="r">${e.llm ? esc(pretty(e.llm.model)) : ""}</span></div>`;
  if (e.kind === "barrier") return `<div class="fi bad${n}"><span class="ic">✗</span><div class="tx"><div class="k">${th("Deterministic check · blocked")}</div><div class="t">${ax(e.text)}</div></div><span class="r">WCAG ${esc(e.barrier.sc)}</span></div>`;
  if (e.kind === "handoff") return `<div class="fi hum${n}"><span class="ic">✋</span><div class="tx"><div class="k">${th("Hand-off to a human")}</div><div class="t">${ax(e.text)}</div></div><span class="r">${th("guard")}</span></div>`;
  if (e.kind === "patch") return `<div class="fi ${isLLM(e.engine) ? "llm" : "rule"}${n}"><span class="ic">✎</span><div class="tx"><div class="k">${isLLM(e.engine) ? th("LLM-written patch") : th("Rule-based patch")} · ${code(e.file)}</div><div class="t">${patchText(e, P)}</div></div><span class="r">${e.precheck && e.precheck.passed ? th("pre-check ✓") : th("pre-check ✗")}</span></div>`;
  if (e.kind === "approval") return `<div class="fi ${e.approved ? "ok" : "bad"}${n}"><span class="ic">${e.approved ? "✓" : "✗"}</span><div class="tx"><div class="k">${th("Human decision")}</div><div class="t">${ax(e.text)}</div></div><span class="r">${step}</span></div>`;
  if (e.kind === "precheck_fail") return `<div class="fi bad${n}"><span class="ic">⚙</span><div class="tx"><div class="k">${th("Pre-check failed · LLM retries")}</div><div class="t">${ax(e.text)}</div></div><span class="r">${th("retry")}</span></div>`;
  if (["pass", "verified", "reached"].includes(e.kind)) return `<div class="fi ok${n}"><span class="ic">✓</span><div class="tx"><div class="k">${e.kind === "verified" ? th("Deterministic check · verified") : e.kind === "reached" ? th("Goal reached") : th("Deterministic check · pass")}</div><div class="t">${ax(e.text)}</div></div><span class="r">${step}</span></div>`;
  if (e.kind === "sys") return `<div class="fi sys${n}"><span class="ic">i</span><div class="tx"><div class="k">${e.labelHtml || th(e.label || "Agent")}</div><div class="t">${e.html || ax(e.text)}</div></div><span class="r">${esc(e.right || "")}</span></div>`;
  if (e.kind === "warn") return `<div class="fi warn${n}"><span class="ic">!</span><div class="tx"><div class="k">${th(e.label || "Notice")}</div><div class="t">${e.html || ax(e.text)}</div></div><span class="r"></span></div>`;
  return "";
}

function patchText(p, P) {
  if (!isLLM(p.engine)) return ax(p.text);
  if (LANG === "en") return dx(p.text);
  if (LANG === pageLang(P) && p.explanation_local) return dx(p.explanation_local);
  return lx(p.text);
}

function trimFeed(minKeep = 2) {
  const f = document.getElementById("feed");
  if (!f) return;
  const panel = f.parentElement;
  const growers = [...panel.querySelectorAll(":scope > .grow")];
  growers.forEach(g => g.style.flexGrow = "0");
  f.style.flex = "1 1 0";
  while (f.children.length > 0 && f.scrollHeight > f.clientHeight + 1) f.removeChild(f.firstElementChild);
  f.style.flex = "0 0 auto";
  growers.forEach(g => g.style.flexGrow = "");
  if (f.children.length < minKeep && f.children.length && panel.scrollHeight > panel.clientHeight + 1) f.innerHTML = "";
  [...f.querySelectorAll(".fi.new")].forEach((el, i) => el.style.animationDelay = (i * 0.28) + "s");
}

function srcLabel(m) {
  if (!m) return "";
  if (m.source === "cache") return m.error ? t("cached answer (live call failed)") : t("replay · live call took {s}", {s: secs(m.ms)});
  if (m.source === "live") return t("live call · {s}", {s: secs(m.ms)});
  return t(m.source);
}

function llmChips(m) {
  return m ? `<span class="sp"><span class="pill llm">✦ ${esc(pretty(m.model))}</span><span class="pill g">${esc(srcLabel(m))}</span></span>` : "";
}

function readCardHtml(m, ruleStopped, P) {
  const o = m.output;
  const pl = pageLang(P);
  return `<div class="card llmc grow"><h3>✦ ${th("LLM reasoning")} ${llmChips(m)}</h3>
    <dl class="kv"><dt>${th("Screen reader heard")}</dt><dd class="heard big">${heardHtml(m.heard, P)}</dd>
    <dt>${th("LLM reading")}</dt><dd style="font-size:1.1rem"><b>${lx(o.field_meaning)}</b></dd>
    <dt>${th("Value to type")}</dt><dd class="big">${o.decision === "fill" ? `<b style="color:var(--ok)">${q(o.value, langOf(o.value))}</b>` : th("hand off to a human")}</dd>
    <dt>${th("Why")}</dt><dd>${lx(o.reasoning)}</dd>
    ${o.label_clear_for_screen_reader === false && o.advisory ? `<dt>${th("Advisory")}</dt><dd>${lx(o.advisory)}</dd>` : ""}</dl>
    ${ruleStopped ? `<div class="guard" style="border-color:var(--hum2)"><span>⚖</span><span>${th("{b}Rule-only engine on the same field:{/b} stopped and handed it to a human, because {heard} is not in its keyword table.", {b: "<b>", "/b": "</b>", heard: q(m.heard, pl)})}</span></div>` : ""}
    <div class="guard"><span>🛡</span><span>${th("{b}Guardrail:{/b} the LLM interprets and proposes. It never decides pass or fail. Submit stays forbidden by a hard rule.", {b: "<b>", "/b": "</b>"})}</span></div></div>`;
}

function blockedCardHtml(b, P) {
  return `<div class="card badc grow"><div class="blockhero"><div class="sc"><small>WCAG</small><b>${esc(b.sc)}</b><em>${th("Level {l}", {l: esc(b.level)})}</em></div>
    <div><h4>${esc(kindName(b.kind))} · ${code("#" + b.element_id)}</h4><p>${ax(b.evidence)}</p></div></div>
    <div class="guard" style="border-color:var(--bad2)"><span>⚙</span><span>${th("Step {n} · {name} · found by a {b}deterministic {check}{/b}, not by the LLM.", {n: b.step, name: esc(stepName(P.key, b.step)), b: "<b>", "/b": "</b>", check: esc(t(checkLabel(b.check)))})}</span></div></div>`;
}

function checkLabel(c) {
  const s = String(c || "");
  if (!s || s.startsWith("deterministic")) return "check";
  return s;
}

function blockedLLMHtml(m, P) {
  if (!m) return "";
  return `<div class="card llmc"><h3>✦ ${th("LLM reads the visible caption")} ${llmChips(m)}</h3><p class="big" style="font-size:1.08rem"><span class="strike">${m.heard ? q(m.heard, pageLang(P)) : ax("(nothing but the role)")}</span><span class="arrow">→</span><b>${lx(m.output.field_meaning)}</b> <span style="color:var(--mute)">${th("(caption {c})", {c: q(m.caption, pageLang(P))})}</span></p>${gloss(m.caption, pageLang(P))}</div>`;
}

function checksList(check, baseDelay = 0.9) {
  if (!check) return "";
  return `<ul class="checks">${check.checks.map((c, i) => `<li style="animation-delay:${baseDelay + i * 0.25}s"><span class="m ${c.passed ? "ok" : "bad"}">${c.passed ? "✓" : "✗"}</span><span>${c.html || checkName(c.name)}<span class="d">${c.detailHtml || checkDetail(c.detail)}</span></span></li>`).join("")}</ul>`;
}

function diffHtml(d, maxLines) {
  const lines = String(d || "").split("\n").filter(Boolean).filter(l => !l.startsWith("---") && !l.startsWith("+++") && !l.startsWith("@@"));
  const keep = lines.filter(l => l.startsWith("+") || l.startsWith("-")).slice(0, maxLines);
  return keep.map((l, i) => {
    const c = l.startsWith("+") ? "add" : l.startsWith("-") ? "del" : "ctx";
    return `<span class="${c}" style="animation-delay:${i * 0.12}s">${esc(l)}</span>`;
  }).join("");
}

function patchCardHtml(p, P, compact, tight) {
  const llm = isLLM(p.engine);
  return `<div class="card shrink ${llm ? "llmc" : ""}"><h3>${llm ? `✦ ${th("LLM-written patch")}` : th("Rule-based patch")} · ${code(p.file)} ${llm ? llmChips(p.llm) : `<span class="sp"><span class="pill g">${esc(engineName(p.engine))}</span></span>`}</h3>
    ${compact ? "" : `<div class="expl${tight ? " tight" : ""}"><span class="lg">${LANG.toUpperCase()}</span><span>${patchText(p, P)}</span></div>`}
    <details class="patch-details"><summary>${th("Code change")}</summary><pre class="diff" data-src="code" aria-label="${esc(t("Code change"))}">${diffHtml(p.diff, compact ? 4 : 8)}</pre></details></div>`;
}

function precheckCardHtml(p) {
  const ok = p.precheck && p.precheck.passed;
  return `<div class="card pre"><h3>⚙ ${th("Deterministic pre-check on a staging copy")} <span class="sp"><span class="pill ${ok ? "ok" : "bad"}">${ok ? th("passed") : th("failed")}</span></span></h3>${checksList(p.precheck)}</div>`;
}

function verifiedCardHtml(b, P, attempt, record, axeAfter) {
  const rows = [{passed: true, name: `Keyboard replay: restarted from step 1 in attempt ${attempt} and passed step ${b.step}`, detail: "deterministic"}, ...((record && record.precheck && record.precheck.checks) || [])];
  if (axeAfter !== null && axeAfter !== undefined) rows.push({passed: !axeAfter, name: `axe-core on the fixed page: ${axeAfter} violation(s) on #${b.element_id}`, detail: "axe-core 4.10.2", detailHtml: "axe-core 4.10.2"});
  return `<div class="card okc grow"><div class="blockhero" style="margin-bottom:.9rem"><div class="sc ok"><small>WCAG</small><b>${esc(b.sc)}</b><em>✓ ${th("fixed")}</em></div>
    <div><h4>${th("Verified ✓ {id}", {id: code("#" + b.element_id)})}</h4><p>${th("{kind} no longer blocks. Fix proposed by {who}, judged by code.", {kind: esc(kindName(b.kind)), who: esc(record ? engineName(record.patch_engine) : t("the agent"))})}</p></div></div>
    ${checksList({checks: rows})}</div>`;
}

function handoffCardHtml(b, P, submitted) {
  const captcha = b.kind === "captcha";
  return `<div class="card humc grow"><div class="blockhero"><div class="sc hum"><small>WCAG</small><b>${esc(b.sc)}</b><em>${esc(scTitle(b.sc, b.sc_title))}</em></div>
    <div><h4>✋ ${th("{kind} → human officer", {kind: esc(kindName(b.kind))})}</h4><p>${ax(b.evidence)}</p></div></div>
    <dl class="kv" style="margin-top:1rem"><dt>${th("Next owner")}</dt><dd>${th("Human officer.")} ${captcha ? th("Recommended fix: an audio or text alternative.") : th("The officer confirms what the field asks for.")}</dd>
    <dt>${th("Guards")}</dt><dd>${th("No CAPTCHA solving · no submit (submitted: {v}) · no login · 127.0.0.1 only", {v: `<b>${esc(yesNo(submitted || "no"))}</b>`})}</dd></dl></div>`;
}

function yesNo(v) {
  return v === "no" ? t("no") : v === "yes" ? t("yes") : String(v);
}

function timelineHtml(P, events, curA, curStep, sweep, maxRows = 4) {
  const attempts = [...new Set(events.filter(e => e.kind === "restart").map(e => e.attempt))];
  const shown = attempts.length > maxRows ? attempts.slice(-maxRows) : attempts;
  let html = `<div></div>` + P.step_names.map((n, i) => `<div class="h">${i + 1} · ${esc(stepName(P.key, i + 1))}</div>`).join("");
  shown.forEach(a => {
    html += `<div class="r">${th("Attempt {n}", {n: a})}</div>`;
    for (let st = 1; st <= P.steps.length; st++) {
      const here = events.filter(e => e.attempt === a && e.step === st);
      let cls = "", txt = "·";
      if (here.some(e => e.kind === "barrier")) { const b = here.find(e => e.kind === "barrier").barrier; cls = "block"; txt = `✗ ${b.sc}`; }
      else if (here.some(e => e.kind === "handoff")) { cls = "handoff"; txt = t("→ human"); }
      else if (here.some(e => e.kind === "verified")) { cls = "pass"; txt = t("✓ verified"); }
      else if (here.some(e => e.kind === "pass" || e.kind === "reached")) { cls = "pass"; txt = here.some(e => e.kind === "reached") ? t("✓ reached") : t("✓ pass"); }
      else if (here.length) { cls = "pass"; txt = "…"; }
      const now = curA === a && curStep === st ? " now" : "";
      const sw = sweep && a === curA && here.length ? ` sweep" style="animation-delay:${(st - 1) * 0.22}s` : "";
      html += `<div class="cell ${cls}${now}${sw}">${esc(txt)}</div>`;
    }
  });
  const banner = sweep ? `<div class="restart-banner"><span class="ring"></span>${th("Restart from step 1 · attempt {n}", {n: curA})}</div>` : "";
  return `<h3>${th("Run timeline")} <span class="sp"><span class="pill g">${th("restart from step 1 after every fix")}</span></span></h3>${banner}<div class="tlg" style="grid-template-columns:auto repeat(${P.steps.length},minmax(0,1fr))">${html}</div>`;
}

function setRail(stage) {
  const idx = STAGES.findIndex(s => s[0] === stage);
  const restartDone = stage === "verified";
  document.getElementById("rail").innerHTML = STAGES.map(([k, tt, sub], i) => {
    const now = i === idx;
    const done = !now && idx >= 0 && (i < idx || (restartDone && k === "restart"));
    const mark = done ? "✓" : String(i + 1);
    return `<div class="st${now ? " now" : ""}${done ? " done" : ""}" style="--tone:${TONE[k]}"${now ? ' aria-current="step"' : ""}><span class="dot">${mark}</span><span class="lb"><b>${th(tt)}</b><small>${th(sub)}</small></span>${i < STAGES.length - 1 ? `<span class="bar"></span>` : ""}</div>`;
  }).join("");
}

let typeTimer = null;
function typewriter(text, animate, srcLang, after) {
  const el = document.getElementById("said");
  clearInterval(typeTimer);
  typeTimer = null;
  const chars = [...String(text || "")];
  el.classList.toggle("long", chars.length > 60);
  el.dataset.src = srcLang || "code";
  el.lang = srcLang || "";
  if (!animate) { el.innerHTML = chars.length ? `<span class="q">“</span>${esc(text)}<span class="q">”</span>` : ""; after && after(); return; }
  let n = 0;
  const step = Math.max(1, Math.ceil(chars.length / 45));
  const draw = () => { el.innerHTML = `<span class="q">“</span>${esc(chars.slice(0, n).join(""))}${n < chars.length ? `<span class="cur"></span>` : `<span class="q">”</span>`}`; };
  draw();
  typeTimer = setInterval(() => { n = Math.min(chars.length, n + step); draw(); if (n >= chars.length) { clearInterval(typeTimer); typeTimer = null; after && after(); } }, 32);
}

function setCaption(text, tone, meta, animate, P) {
  const capEl = document.getElementById("caption");
  const isNote = /^\(.*\)$/.test(String(text || ""));
  const g = text && !isNote ? glossText(text, pageLang(P)) : null;
  capEl.className = "caption " + (tone || "") + (text ? "" : " quiet") + (g ? " glossed" : "");
  document.getElementById("capMeta").textContent = meta || "";
  const glossEl = document.getElementById("gloss");
  glossEl.innerHTML = "";
  const showGloss = () => { glossEl.innerHTML = g ? `<span class="gl">${LANG.toUpperCase()}</span>${g.html}` : ""; };
  if (isNote) {
    clearInterval(typeTimer);
    typeTimer = null;
    const el = document.getElementById("said");
    el.dataset.src = "";
    el.removeAttribute("data-src");
    el.lang = LANG;
    el.classList.remove("long");
    el.innerHTML = `<span class="note-said">${ax(text)}</span>`;
    return;
  }
  typewriter(text, animate, pageLang(P), showGloss);
}

function setStamp(st) {
  const screen = document.getElementById("screen");
  screen.querySelectorAll(".stamp-ov").forEach(x => x.remove());
  if (st) screen.insertAdjacentHTML("beforeend", `<div class="stamp-ov ${st[0]}">${esc(t(st[1], st[2]))}</div>`);
}

let toastTimer = null;
function toast(html, bad) {
  const tEl = document.getElementById("toast");
  tEl.innerHTML = html;
  tEl.className = "toast" + (bad ? " bad" : "");
  tEl.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { tEl.hidden = true; }, 4200);
}

function fitHeader() {
  const hdr = document.getElementById("hdr");
  if (!hdr) return;
  const chips = [...hdr.children];
  chips.forEach(c => { c.hidden = false; });
  const order = [...chips].sort((x, y) => (+x.dataset.prio || 0) - (+y.dataset.prio || 0));
  for (const c of order) {
    if (hdr.scrollWidth <= hdr.clientWidth + 1) break;
    if (order.filter(x => !x.hidden).length <= 1) break;
    c.hidden = true;
  }
}
