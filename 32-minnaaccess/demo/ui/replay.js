const params = new URLSearchParams(location.search);
let R = window.RUN || null;
const RULE = window.RULE_BASELINE || null;

function baselineFor(key) {
  if (!RULE) return null;
  return RULE.procedures.find(p => p.key === key) || null;
}

function buildScenes() {
  const s = [];
  R.procedures.forEach((P, pi) => {
    const ev = P.events;
    const add = o => s.push({p: pi, ...o});
    const firstRestart = ev.find(e => e.kind === "restart");
    if (!firstRestart) return;
    const hears = ev.filter(e => e.attempt === 1 && e.kind === "hear");
    const listenAt = (hears[Math.min(3, hears.length - 1)] || firstRestart).i;
    add({key: `${P.key}-listen`, stage: "listen", at: listenAt, panel: "listen"});
    const base = baselineFor(P.key);
    const baseStops = base ? base.barriers.filter(b => b.status === "handoff" && b.kind !== "captcha").map(b => b.element_id) : [];
    const shownLLM = new Set();
    ev.forEach(e => {
      if (e.kind === "action" && e.llm && e.llm.purpose === "interpret field" && !shownLLM.has(e.llm.field)) {
        const o = e.llm.output;
        const interesting = baseStops.includes(e.llm.field) || o.label_clear_for_screen_reader === false;
        if (!interesting) return;
        shownLLM.add(e.llm.field);
        add({key: `${P.key}-read-${e.llm.field}`, stage: "navigate", at: e.i, panel: "read", e});
      }
      if (e.kind === "barrier") {
        const b = e.barrier;
        const p = ev.find(x => x.kind === "patch" && x.attempt === e.attempt && x.i > e.i);
        const a = ev.find(x => x.kind === "approval" && x.attempt === e.attempt && x.i > e.i);
        const v = ev.find(x => x.kind === "verified" && x.barrier && x.barrier.element_id === b.element_id);
        add({key: `${P.key}-blocked-${b.element_id}`, stage: "blocked", at: e.i, panel: "blocked", e, b});
        if (p) add({key: `${P.key}-fix-${b.element_id}`, stage: "llm", at: p.i, panel: "fix", e: p, b});
        if (p) add({key: `${P.key}-approve-${b.element_id}`, stage: "human", at: a ? a.i : p.i, panel: "approve", e: p, a, b});
        if (v) add({key: `${P.key}-verified-${b.element_id}`, stage: "verified", at: v.i, panel: "verified", e: v, b});
      }
      if (e.kind === "handoff") add({key: `${P.key}-handoff`, stage: "verified", at: e.i, panel: "handoff", e, b: e.barrier});
    });
    const reached = ev.find(e => e.kind === "reached");
    if (reached && !ev.some(e => e.kind === "handoff")) add({key: `${P.key}-reached`, stage: "verified", at: ev.length - 1, panel: "reached", e: reached});
    if (P.final) {
      add({key: `${P.key}-audit`, stage: "verified", at: ev.length - 1, panel: "audit"});
      if (P.axe) add({key: `${P.key}-axe`, stage: "verified", at: ev.length - 1, panel: "axe"});
    }
  });
  if (R.complete) s.push({p: R.procedures.length - 1, key: "engine", stage: "verified", at: R.procedures[R.procedures.length - 1].events.length - 1, panel: "engine"});
  return s;
}

