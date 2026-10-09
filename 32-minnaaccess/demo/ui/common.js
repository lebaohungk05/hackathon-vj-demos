const KIND = {unnamed_field: "Unnamed field", ambiguous_label: "Code instead of a label", keyboard_trap: "Keyboard trap", mouse_only: "Mouse-only button", captcha: "Image CAPTCHA"};
const STAGES = [["listen", "Listen", "screen reader"], ["navigate", "Navigate", "keyboard only"], ["blocked", "Blocked", "barrier found"], ["llm", "LLM proposes fix", "HTML/JS + explanation"], ["human", "Human approves", "developer"], ["restart", "Restart", "from step 1"], ["verified", "Verified", "deterministic checks"]];
const TONE = {listen: "#2a6496", navigate: "#2a6496", blocked: "#bf3a30", llm: "#2c4c8f", human: "#9a6512", restart: "#2a6496", verified: "#147a5e"};
const FLAG = {
  vn: `<svg viewBox="0 0 30 20" aria-hidden="true"><rect width="30" height="20" fill="#da251d"/><polygon fill="#ffcd00" points="15,4 16.35,8.15 20.71,8.15 17.18,10.71 18.53,14.85 15,12.29 11.47,14.85 12.82,10.71 9.29,8.15 13.65,8.15"/></svg>`,
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

const OPEN = {};
const keepOpen = key => OPEN[key] ? " open" : "";

function whyHtml(key, html) {
  if (!html) return "";
  return `<details class="why" data-keep="${esc(key)}"${keepOpen(key)}><summary>${th("Why?")}</summary><div class="whybox">${html}</div></details>`;
}

function fiHtml(cls, isNew, icon, label, text, right, sub) {
  return `<details class="fi ${cls}${isNew ? " new" : ""}"><summary><span class="ic" aria-hidden="true">${icon}</span><span class="t">${text}</span><span class="r">${right || ""}</span></summary><div class="fx"><div class="k">${label}</div>${sub || ""}</div></details>`;
}

function feedItem(e, isNew, P) {
  const step = th("step {n}", {n: e.step});
  if (e.kind === "restart") return fiHtml("rst", isNew, "↻", th("Restart"), ax(e.text), th("attempt {n}", {n: e.attempt}));
  if (e.kind === "hear") {
    const note = /^\(.*\)$/.test(e.text);
    const g = note ? null : glossText(e.text, pageLang(P));
    return fiHtml("hear", isNew, "🔊", th("Screen reader hears"), note ? ax(e.text) : q(e.text, pageLang(P)), step, g ? `<div class="s gl1"><span class="gl">${LANG.toUpperCase()}</span>${g.html}</div>` : "");
  }
  if (e.kind === "action" && isLLM(e.engine)) {
    const m = e.llm, o = m && m.output;
    const typed = e.op === "fill" ? e.value : (String(e.text).match(/^type “([\s\S]*?)” \(/) || [])[1];
    const act = typed !== undefined ? th("type {value}", {value: q(typed, langOf(typed))}) : ax(e.text.replace(/\s*\(.*$/, ""));
    return fiHtml("llm", isNew, "✦", th("LLM thought → action"), act, m ? esc(pretty(m.model)) : "", `${o ? `<div class="s">${lx(o.field_meaning)}</div>` : ""}${m ? `<div class="s">${esc(srcLabel(m))}</div>` : ""}`);
  }
  if (e.kind === "action") return fiHtml("rule", isNew, "⌨", String(e.engine || "").startsWith("rule fallback") ? th("Rule fallback · keyboard action") : th("Rule · keyboard action"), ax(e.text), th("guard"));
  if (e.kind === "advisory") return fiHtml("adv", isNew, "!", th("LLM advisory · needs human"), lx(e.text), e.llm ? esc(pretty(e.llm.model)) : "");
  if (e.kind === "barrier") return fiHtml("bad", isNew, "✗", th("Deterministic check · blocked"), ax(e.text), `WCAG ${esc(e.barrier.sc)}`);
  if (e.kind === "handoff") return fiHtml("hum", isNew, "✋", th("Hand-off to a human"), ax(e.text), th("guard"));
  if (e.kind === "patch") return fiHtml(isLLM(e.engine) ? "llm" : "rule", isNew, "✎", `${isLLM(e.engine) ? th("LLM-written patch") : th("Rule-based patch")} · ${code(e.file)}`, patchText(e, P), e.precheck && e.precheck.passed ? th("pre-check ✓") : th("pre-check ✗"));
  if (e.kind === "approval") return fiHtml(e.approved ? "ok" : "bad", isNew, e.approved ? "✓" : "✗", th("Human decision"), ax(e.text), step);
  if (e.kind === "precheck_fail") return fiHtml("bad", isNew, "⚙", th("Pre-check failed · LLM retries"), ax(e.text), th("retry"));
  if (["pass", "verified", "reached"].includes(e.kind)) return fiHtml("ok", isNew, "✓", e.kind === "verified" ? th("Deterministic check · verified") : e.kind === "reached" ? th("Goal reached") : th("Deterministic check · pass"), ax(e.text), step);
  if (e.kind === "sys") return fiHtml("sys", isNew, "i", e.labelHtml || th(e.label || "Agent"), e.html || ax(e.text), esc(e.right || ""));
  if (e.kind === "warn") return fiHtml("warn", isNew, "!", th(e.label || "Notice"), e.html || ax(e.text), "");
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
  return m ? `<span class="sp"><span class="pill llm" title="${esc(srcLabel(m))}">✦ ${esc(pretty(m.model))}</span></span>` : "";
}

function readCardHtml(m, ruleStopped, P) {
  const o = m.output;
  return `<div class="card llmc grow"><h3>✦ ${th("LLM reasoning")} ${llmChips(m)}</h3>
    <dl class="kv"><dt>${th("Screen reader heard")}</dt><dd class="heard big">${heardHtml(m.heard, P)}</dd>
    <dt>${th("LLM reading")}</dt><dd class="mean"><b>${lx(o.field_meaning)}</b></dd>
    <dt>${th("Value to type")}</dt><dd class="big">${o.decision === "fill" ? `<b class="val">${q(o.value, langOf(o.value))}</b>` : th("hand off to a human")}</dd></dl></div>`;
}

function readWhyHtml(m, ruleStopped, P) {
  const o = m.output;
  const rows = [`<p><b>${th("Why")}:</b> ${lx(o.reasoning)}</p>`];
  if (o.label_clear_for_screen_reader === false && o.advisory) rows.push(`<p><b>${th("Advisory")}:</b> ${lx(o.advisory)}</p>`);
  if (m) rows.push(`<p class="mute">✦ ${esc(pretty(m.model))} · ${esc(srcLabel(m))}</p>`);
  if (ruleStopped) rows.push(`<p>⚖ ${th("{b}Rule-only engine on the same field:{/b} stopped and handed it to a human, because {heard} is not in its keyword table.", {b: "<b>", "/b": "</b>", heard: q(m.heard, pageLang(P))})}</p>`);
  rows.push(`<p>🛡 ${th("{b}Guardrail:{/b} the LLM interprets and proposes. It never decides pass or fail. Submit stays forbidden by a hard rule.", {b: "<b>", "/b": "</b>"})}</p>`);
  return rows.join("");
}

function blockedCardHtml(b, P) {
  return `<div class="card badc grow"><div class="blockhero"><div class="sc"><small>WCAG</small><b>${esc(b.sc)}</b><em>${th("Level {l}", {l: esc(b.level)})}</em></div>
    <div><h4>${esc(kindName(b.kind))} · ${code("#" + b.element_id)}</h4><p>${ax(b.evidence)}</p></div></div></div>`;
}

function blockedWhyHtml(b, P) {
  return `<p>⚙ ${th("Step {n} · {name} · found by a {b}deterministic {check}{/b}, not by the LLM.", {n: b.step, name: esc(stepName(P.key, b.step)), b: "<b>", "/b": "</b>", check: esc(t(checkLabel(b.check)))})}</p>`;
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

function handoffCardHtml(b, P) {
  return `<div class="card humc grow"><div class="blockhero"><div class="sc hum"><small>WCAG</small><b>${esc(b.sc)}</b><em>${esc(scTitle(b.sc, b.sc_title))}</em></div>
    <div><h4>✋ ${th("{kind} → human officer", {kind: esc(kindName(b.kind))})}</h4><p>${ax(b.evidence)}</p></div></div></div>`;
}

function handoffWhyHtml(b, submitted) {
  const captcha = b.kind === "captcha";
  return `<p><b>${th("Next owner")}:</b> ${th("Human officer.")} ${captcha ? th("Recommended fix: an audio or text alternative.") : th("The officer confirms what the field asks for.")}</p>
    <p><b>${th("Guards")}:</b> ${th("No CAPTCHA solving · no submit (submitted: {v}) · no login · 127.0.0.1 only", {v: `<b>${esc(yesNo(submitted || "no"))}</b>`})}</p>`;
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
  return `<h3>${th("Run timeline")}</h3>${banner}<div class="tlg" style="grid-template-columns:auto repeat(${P.steps.length},minmax(0,1fr))">${html}</div>`;
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
  capEl.title = meta || "";
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

const PETAL_STAMPS = ["VERIFIED ✓", "GOAL REACHED"];

function setStamp(st) {
  const screen = document.getElementById("screen");
  const key = st ? `${st[0]}|${t(st[1], st[2])}` : "";
  if (screen.dataset.stamp === key && (!st || screen.querySelector(".stamp-ov"))) return;
  screen.dataset.stamp = key;
  screen.querySelectorAll(".stamp-ov, .petal-fall").forEach(x => x.remove());
  if (!st) return;
  screen.insertAdjacentHTML("beforeend", `<div class="stamp-ov ${st[0]}">${esc(t(st[1], st[2]))}</div>`);
  if (st[0] === "ok" && PETAL_STAMPS.includes(st[1])) dropPetals(screen);
}

function dropPetals(host) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const fall = document.createElement("div");
  fall.className = "petal-fall";
  fall.setAttribute("aria-hidden", "true");
  fall.innerHTML = "<i></i>".repeat(9);
  host.append(fall);
  setTimeout(() => fall.remove(), 6000);
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

function sheadHtml(title, sub, why) {
  return `<h2>${title}</h2>${sub || why ? `<div class="subrow">${sub ? `<p>${sub}</p>` : ""}${why || ""}</div>` : ""}`;
}