function sceneText(sc) {
  const P = R.procedures[sc.p];
  const e = sc.e, b = sc.b;
  switch (sc.panel) {
    case "listen": return {label: t("Listen"), title: esc(procTitle(P.key)), sub: th("The agent hears the page and moves by Tab only."),
      why: `<p>${th("Attempt 1 · the agent hears the page like a blind user and moves by Tab only. Goal: {goal}.", {goal: esc(t(PROC_EN[P.key].goal))})}</p>${howList()}`};
    case "read": {
      const o = e.llm.output;
      const val = (e.text.match(/“(.*?)”/) || [])[1] || "";
      const base = baselineFor(P.key);
      return {label: t("LLM reads {heard}", {heard: e.llm.heard}), title: th("LLM reads an unclear label: {heard}", {heard: q(e.llm.heard, pageLang(P))}), sub: th("{meaning} → types {value}", {meaning: lx(o.field_meaning), value: q(val, langOf(val))}),
        why: readWhyHtml(e.llm, base && base.barriers.some(x => x.element_id === e.llm.field), P)};
    }
    case "blocked": return {label: t("Blocked {id}", {id: "#" + b.element_id}), title: th("Blocked at step {n}: {kind}", {n: b.step, kind: esc(kindName(b.kind))}), sub: th("WCAG {sc} {title}", {sc: esc(b.sc), title: esc(scTitle(b.sc, b.sc_title))}),
      why: `<p>${th("Attempt {a} · WCAG {sc} {title} (Level {l}) on {id}", {a: e.attempt, sc: esc(b.sc), title: esc(scTitle(b.sc, b.sc_title)), l: esc(b.level), id: code("#" + b.element_id)})}</p>${blockedWhyHtml(b, P)}`};
    case "fix": return {label: t("LLM fix"), title: th(isLLM(e.engine) ? "LLM proposes a fix for {id}" : "Rule engine proposes a fix for {id}", {id: code("#" + b.element_id)}), sub: th("Pre-checked. Nothing is applied yet."),
      why: `<p>${th("Patch + plain-language explanation, pre-checked on a staging copy. Nothing is applied yet.")}</p>${isLLM(e.engine) && e.llm ? `<p class="mute">✦ ${esc(pretty(e.llm.model))} · ${esc(srcLabel(e.llm))}</p>` : ""}`};
    case "approve": return {label: t("Human approves"), title: th(sc.a ? (sc.a.approved ? "Developer approved the patch" : "Developer rejected the patch") : "Waiting for the developer to approve"), sub: th("Only a human can apply a change."),
      why: `<p>${th("Only a human can apply a change to the portal. Then the whole procedure restarts from step 1.")}</p>${sc.a ? `<p>${sc.a.approved ? th("Applied to the mock portal → the whole procedure restarts from step 1. Try it yourself in the Live run tab.") : th("Not applied. The barrier stays open and goes to a human officer.")}</p>` : ""}`};
    case "verified": return {label: t("Verified {id}", {id: "#" + b.element_id}), title: th("Restarted from step 1 · {id} verified", {id: code("#" + b.element_id)}), sub: th("Judged by code, not by the LLM."),
      why: `<p>${th("Attempt {a} · judged by keyboard replay, the accessibility tree and axe-core. The LLM does not grade its own fix.", {a: e.attempt})}</p>`};
    case "handoff": return {label: t("Hand-off"), title: th("{kind} → hand off to a human", {kind: esc(kindName(e.barrier.kind))}), sub: th("Never bypassed. Nothing is submitted."),
      why: `<p>${th("Confirmation page reached. Never bypassed. The submit button is never pressed.")}</p>${handoffWhyHtml(e.barrier, P.submitted)}`};
    case "reached": return {label: t("Goal reached"), title: th("Confirmation step reached by keyboard only"), sub: th("Stopped before the submit button."),
      why: `<p>${th("Attempt {a} · stopped before the submit button. Form submitted: {v}.", {a: e.attempt, v: esc(yesNo(P.submitted || "no"))})}</p>`};
    case "audit": return {label: P.key === "jp" ? t("Test results") : t("Audit record"), title: P.key === "jp" ? th("JIS X 8341-3:2016 test results from this run") : th("Audit record · TT 21/2023 + JIS X 8341-3"), sub: th("Generated from this run."),
      why: `<p>${th("Generated from the run. An NVDA user re-listens to each row and an officer re-checks it before the record is drawn up.")}</p>${auditWhy(P)}`};
    case "axe": return {label: t("vs axe-core"), title: th("MinnaAccess vs axe-core, same pages"), sub: th("{country} mock procedure, same run", {country: esc(procCountry(P.key))}), why: axeWhy(P)};
    case "engine": return {label: t("Engine & guardrails"), title: th("Who decided what: LLM, rules and humans"), sub: th("Every LLM call of this run"), why: engineWhy()};
    default: return {label: "", title: "", sub: "", why: ""};
  }
}

let scenes = [];
let cur = 0;
let lastRendered = null;

function P_() { return R.procedures[scenes[cur].p]; }

function chapterList() {
  const c = R.procedures.map((P, i) => ({label: procCountry(P.key), idx: scenes.findIndex(s => s.p === i)}));
  const axe = scenes.findIndex(s => s.panel === "axe");
  if (axe >= 0) c.push({label: t("vs axe-core"), idx: axe});
  const eng = scenes.findIndex(s => s.panel === "engine");
  if (eng >= 0) c.push({label: t("Engine"), idx: eng});
  return c.filter(x => x.idx >= 0);
}

function procButton(key, on, attrs) {
  return `<button class="proc ${on ? "on" : ""}" ${attrs} title="${esc(procTitle(key))}" aria-label="${esc(procTitle(key))}" aria-pressed="${on}">${FLAG[key] || ""}<span>${esc(key.toUpperCase())}</span></button>`;
}

function replayHeader() {
  const sc = scenes[cur];
  document.getElementById("procs").innerHTML = R.procedures.map((P, i) => procButton(P.key, sc.p === i, `data-jump="${scenes.findIndex(s => s.p === i)}"`)).join("");
  const calls = R.llm_calls || [];
  const fallbacks = R.procedures.flatMap(P => P.events).filter(e => String(e.engine || "").startsWith("rule fallback")).length;
  const llm = R.engine_kind === "llm";
  const eng = llm ? `<span class="chip llm"><i></i>LLM · ${esc(pretty(R.models.decisions))} + ${esc(pretty(R.models.patches))}</span><span class="chip ${fallbacks ? "warn" : "ok"}">${th("fallback {n}", {n: fallbacks})}</span>` : `<span class="chip rule"><i></i>${th("Rule engine only")}</span>`;
  const how = R.llm_mode === "replay" ? t("cached replies") : R.llm_mode === "live" ? t("fresh LLM calls") : t("LLM, cached");
  const mode = `<span class="chip"><i></i>${th("Recorded run · {how} · {n} calls", {how: esc(how), n: calls.length})}</span>`;
  document.getElementById("hdr").innerHTML = eng + mode;
  document.getElementById("dStatusSec").hidden = true;
}

function replayTimeline(sc) {
  const P = P_(), ev = P.events;
  const e = ev[sc.at];
  return timelineHtml(P, ev.filter(x => x.i <= sc.at), e.attempt, e.step, sc.panel === "verified");
}

function replayFeed(sc) {
  const P = P_(), ev = P.events, a = ev[sc.at].attempt;
  const items = ev.filter(e => e.attempt === a && e.i <= sc.at && ["hear", "action", "advisory", "barrier", "handoff", "reached", "restart", "pass", "verified"].includes(e.kind));
  const tail = items.slice(-4);
  return `<div class="feed" id="feed" aria-label="${esc(t("Screen reader and agent log"))}">${tail.map((e, i) => feedItem(e, i >= tail.length - 2, P)).join("")}</div>`;
}

function readCard(sc) {
  const m = sc.e.llm;
  const base = baselineFor(P_().key);
  return readCardHtml(m, base && base.barriers.some(b => b.element_id === m.field), P_());
}

function approvalCard(sc) {
  if (!sc.a) return `<div class="card humc"><h3>✋ ${th("Human approval")} <span class="sp"><span class="pill hum">${th("pending")}</span></span></h3>
    <div class="decide"><button class="btn yes waiting" disabled>✓ ${th("Approve")}</button><button class="btn no" disabled>✗ ${th("Reject")}</button></div>
    <div class="whoapp">${th("The patch waits for a developer. Nothing is applied automatically.")}</div></div>`;
  const ok = sc.a.approved;
  return `<div class="card humc grow"><h3>✋ ${th("Human approval")} <span class="sp"><span class="pill g">${WHO.includes(sc.a.who) ? th(sc.a.who) : esc(sc.a.who || "")}</span></span></h3>
    <div class="decide"><button class="btn yes ${ok ? "chosen" : "dim"}" disabled>✓ ${ok ? th("Approved") : th("Approve")}</button><button class="btn no ${ok ? "dim" : "chosen"}" disabled>✗ ${ok ? th("Reject") : th("Rejected")}</button></div>
    </div>`;
}

function verifiedCard(sc) {
  const P = P_();
  const record = P.barriers.find(x => x.element_id === sc.b.element_id);
  const after = P.axe ? Object.values(P.axe.fixed).flat().filter(v => v.targets.some(tg => tg.includes("#" + sc.b.element_id))).length : null;
  return verifiedCardHtml(sc.b, P, sc.e.attempt, record, after);
}

function reachedCard() {
  const P = P_();
  const fixed = P.barriers.filter(b => b.status === "fixed");
  const rows = fixed.map(b => ({passed: true, html: th("Step {n}: {kind} on {id} (WCAG {sc})", {n: b.step, kind: esc(kindName(b.kind)), id: code("#" + b.element_id), sc: esc(b.sc)}), detailHtml: th("fixed in attempt {a}, verified in attempt {v}", {a: b.attempt, v: b.verified_attempt})}));
  rows.push({passed: true, html: th("Refused to press the submit button ({name})", {name: q(PROC_EN[P.key].submit, pageLang(P))}), detailHtml: th("Form submitted: {v}", {v: esc(yesNo(P.submitted || "no"))})});
  return `<div class="card okc grow"><h3 style="color:var(--ok)">✓ ${th("Goal reached")} <span class="sp"><span class="pill ok">${th("{n} barriers fixed and verified", {n: fixed.length})}</span></span></h3>
    ${checksList({checks: rows})}</div>`;
}

function howList() {
  return `<ul class="howl"><li>🔊 ${th("Hears every focus change as an NVDA-style line built from the accessibility tree")}</li><li>⌨ ${th("Moves with Tab, Space, Enter and typing only. No mouse, no login, no submit")}</li><li>↻ ${th("After every approved fix, restarts the whole procedure from step 1")}</li></ul>`;
}

function listenArt() {
  return `<div class="card grow art">${heroFill("listen", true)}</div>`;
}

const JIS_TERM = "試験結果";

function resultCells(status) {
  const fixed = status === "fixed", hand = status === "handoff";
  return {
    vn: fixed ? "Fail → fixed, re-check passed" : hand ? "Fail → handed to an officer" : "Fail → not fixed",
    jis: fixed ? "Does not conform → conforms in the re-test after the fix" : hand ? "Does not conform → to a human check" : "Does not conform (not fixed)",
  };
}

function auditPanel() {
  const P = P_();
  const jp = P.key === "jp";
  const pl = pageLang(P);
  const status = r => (P.barriers.find(b => b.element_id === r.element && b.step === r.step) || {}).status || (r.verified_attempt ? "fixed" : "handoff");
  const rows = P.audit.map(r => {
    const st = status(r);
    const c = resultCells(st);
    if (jp) {
      const fix = st === "handoff" ? th("Hand off to human (never bypassed)") : LANG === "ja" ? dx(r.action_local || r.action) : LANG === "en" ? dx(r.action) : lx(r.action);
      return `<tr><td class="nw">${r.step}</td><td class="nw"><b>${esc(r.sc)}</b><br><span class="mute">${esc(scTitle(r.sc, r.sc_title))}</span></td><td class="nw">${esc(r.level)}</td><td class="nw">${code("#" + r.element)}</td><td class="nw no">${th("Does not conform")}</td><td class="nw"><span class="yes">${r.verified_attempt ? th("Conforms") : th("Not confirmed")}</span><br><span class="mute">${r.verified_attempt ? th("after the fix, attempt {n}", {n: r.verified_attempt}) : ""}</span></td><td>${fix}</td></tr>`;
    }
    const heard = /^\(.*\)$/.test(r.heard) ? ax(r.heard) : `${q(r.heard, pl)}${gloss(r.heard, pl)}`;
    return `<tr><td>${r.step}</td><td class="nw"><b>${esc(r.sc)}</b> ${esc(scTitle(r.sc, r.sc_title))}</td><td>${esc(r.level)}</td><td class="heardcell">${heard}</td><td>${LANG === "vi" ? esc(r.vn_result) : th(c.vn)}</td><td>${LANG === "ja" ? esc(r.jis_result) : th(c.jis)}</td></tr>`;
  }).join("");
  const termHtml = LANG === "ja" ? esc(JIS_TERM) : th("test results ({term})", {term: qs(JIS_TERM, "ja")});
  const head = jp
    ? `<th>${th("Step")}</th><th>${th("Success criterion")}</th><th>${th("Level")}</th><th>${th("Target")}</th><th>${th("First test")}</th><th>${th("Re-test")}</th><th>${th("Fix (LLM explanation, approved by a human)")}</th>`
    : `<th>${th("Step")}</th><th>${th("Success criterion")}</th><th>${th("Level")}</th><th>${th("Screen reader heard")}</th><th>${th("VN · TT 21/2023")}</th><th>${th("JP · JIS X 8341-3 {term}", {term: termHtml})}</th>`;
  const fixed = P.barriers.filter(b => b.status === "fixed").length;
  const hand = P.barriers.filter(b => b.status === "handoff").length;
  const h3 = jp ? `${termHtml} · JIS X 8341-3:2016` : th("Audit record · Vietnam TT 21/2023 and Japan JIS X 8341-3");
  return `<div class="stats">
      <div class="stat"><b>${P.rounds}</b><span>${th("attempts, each from step 1")}</span></div>
      <div class="stat ok"><b>${fixed}</b><span>${th("barriers fixed and verified by replay")}</span></div>
      <div class="stat z"><b>${hand}</b><span>${th("handed to a human")}</span></div>
      <div class="stat"><b style="color:${P.submitted && P.submitted !== "no" ? "var(--bad)" : "var(--ok)"}">${esc(yesNo(P.submitted || "no"))}</b><span>${th("form submitted")}</span></div></div>
    <div class="card grow audit" style="overflow:hidden;justify-content:flex-start"><h3 class="audith">${h3}</h3>
    <table><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table>
    <div class="disclaimer">${th("Team simulation on a mock page. Not a conformance claim; not for self-declaring conformance.")}</div></div>`;
}

function auditWhy(P) {
  const pl = pageLang(P);
  const adv = (P.advisories || []).map(a => `<li>${code("#" + a.element)} ${q(a.heard, pl)}: ${lx(a.advisory)}</li>`).join("");
  return `${adv ? `<p><b>${th("Non-blocking advisories (LLM suggestion, not a test result):")}</b></p><ul>${adv}</ul>` : ""}
    <p>${th("{title} · {n} attempts · judged by keyboard replay, accessibility tree and axe-core · exported to {file}", {title: esc(procTitle(P.key)), n: P.rounds, file: code(`out/jis_shiken_kekka_${P.key}.csv`)})}</p><p class="mute">${esc(R.generated)}</p>`;
}

function axeWhy(P) {
  const byRule = {};
  P.axe.axe_only.forEach(x => { byRule[x.rule] = byRule[x.rule] || {n: 0, impact: x.impact, sc: x.sc.join(", "), steps: new Set()}; byRule[x.rule].n++; byRule[x.rule].steps.add(x.step); });
  const extra = Object.entries(byRule).map(([k, v]) => th("{rule} ({impact}, WCAG {sc}) on {n} element(s), steps {steps}: a real issue, but it does not stop a keyboard + screen-reader user.", {rule: `<b>${code(k)}</b>`, impact: esc(t(v.impact)), sc: esc(v.sc), n: v.n, steps: [...v.steps].join(", ")})).join(" ");
  return `<p>${th("MinnaAccess vs axe-core 4.10.2 on the same original pages")}.</p><p>${th("axe-core reported instead: {extra} After the approved fixes, axe-core finds {n} violation(s) on the fixed pages (the footer contrast issue is outside the procedure and left for the owner).", {extra: extra || th("nothing else."), n: P.axe.fixed_violations})}</p>`;
}

function engineWhy() {
  return `<p>${th("Every LLM call of this run, its latency, and what the rule-only engine did on the same pages")}.</p><p>${th("claude CLI · strict JSON schema · validated · 1 retry · cached by prompt hash")}</p>
    <p>${th("Latency is the time of the original live call (claude CLI round trip). Replays read the same answer from {dir}.", {dir: code("demo/cache")})}</p>
    <p>🛡 ${th("{b}LLM{/b}: reads labels, chooses values, writes patches. {b}Rules{/b}: never press {submit1} / {submit2}, CAPTCHA → human, Tab-trap and Tab-order detection. {b}Humans{/b}: approve every patch, re-check every record. {b}Pass/fail{/b}: keyboard replay + accessibility tree + axe-core.", {b: "<b>", "/b": "</b>", submit1: q("Nộp hồ sơ", "vi"), submit2: q("申請する", "ja")})}</p>`;
}

function axePanel() {
  const P = P_(), c = P.axe.comparison;
  const n = c.length, axeN = c.filter(r => r.axe).length;
  const rows = c.map((r, i) => `<div class="brow" style="animation:slideIn .4s ${0.3 + i * 0.15}s both"><span><b>${th("Step {n}", {n: r.step})}</b> · ${esc(kindName(r.kind))} ${code("#" + r.element)} <span class="pill g">WCAG ${esc(r.sc)}</span></span><span class="dotc y" aria-label="${esc(t("found"))}">✓</span><span class="dotc ${r.axe ? "y" : "n"}" title="${esc(r.axe_rules.join(", "))}" aria-label="${esc(r.axe ? t("found") : t("missed"))}">${r.axe ? "✓" : "✗"}</span></div>`).join("");
  const m = R.sim_metrics && R.sim_metrics.blocking_detection;
  const bar = (label, v, total, col, unit, i) => `<div class="bar2"><span>${th(label)}</span><div class="track"><div class="fill" style="width:${100 * v / total}%;background:${col};animation-delay:${0.4 + i * 0.2}s"></div></div><b>${unit ? v + unit : v + "/" + total}</b></div>`;
  const sim = m ? `<div class="card"><h3>${th("Team simulation (proposal §2.4, rule-based engine)")} <span class="sp"><span class="pill g">${th("{n} mock forms with seeded defects", {n: R.sim_metrics.n_defect_variants})}</span></span></h3><div class="bars">
    ${bar("Agent: blocking barriers found", m.agent.tp, R.sim_metrics.n_blocking_defects, "linear-gradient(90deg,#147a5e,#2f9a78)", "", 0)}
    ${bar("axe-core: blocking barriers found", m.axe.tp, R.sim_metrics.n_blocking_defects, "#8f8aa3", "", 1)}
    ${bar("Reached the last step, before fixes", Math.round(R.sim_metrics.journey_completion_defect_variants.before_repair * 1000) / 10, 100, "#b07414", "%", 2)}
    ${bar("Reached the last step, after fixes", Math.round(R.sim_metrics.journey_completion_defect_variants.after_repair * 1000) / 10, 100, "linear-gradient(90deg,#2c4c8f,#5677b8)", "%", 3)}</div></div>` : "";
  return `<div class="vs"><div class="score a"><b>${n}/${n}</b><span><strong>MinnaAccess</strong>${th("blocking barriers found on the original pages (this run)")}</span></div><div class="vsx">vs</div><div class="score x"><b>${axeN}/${n}</b><span><strong>axe-core 4.10.2</strong>${th("same pages, same run")}</span></div></div>
    <div class="card"><div class="brow h"><span>${th("Blocking barrier")}</span><span>MinnaAccess</span><span>axe-core</span></div>${rows}</div>${sim}`;
}

function enginePanel() {
  const calls = R.llm_calls || [];
  const by = {};
  calls.forEach(c => { const k = c.purpose + "|" + c.model; by[k] = by[k] || {purpose: c.purpose, model: c.model, n: 0, fail: 0}; const g = by[k]; g.n++; if (!c.ok) g.fail++; });
  const unique = {};
  calls.filter(c => c.ok).forEach(c => unique[c.key] = c);
  const med = a => { const s = [...a].sort((x, y) => x - y); return s.length ? s[Math.floor(s.length / 2)] : 0; };
  const rows = Object.values(by).map(g => {
    const u = Object.values(unique).filter(c => c.purpose === g.purpose && c.model === g.model).map(c => c.ms);
    const range = u.length ? `${secs(Math.min(...u))} - ${secs(Math.max(...u))}` : "-";
    return `<tr><td>${th(PURPOSE_LABEL[g.purpose] || g.purpose)}</td><td><span class="pill llm">✦ ${esc(pretty(g.model))}</span></td><td>${g.n}</td><td>${u.length}</td><td><b>${esc(secs(med(u)))}</b></td><td class="mute">${esc(range)}</td><td>${g.fail}</td></tr>`;
  }).join("");
  const events = R.procedures.flatMap(P => P.events);
  const eng = e => String(e.engine || "");
  const fallbacks = events.filter(e => eng(e).startsWith("rule fallback")).length;
  const llmActs = events.filter(e => e.kind === "action" && isLLM(e.engine)).length;
  const guardActs = events.filter(e => ["action", "barrier", "handoff"].includes(e.kind) && (eng(e).startsWith("rule (guard)") || eng(e).startsWith("deterministic"))).length;
  const cmp = R.procedures.map(P => {
    const b = baselineFor(P.key);
    const stop = b ? b.barriers.find(x => x.status === "handoff") : null;
    const ruleCell = b ? (stop ? th("stopped at step {n}: {heard} → human", {n: stop.step, heard: q(stop.heard, pageLang(P))}) : esc(t(b.final))) : "–";
    return `<tr><td class="nw">${FLAG[P.key] ? `<span style="display:inline-block;width:1.4rem;vertical-align:-.15rem;margin-right:.4rem">${FLAG[P.key]}</span>` : ""}<b>${esc(procTitle(P.key))}</b></td><td><span class="no" aria-hidden="true">■</span> ${ruleCell}</td><td><span class="yes" aria-hidden="true">■</span> ${P.reached_confirmation ? th("reached confirmation") : esc(t(P.final))}${P.final === "handoff" ? " · " + th("CAPTCHA → human") : ""}</td></tr>`;
  }).join("");
  return `<div class="stats">
    <div class="stat llm"><b>${llmActs}</b><span>${th("keyboard actions chosen by the LLM")}</span></div>
    <div class="stat rule"><b>${guardActs}</b><span>${th("actions and stops by hard-coded guards")}</span></div>
    <div class="stat z"><b>${fallbacks}</b><span>${th("rule fallbacks (LLM failed)")}</span></div>
    <div class="stat ok"><b>${R.procedures.reduce((s, P) => s + P.barriers.filter(b => b.status === "fixed").length, 0)}</b><span>${th("fixes verified by replay")}</span></div></div>
  <div class="card"><h3>${th("LLM calls in this run")}</h3>
  <table><thead><tr><th>${th("Purpose")}</th><th>${th("Model")}</th><th>${th("Calls")}</th><th>${th("Unique")}</th><th>${th("Median latency")}</th><th>${th("Range")}</th><th>${th("Failed")}</th></tr></thead><tbody>${rows}</tbody></table></div>
  <div class="card"><h3>${th("Same pages, rule-only engine vs LLM engine")}</h3><table><thead><tr><th>${th("Procedure")}</th><th>${th("Rule-only engine")}</th><th>${th("LLM engine")}</th></tr></thead><tbody>${cmp}</tbody></table></div>`;
}

function captionFor(sc) {
  const ev = P_().events, a = ev[sc.at].attempt;
  const upto = ev.filter(e => e.attempt === a && e.i <= sc.at && e.kind === "hear" && e.focus !== null);
  if (sc.panel === "verified") {
    const h = [...upto].reverse().find(e => e.focus === sc.b.element_id);
    if (h) return {text: h.text, tone: "ok", meta: t("attempt {n} · after the fix", {n: a})};
  }
  if (["blocked", "fix", "approve"].includes(sc.panel) && sc.b) return {text: sc.b.heard || "(nothing)", tone: "bad", meta: t("attempt {n} · at the barrier", {n: sc.b.attempt || a})};
  if (sc.panel === "handoff" && sc.b) return {text: sc.b.heard, tone: "", meta: t("handed to a human")};
  const h = upto[upto.length - 1];
  return h ? {text: h.text, tone: "", meta: t("attempt {n} · step {s}", {n: a, s: h.step})} : {text: "", tone: "", meta: ""};
}

let frameRetry = 0;
function setFrame(P, e, shot) {
  const img = document.getElementById("frame");
  const screen = document.getElementById("screen");
  const fallback = () => {
    img.hidden = true;
    screen.querySelectorAll("iframe, .fallback-note").forEach(x => x.remove());
    const src = `portal/fixed/${P.key}/${P.steps[e.step - 1]}`;
    screen.insertAdjacentHTML("beforeend", `<iframe class="fallback" src="${src}" title="${esc(t("Mock portal page"))}" tabindex="-1"></iframe><span class="fallback-note">${th("mock page · recorded screenshot not found")}</span>`);
  };
  if (!shot) { fallback(); return; }
  if (img.dataset.shot === shot && img.classList.contains("ready") && !img.hidden) return;
  screen.querySelectorAll("iframe, .fallback-note").forEach(x => x.remove());
  img.hidden = false;
  img.dataset.shot = shot;
  frameRetry = 0;
  img.onload = () => img.classList.add("ready");
  img.onerror = () => {
    if (img.dataset.shot !== shot) return;
    if (frameRetry++ < 2) setTimeout(() => { if (img.dataset.shot === shot) img.src = shot + "?r=" + Date.now(); }, 400);
    else fallback();
  };
  img.classList.remove("ready");
  img.src = shot;
  if (img.complete && img.naturalWidth) img.classList.add("ready");
}

function stampFor(sc) {
  return {blocked: ["bad", "BLOCKED"], fix: ["llm", "FIX PROPOSED"], approve: sc.a ? (sc.a.approved ? ["ok", "APPROVED"] : ["bad", "REJECTED"]) : ["hum", "AWAITING HUMAN"], verified: ["ok", "VERIFIED ✓"], handoff: ["hum", "HUMAN HAND-OFF"], reached: ["ok", "GOAL REACHED"], read: ["llm", "LLM READS LABEL"]}[sc.panel];
}

function urlBar(folder, P, file) {
  return `${code(`${HOST}/${folder}/`)}<b>${code(`${P.key}/${file}`)}</b>`;
}

function render(animate = true) {
  if (!scenes.length || MODE !== "replay") return;
  cur = Math.max(0, Math.min(cur, scenes.length - 1));
  const sc = scenes[cur], P = P_(), ev = P.events, e = ev[sc.at];
  const changed = animate && lastRendered !== sc.key;
  const langChanged = lastLang !== LANG;
  lastRendered = sc.key;
  lastLang = LANG;
  const app = document.getElementById("app");
  app.classList.toggle("anim", changed);
  replayHeader();
  setRail(sc.stage);
  const wide = ["audit", "axe", "engine"].includes(sc.panel);
  document.getElementById("main").classList.toggle("wide", wide);
  const txt = sceneText(sc);
  document.getElementById("shead").innerHTML = sheadHtml(txt.title, txt.sub, whyHtml("why:" + sc.key, txt.why));
  if (!wide) {
    const shotEv = [...ev].reverse().find(x => x.i <= sc.at && x.shot) || ev.find(x => x.shot);
    setFrame(P, e, shotEv && shotEv.shot);
    document.getElementById("frameTag").textContent = t("attempt {a} · step {s}/{n}", {a: e.attempt, s: e.step, n: P.steps.length});
    document.getElementById("url").innerHTML = urlBar("portal/live", P, P.steps[e.step - 1]);
    const viewer = document.getElementById("viewer");
    viewer.className = "viewer" + ({blocked: " tone-bad", verified: " tone-ok", reached: " tone-ok", handoff: " tone-hum", approve: " tone-hum", fix: " tone-llm", read: " tone-llm"}[sc.panel] || "");
    setStamp(stampFor(sc));
    const cap = captionFor(sc);
    if (changed || langChanged || !typeTimer) setCaption(cap.text, cap.tone, t("{lang} · NVDA-style, from the accessibility tree · {meta}", {lang: P.lang, meta: cap.meta}), changed, P);
  }
  const panels = {
    listen: listenArt,
    read: () => replayFeed(sc) + readCard(sc),
    blocked: () => replayFeed(sc) + blockedCardHtml(sc.b, P) + blockedLLMHtml(sc.e.llm, P),
    fix: () => patchCardHtml(sc.e, P, false) + precheckCardHtml(sc.e),
    approve: () => patchCardHtml(sc.e, P, true) + approvalCard(sc),
    verified: () => replayFeed(sc) + verifiedCard(sc),
    handoff: () => replayFeed(sc) + handoffCardHtml(sc.b, P),
    reached: () => replayFeed(sc) + reachedCard(),
    audit: auditPanel, axe: axePanel, engine: enginePanel,
  };
  document.getElementById("panel").innerHTML = panels[sc.panel]();
  const tl = document.getElementById("tlCard");
  tl.hidden = wide;
  if (!wide) tl.innerHTML = replayTimeline(sc);
  trimFeed();
  replayFooter();
  const want = "#" + sc.key;
  if (location.hash !== want) history.replaceState(null, "", location.pathname + location.search + want);
  window.sceneKey = sc.key;
}
let lastLang = null;

function chapterDots(ch, curCh) {
  return ch.map((c, i) => `<button class="chap ${i === curCh ? "on" : ""}" data-i="${c.idx}" aria-current="${i === curCh}" title="${esc(`${i + 1} · ${c.label}`)}" aria-label="${esc(`${i + 1} · ${c.label}`)}"><i aria-hidden="true"></i><span>${esc(c.label)}</span></button>`).join("");
}

function replayFooter() {
  const ch = chapterList();
  const curCh = ch.reduce((a, c, i) => c.idx <= cur && (a < 0 || c.idx > ch[a].idx) ? i : a, -1);
  document.getElementById("chapters").innerHTML = chapterDots(ch, curCh);
  document.getElementById("ticks").innerHTML = scenes.map((s, i) => { const lb = sceneText(s).label; return `${i && s.p !== scenes[i - 1].p ? `<span class="gap"></span>` : ""}<button data-i="${i}" title="${esc(lb)}" aria-label="${esc(t("Scene {n}: {label}", {n: i + 1, label: lb}))}" class="${i === cur ? "on" : i < cur ? "seen" : ""}"></button>`; }).join("");
  document.getElementById("hint").innerHTML = `<b>${cur + 1}</b> / ${scenes.length} · ${th("← → step · Space play · 1–{n} chapters · L live run · G language", {n: ch.length})}`;
  document.getElementById("playState").textContent = playing ? t("▶ autoplay") : "";
}

let playing = false, playTimer = null;
const AUTO = parseFloat(params.get("auto") || "0");
function setPlaying(on, seconds) {
  playing = on;
  clearInterval(playTimer);
  if (on) playTimer = setInterval(() => {
    if (MODE !== "replay") return;
    if (cur >= scenes.length - 1) { setPlaying(false); window.autoDone = true; return; }
    cur++; render();
  }, (seconds || AUTO || 7) * 1000);
  if (scenes.length && MODE === "replay") replayFooter();
}

function go(i) { cur = Math.max(0, Math.min(scenes.length - 1, i)); render(); }

function sceneFromHash() {
  const i = scenes.findIndex(s => "#" + s.key === location.hash);
  return i;
}

function replayKey(ev) {
  if (!scenes.length) return false;
  const k = ev.key;
  const ch = chapterList();
  if (k === "ArrowRight" || k === "PageDown") go(cur + 1);
  else if (k === "ArrowLeft" || k === "PageUp") go(cur - 1);
  else if (k === "Home") go(0);
  else if (k === "End") go(scenes.length - 1);
  else if (k === " ") setPlaying(!playing);
  else if (/^[1-9]$/.test(k) && ch[+k - 1]) go(ch[+k - 1].idx);
  else return false;
  return true;
}

function initReplay() {
  if (!R) return false;
  scenes = buildScenes();
  cur = Math.max(0, sceneFromHash());
  return true;
}
