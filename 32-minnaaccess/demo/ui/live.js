const HTTP = location.protocol.startsWith("http");
const DUR = {restart: 900, hear: 420, heading: 650, action: 600, fill: 750, advisory: 1300, barrier: 1900, patch: 900, approval: 1100,
  pass: 650, verified: 2000, reached: 1500, handoff: 1900, precheck_fail: 1100, info: 500, warning: 900, llm_start: 150, llm_end: 450, done: 0, stopped: 0, error: 0};
const PURPOSE = {"interpret field": "Claude {model} is reading the field label", "write patch": "Claude {model} is writing a patch and a plain-language explanation"};
const HL = {focus: "#2563eb", llm: "#7c3aed", bad: "#e11d48", ok: "#0f9f8f", hum: "#d97706", plant: "#d97706"};

const L = {
  options: null, health: null, offline: false,
  cfg: {procedure: "vn", form: "original", barrier: "unnamed_field", target: null, llm: "cached", speed: 1},
  view: "setup", status: "idle", runId: null, since: 0, serverPending: null, result: null, error: null, busy: null,
  queue: [], feed: [], events: [], attempt: 0, step: 1, values: {}, highlight: null, current: null, stamp: null, stage: null,
  caption: {text: "", tone: "", meta: ""}, prepared: null, frameVersion: 0, playTimer: null, pollTimer: null, tickTimer: null,
  decisionSent: false, started: false, lastPollOk: true,
};
const urlSpeed = parseFloat(new URLSearchParams(location.search).get("speed") || "0");

function procMeta() { return L.options ? L.options.procedures[L.cfg.procedure] : null; }

async function api(path, body) {
  const opts = body === undefined ? {cache: "no-store"} : {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)};
  const r = await fetch(path, opts);
  let data = {};
  try { data = await r.json(); } catch (e) { data = {}; }
  if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}

async function liveInit() {
  if (!HTTP) { L.offline = "file"; return; }
  try {
    L.options = await api("/api/live/options");
    L.health = L.options.health;
    L.lastPollOk = true;
  } catch (e) {
    L.offline = "server";
    return;
  }
  const P = L.options.barriers[L.cfg.procedure];
  L.cfg.target = P.defaults[L.cfg.barrier];
  if (!L.health.claude_cli) L.cfg.llm = "cached";
  try {
    const st = await api("/api/live/state?since=0");
    if (st.run_id && st.events.length && ["starting", "running", "waiting"].includes(st.status)) {
      L.cfg = {...L.cfg, ...(st.config || {}), llm: (st.config && st.config.llm) === "live" ? "live" : "cached"};
      if (st.config && st.config.barrier) L.cfg.target = st.config.target;
      L.view = "run";
      absorbState(st, true);
    } else {
      await prepare();
    }
  } catch (e) {
    L.offline = "server";
  }
}

function speedFactor() { return urlSpeed > 0 ? urlSpeed : (L.cfg.speed || 1); }

function absorbState(st, instant) {
  L.status = st.status;
  L.runId = st.run_id;
  L.serverPending = st.pending;
  L.result = st.result;
  L.error = st.error;
  L.busy = st.llm_busy;
  if (st.prepared && st.prepared.procedure) L.prepared = st.prepared;
  L.since = st.next;
  st.events.forEach(e => L.queue.push(e));
  if (instant) { while (L.queue.length) consume(L.queue.shift(), true); }
}

function resetLocal() {
  clearTimeout(L.playTimer); L.playTimer = null;
  Object.assign(L, {queue: [], feed: [], events: [], attempt: 0, step: 1, values: {}, highlight: null, current: null, stamp: null, stage: null,
    caption: {text: "", tone: "", meta: ""}, since: 0, serverPending: null, result: null, error: null, busy: null, decisionSent: false, frameVersion: Date.now()});
}

let prepareChain = Promise.resolve();
let prepareSeq = 0;
function prepare() {
  const seq = ++prepareSeq;
  prepareChain = prepareChain.then(() => seq === prepareSeq ? doPrepare() : null);
  return prepareChain;
}

async function doPrepare() {
  if (L.offline) return;
  try {
    const r = await api("/api/live/prepare", cfgBody());
    L.prepared = r.prepared;
    L.frameVersion = Date.now();
    const inj = L.prepared.injected;
    L.step = inj ? inj.step : 1;
    L.highlight = inj ? {id: inj.element, tone: "plant"} : null;
    L.values = {};
    if (MODE === "live") renderLive();
  } catch (e) {
    toast(th("Could not prepare the mock portal: {msg}", {msg: ax(e.message)}), true);
  }
}

function cfgBody() {
  const b = {procedure: L.cfg.procedure, form: L.cfg.form, llm: L.cfg.llm === "live" ? "live" : "cached", pace: 0};
  if (L.cfg.form === "inject") { b.barrier = L.cfg.barrier; b.target = L.cfg.target; }
  return b;
}

async function startRun() {
  if (L.offline || ["starting", "running", "waiting"].includes(L.status)) return;
  await prepareChain;
  resetLocal();
  L.view = "run";
  L.status = "starting";
  L.started = true;
  renderLive();
  try {
    const r = await api("/api/live/start", cfgBody());
    L.runId = r.run_id;
  } catch (e) {
    L.status = "idle";
    L.view = "setup";
    toast(th("Could not start the run: {msg}", {msg: ax(e.message)}), true);
    renderLive();
    return;
  }
  schedulePoll(50);
}

async function stopRun() {
  try { await api("/api/live/stop", {}); } catch (e) { toast(th("Stop failed: {msg}", {msg: ax(e.message)}), true); }
  schedulePoll(50);
}

async function resetPortal() {
  try {
    await api("/api/live/reset", {});
  } catch (e) {
    toast(th("Reset failed: {msg}", {msg: ax(e.message)}), true);
    return;
  }
  resetLocal();
  L.status = "idle";
  L.runId = null;
  L.view = "setup";
  L.cfg.form = "original";
  toast(th("Mock portal restored to the original pages."));
  await prepare();
  renderLive();
}

async function decideLive(approved) {
  const p = visiblePending();
  if (!p || L.decisionSent) return;
  L.decisionSent = true;
  renderLive(false);
  try {
    await api("/api/live/decision", {approved, run_id: L.runId, seq: p.seq});
  } catch (e) {
    L.decisionSent = false;
    toast(th("Decision not delivered: {msg}", {msg: ax(e.message)}), true);
    renderLive(false);
    return;
  }
  schedulePoll(30);
}

function schedulePoll(ms) {
  clearTimeout(L.pollTimer);
  L.pollTimer = setTimeout(pollLive, ms);
}

async function pollLive() {
  if (MODE !== "live" || L.offline) return;
  const active = ["starting", "running", "waiting"].includes(L.status);
  try {
    const st = await api(`/api/live/state?since=${L.since}`);
    if (!L.lastPollOk) { L.lastPollOk = true; toast(th("Server connection restored.")); }
    if (st.run_id && L.runId && st.run_id !== L.runId) { resetLocal(); L.runId = st.run_id; }
    if (st.run_id || active) {
      const wasPending = !!L.serverPending;
      absorbState(st, false);
      if (!!L.serverPending !== wasPending) { if (!L.serverPending) L.decisionSent = false; renderLive(false); }
      if (!L.playTimer) playNext();
    }
  } catch (e) {
    if (L.lastPollOk) toast(th("Lost connection to the local server. Is {cmd} still running? Replay mode still works.", {cmd: code("start_demo.py")}), true);
    L.lastPollOk = false;
  }
  schedulePoll(["starting", "running", "waiting"].includes(L.status) || L.queue.length ? 350 : 2000);
}

function playNext() {
  clearTimeout(L.playTimer);
  L.playTimer = null;
  if (!L.queue.length) { renderLive(false); return; }
  const e = L.queue.shift();
  const d = consume(e, false);
  renderLive(true);
  L.playTimer = setTimeout(playNext, Math.max(0, d / speedFactor()));
}

function feedPush(item) {
  L.feed.push(item);
  if (L.feed.length > 40) L.feed.splice(0, L.feed.length - 40);
}

function consume(e, instant) {
  if (e.kind === "info") { feedPush({kind: "sys", text: e.text, label: "Agent"}); return DUR.info; }
  if (e.kind === "warning") { feedPush({kind: "warn", text: e.text, label: "Fallback"}); if (!instant) toast(ax(e.text)); return DUR.warning; }
  if (e.kind === "llm_start") {
    L.current = {type: "thinking", model: e.model, purpose: e.purpose, since: e.t};
    if (e.purpose === "write patch") L.stage = "llm";
    return DUR.llm_start;
  }
  if (e.kind === "llm_end") {
    if (L.current && L.current.type === "thinking") L.current = null;
    feedPush(e.ok ? {kind: "sys", labelHtml: esc(`Claude ${pretty(e.model)}`), html: th("Answered in {s} (live call)", {s: esc(secs(e.ms))})} : {kind: "warn", label: "LLM call failed", html: th("{error}. Falling back to the cached answer or the rule engine.", {error: e.error ? code(String(e.error).slice(0, 140)) : th("no answer")})});
    return DUR.llm_end;
  }
  if (e.kind === "done") {
    const rej = e.summary && e.summary.final === "rejected";
    L.status = "done"; L.result = e.summary; L.current = {type: "result", summary: e.summary}; L.stage = rej ? "human" : "verified"; finalStamp(e.summary);
    if (!rej) L.highlight = null;
    return 0;
  }
  if (e.kind === "stopped") { L.status = "stopped"; L.current = {type: "stopped", text: e.text}; L.stamp = ["info", "STOPPED"]; return 0; }
  if (e.kind === "error") { L.status = "error"; L.current = {type: "error", text: e.text}; L.stamp = ["bad", "AGENT ERROR"]; if (!instant) toast(ax(e.text), true); return 0; }
  if (e.kind !== "agent") return 0;
  const ev = e.ev;
  L.events.push(ev);
  const key = `${ev.attempt}:${ev.step}`;
  switch (ev.kind) {
    case "restart":
      L.attempt = ev.attempt; L.step = 1; L.frameVersion = `${L.runId}-${ev.attempt}`; L.highlight = null; L.stamp = ev.attempt > 1 ? ["info", "RESTART · ATTEMPT {n}", {n: ev.attempt}] : null;
      L.stage = ev.attempt > 1 ? "restart" : "listen"; L.current = null;
      feedPush(ev);
      return DUR.restart;
    case "hear":
      if (ev.page) { L.step = ev.step; L.stamp = L.stamp && L.stamp[1].startsWith("RESTART") ? L.stamp : null; }
      if (ev.focus) L.highlight = {id: ev.focus, tone: "focus"};
      if (!String(ev.text).startsWith("(focus left")) L.caption = {text: ev.text, tone: "", meta: ["attempt {n} · step {s}", {n: ev.attempt, s: ev.step}]};
      if (L.stage !== "restart" || !ev.page) L.stage = L.attempt > 1 && L.stage === "restart" ? "restart" : (L.events.some(x => x.kind === "action") ? "navigate" : "listen");
      feedPush(ev);
      return ev.page ? DUR.heading : DUR.hear;
    case "action": {
      L.values[key] = L.values[key] || {};
      if (ev.op === "fill") L.values[key][ev.focus] = ev.value;
      if (ev.op === "press" && ev.value === "Space") L.values[key][ev.focus] = true;
      if (ev.focus) L.highlight = {id: ev.focus, tone: isLLM(ev.engine) ? "llm" : "focus"};
      L.stage = "navigate";
      if (isLLM(ev.engine) && ev.llm) L.current = {type: "read", ev};
      else if (L.current && L.current.type === "read") L.current = null;
      feedPush(ev);
      return ev.op === "fill" ? (isLLM(ev.engine) ? DUR.fill * 1.6 : DUR.fill) : DUR.action;
    }
    case "advisory": feedPush(ev); return DUR.advisory;
    case "barrier":
      L.current = {type: "blocked", ev}; L.highlight = {id: ev.barrier.element_id, tone: "bad"}; L.stamp = ["bad", "BLOCKED"]; L.stage = "blocked";
      L.caption = {text: ev.barrier.heard, tone: "bad", meta: ["attempt {n} · at the barrier", {n: ev.attempt}]};
      feedPush(ev);
      return DUR.barrier;
    case "precheck_fail": feedPush(ev); return DUR.precheck_fail;
    case "patch":
      L.current = {type: "patch", ev}; L.stamp = ["llm", "FIX PROPOSED"]; L.stage = "llm"; L.decisionSent = false;
      return DUR.patch;
    case "approval":
      L.current = {type: "approval", ev}; L.stamp = ev.approved ? ["ok", "APPROVED"] : ["bad", "REJECTED"]; L.stage = "human"; L.decisionSent = false;
      feedPush(ev);
      return DUR.approval;
    case "pass": L.stage = "navigate"; feedPush(ev); return DUR.pass;
    case "verified":
      L.current = {type: "verified", ev}; L.highlight = {id: ev.barrier.element_id, tone: "ok"}; L.stamp = ["ok", "VERIFIED ✓"]; L.stage = "verified";
      feedPush(ev);
      return DUR.verified;
    case "reached":
      L.stamp = ["ok", "GOAL REACHED"]; L.stage = "verified"; L.step = ev.step;
      feedPush(ev);
      return DUR.reached;
    case "handoff":
      L.current = {type: "handoff", ev}; L.highlight = {id: ev.focus || (ev.barrier && ev.barrier.element_id), tone: "hum"}; L.stamp = ["hum", "HUMAN HAND-OFF"]; L.stage = "verified";
      feedPush(ev);
      return DUR.handoff;
    default:
      return 0;
  }
}

function finalStamp(s) {
  if (!s) return;
  if (s.final === "rejected") L.stamp = ["bad", "PATCH REJECTED"];
  else if (s.final === "handoff") L.stamp = ["hum", "HUMAN HAND-OFF"];
  else if (s.reached) L.stamp = ["ok", "GOAL REACHED"];
  else L.stamp = ["info", "RUN FINISHED"];
}

function visiblePending() {
  const p = L.serverPending;
  if (!p || !L.current || L.current.type !== "patch") return null;
  const ev = L.current.ev;
  return p.attempt === ev.attempt && p.element === ev.focus ? p : null;
}

function liveHeader() {
  const running = ["starting", "running", "waiting"].includes(L.status);
  document.getElementById("procs").innerHTML = Object.values(L.options ? L.options.procedures : {vn: {key: "vn", title: ""}, jp: {key: "jp", title: ""}}).map(p =>
    `<button class="proc ${L.cfg.procedure === p.key ? "on" : ""}" data-proc="${p.key}" title="${esc(procTitle(p.key))}" aria-pressed="${L.cfg.procedure === p.key}" ${running ? "disabled" : ""}>${FLAG[p.key] || ""}<span>${esc(procShort(p.key))}</span></button>`).join("");
  if (L.offline) { document.getElementById("hdr").innerHTML = `<span class="chip warn"><i></i>${th("Live run needs the local server")}</span>`; fitHeader(); return; }
  const mode = L.cfg.llm === "live" ? `<span class="chip llm" data-prio="2"><i></i>${th("Live Claude calls")}</span>` : `<span class="chip ok" data-prio="2"><i></i>${th("Cached LLM replies · offline")}</span>`;
  const st = L.status === "waiting" && visiblePending() ? `<span class="chip warn" data-prio="3"><i></i>${th("Waiting for your decision")}</span>`
    : running ? `<span class="chip live" data-prio="3"><i></i>${th("LIVE RUN")}</span>` : L.status === "done" ? `<span class="chip ok" data-prio="1"><i></i>${th("Run finished")}</span>` : "";
  document.getElementById("hdr").innerHTML = `<span class="chip llm" data-prio="0"><i></i>LLM · Haiku 4.5 + Sonnet 5.5</span>${mode}${st}`;
  fitHeader();
}

function liveFooter() {
  document.getElementById("chapters").innerHTML = "";
  document.getElementById("ticks").innerHTML = "";
  document.getElementById("playState").textContent = "";
  document.getElementById("progBar").style.width = "0";
  const h = L.health || {};
  const chip = (ok, label) => `<span class="chip ${ok ? "ok" : "warn"}"><i></i>${label}</span>`;
  const running = ["starting", "running", "waiting"].includes(L.status);
  const busyFor = L.busy ? Math.max(0, Math.round(Date.now() / 1000 - L.busy.since)) : 0;
  document.getElementById("ticks").innerHTML = L.offline ? "" : `<div class="status">${chip(true, th("Local server"))}${chip(h.chromium !== false, h.chromium === false ? th("Chromium missing") : "Chromium")}${chip(h.claude_cli, h.claude_cli ? "Claude CLI" : th("Claude CLI not found"))}${running && L.busy ? `<span class="chip llm"><i></i>${th("Claude call {s} s", {s: busyFor})}</span>` : ""}${L.runId ? `<span class="mute">${th("run {id} · saved to {dir}", {id: esc(L.runId), dir: code("runs/live/")})}</span>` : ""}</div>`;
  const B = {b: "<b>", "/b": "</b>"};
  document.getElementById("hint").innerHTML = `${visiblePending() ? th("{b}A{/b} approve · {b}R{/b} reject", B) + " · " : ""}${running ? th("{b}Esc{/b} stop", B) + " · " : ""}${th("{b}L{/b} replay · {b}G{/b} language", B)}`;
}

const SEG_NAME = {procedure: "Procedure", form: "Start from", llm: "LLM answers", speed: "Speed", barrier: "Barrier"};

function seg(name, value, items, disabled) {
  return `<div class="seg" role="group" aria-label="${esc(t(SEG_NAME[name] || name))}">${items.map(([v, label, small, dis]) => `<button type="button" data-set="${name}" data-v="${v}" aria-pressed="${value === v}" ${disabled || dis ? "disabled" : ""}>${label}${small ? ` <small>${esc(small)}</small>` : ""}</button>`).join("")}</div>`;
}

function targetName(P, x) {
  if (x.id.startsWith("step")) return stepName(P.key, x.step);
  return labelPlain(x.name, pageLang(P)) || `#${x.id}`;
}

function setupPanel() {
  if (L.offline) {
    const why = L.offline === "file" ? th("This page was opened from disk, so it cannot start the agent.") : th("The local server does not answer.");
    return `<div class="card humc grow"><h3>${th("Live run needs the local server")}</h3><p class="big">${why}</p>
      <p class="note">${th("Start it with {cmd} in the demo folder, then open {url}. The recorded replay (key {b}L{/b}) works without it.", {cmd: `<b>${code("python start_demo.py")}</b>`, url: `<b>${code("http://127.0.0.1:8765/dashboard.html#live")}</b>`, b: "<b>", "/b": "</b>"})}</p></div>`;
  }
  const O = L.options, B = O.barriers[L.cfg.procedure], P = procMeta();
  const inj = L.cfg.form === "inject";
  const targets = B.targets[L.cfg.barrier] || [];
  const kind = B.kinds.find(k => k.id === L.cfg.barrier);
  const tg = targets.find(x => x.id === L.cfg.target) || targets[0];
  const live = L.health.claude_cli;
  const planted = L.prepared && L.prepared.injected;
  const plantedOn = planted && planted.target_name && !String(planted.target).startsWith("step") ? `: ${q(planted.target_name, pageLang(P))}` : "";
  return `<div class="setup">
    <div class="card"><h3>▶ ${th("Run the agent now")} <span class="sp"><span class="pill g">${th("real Chromium · keyboard only · local mock")}</span></span></h3>
      <div class="row"><span class="lbl">${th("Procedure")}</span>${seg("procedure", L.cfg.procedure, Object.values(O.procedures).map(p => [p.key, `${FLAG[p.key]} ${esc(procShort(p.key))}`, t("{n} steps", {n: p.steps.length})]))}</div>
      <div class="row"><span class="lbl">${th("Start from")}</span>${seg("form", L.cfg.form, [["original", th("Original mock"), t("planted barriers")], ["inject", th("Try it yourself"), t("clean form + 1 barrier")]])}</div>
      <div class="row"><span class="lbl">${th("LLM answers")}</span>${seg("llm", L.cfg.llm, [["cached", th("Cached replies"), t("offline")], ["live", th("Live Claude calls"), live ? t("10–50 s each") : t("CLI not found"), !live]])}</div>
      <div class="row"><span class="lbl">${th("Speed")}</span>${seg("speed", String(L.cfg.speed), [["1", th("Stage"), "1×"], ["3", th("Fast"), "3×"]])}</div>
      <div class="go"><button class="runbtn" id="runBtn" data-act="run">▶ ${th("Run agent now")}</button><button class="ghost" data-act="reset" title="${esc(t("Restore the original mock portal"))}">↺ ${th("Reset portal")}</button></div></div>
    <div class="card ${inj ? "" : "dimmed"}"><h3>🧪 ${th("Try it yourself: plant one barrier")} ${inj ? "" : `<span class="sp"><span class="pill g">${th("choose “Try it yourself” above")}</span></span>`}</h3>
      <div class="row"><span class="lbl">${th("Barrier")}</span>${seg("barrier", L.cfg.barrier, B.kinds.map(k => [k.id, th(k.short), "WCAG " + k.sc]), !inj).replace('class="seg"', 'class="seg kinds"')}</div>
      <div class="row"><label for="targetSel">${th("Where")}</label><select class="sel" id="targetSel" ${inj ? "" : "disabled"}>${targets.map(x => `<option value="${esc(x.id)}" ${tg && x.id === tg.id ? "selected" : ""}>${esc(x.id.startsWith("step") ? t("Step {n} · {step}", {n: x.step, step: stepName(P.key, x.step)}) : t("Step {n} · {step} · {name}", {n: x.step, step: stepName(P.key, x.step), name: targetName(P, x)}))}${x.id.startsWith("step") ? "" : ` (#${esc(x.id)})`}</option>`).join("")}</select></div>
      ${inj && kind ? `<div class="planted"><span>⚑</span><span>${th("{b}{label}{/b} (WCAG {sc}){where}. {what} The agent is not told where it is.", {b: "<b>", "/b": "</b>", label: esc(t(kind.label)), sc: esc(kind.sc), where: planted ? " " + th("planted on step {n}", {n: planted.step}) + plantedOn : "", what: th(kind.what)})}</span></div>` : ""}</div>
  </div>`;
}

function thinkLine(s) {
  return th("{s} s · live call through the claude CLI (timeout 90 s, then cached answer or rule engine)", {s});
}

function thinkingCard(c) {
  const s = Math.max(0, Math.round(Date.now() / 1000 - c.since));
  return `<div class="card llmc"><div class="think"><span class="orb" aria-hidden="true"></span><div><b>✦ ${th(PURPOSE[c.purpose] || "Claude {model} is thinking", {model: esc(pretty(c.model))})}…</b><span id="thinkSecs">${thinkLine(s)}</span></div></div></div>`;
}

const CHECK_SHORT = {"Target element still present": "Target element still present", "Accessibility tree: accessible name matches the visible label": "accessible name matches the visible label",
  "Keyboard replay: Tab leaves the field": "Tab leaves the field", "Keyboard replay: element takes focus with role button": "element takes focus with role button",
  "Keyboard replay: Enter activates it": "Enter activates it", "axe-core: no rule fails on this element": "no rule fails on this element"};

function prechecksInline(check) {
  if (!check) return "";
  return `<div class="seg" style="margin:.2rem 0 .8rem">${check.checks.map(c => `<span class="pill ${c.passed ? "ok" : "bad"}" title="${esc(c.detail)}">${c.passed ? "✓" : "✗"} ${CHECK_SHORT[c.name] ? th(CHECK_SHORT[c.name]) : checkName(c.name)}</span>`).join("")}</div>`;
}

function decisionCard(ev) {
  const p = visiblePending();
  const ok = ev.precheck && ev.precheck.passed;
  const head = `<h3>✋ ${th("Your decision")} <span class="sp"><span class="pill ${ok ? "ok" : "bad"}">${ok ? th("pre-check passed") : th("pre-check failed")}</span>${p ? `<span class="pill hum waiting">${th("waiting for you")}</span>` : ""}</span></h3>${prechecksInline(ev.precheck)}`;
  if (!p) return `<div class="card humc">${head}<div class="decide"><button class="btn yes" disabled>✓ ${th("Approve")}</button><button class="btn no" disabled>✗ ${th("Reject")}</button></div><div class="whoapp">${th("Waiting for the agent to hand over the patch…")}</div></div>`;
  const dis = L.decisionSent ? "disabled" : "";
  return `<div class="card humc">${head}<div class="decide"><button class="btn yes" data-act="approve" ${dis}>✓ ${th("Approve")} <kbd>A</kbd></button><button class="btn no" data-act="reject" ${dis}>✗ ${th("Reject")} <kbd>R</kbd></button></div>
    <div class="whoapp">${L.decisionSent ? th("Sending your decision…") : th("Approve → written to the local mock portal, then the agent restarts from step 1. Reject → nothing changes; the barrier goes to a human.")}</div></div>`;
}

function approvalResultCard(ev) {
  return `<div class="card humc"><h3>✋ ${th("Human decision")} <span class="sp"><span class="pill g">${WHO.includes(ev.who) ? th(ev.who) : esc(ev.who)}</span></span></h3>
    <div class="decide"><button class="btn yes ${ev.approved ? "chosen" : "dim"}" disabled>✓ ${ev.approved ? th("Approved") : th("Approve")}</button><button class="btn no ${ev.approved ? "dim" : "chosen"}" disabled>✗ ${ev.approved ? th("Reject") : th("Rejected")}</button></div>
    <div class="whoapp">${ev.approved ? th("Patch written to the mock portal. The agent now restarts the whole procedure from step 1.") : th("Not applied. The barrier stays open and goes to a human officer.")}</div></div>`;
}

function patchRecordFor(id) {
  return [...L.events].reverse().find(e => e.kind === "patch" && e.focus === id);
}

const STATUS_TEXT = {fixed: "fixed ✓ verified", handoff: "→ human", rejected: "rejected", approved: "approved", "approved, not re-verified": "approved, not re-verified"};

function resultCard(s) {
  const P = procMeta();
  const axeRows = s.axe ? s.axe.comparison : [];
  const axeN = axeRows.filter(r => r.axe).length;
  const verdict = s.final === "rejected" ? th("Patch rejected: the barrier stays open and goes to a human officer.")
    : s.final === "handoff" ? (s.barriers.some(b => b.kind === "captcha" && b.status === "handoff") ? th("Stopped at a CAPTCHA: handed to a human. Never bypassed.") : th("Stopped at a field it could not read: handed to a human. Never bypassed."))
    : s.reached ? th("Confirmation step reached by keyboard only. The submit button was never pressed.") : th("Run ended: {final}.", {final: esc(t(s.final))});
  const rows = s.barriers.map(b => {
    const a = axeRows.find(r => r.element === b.element_id && r.step === b.step);
    return `<tr><td class="nw">${th("Step {n}", {n: b.step})}</td><td>${esc(kindName(b.kind))} ${code("#" + b.element_id)}</td><td class="nw">WCAG ${esc(b.sc)}</td><td class="nw ${b.status === "fixed" ? "yes" : b.status === "rejected" ? "no" : ""}">${th(STATUS_TEXT[b.status] || b.status)}</td><td class="nw">${a ? (a.axe ? `<span class="yes">✓</span> ${code(a.axe_rules.join(", "))}` : `<span class="no">✗ ${th("missed")}</span>`) : "–"}</td></tr>`;
  }).join("");
  return `<div class="card okc result grow" style="justify-content:flex-start"><h3 style="color:var(--ok)">${th("Run result · {title}", {title: esc(procTitle(P.key))})} <span class="sp"><span class="pill g">${s.llm_mode === "live" ? th("live Claude calls") : th("cached LLM replies")}</span></span></h3>
    <p class="big" style="margin-bottom:.8rem">${verdict}</p>
    <div class="stats"><div class="stat"><b>${s.attempts}</b><span>${th("attempts, each from step 1")}</span></div><div class="stat ok"><b>${s.fixed}</b><span>${th("fixed and verified by replay")}</span></div><div class="stat z"><b>${s.handoff + s.rejected}</b><span>${th("left to a human")}</span></div><div class="stat"><b style="color:var(--ok)">${esc(yesNo(s.submitted))}</b><span>${th("form submitted")}</span></div></div>
    ${rows ? `<table style="margin-top:.8rem"><thead><tr><th>${th("Step")}</th><th>${th("Barrier found by the agent")}</th><th>${th("Criterion")}</th><th>${th("Outcome")}</th><th>${th("axe-core, same start page")}</th></tr></thead><tbody>${rows}</tbody></table>` : `<p class="note">${th("No blocking barrier found.")}</p>`}
    ${s.axe ? `<p class="note">${th("axe-core 4.10.2 on the same starting pages found {n} of {total} blocking barrier(s) the agent found.", {n: axeN, total: axeRows.length})}</p>` : ""}
    <div class="go"><button class="runbtn" data-act="run">▶ ${th("Run again")}</button><button class="ghost" data-act="setup">⚙ ${th("Change setup")}</button><button class="ghost" data-act="reset">↺ ${th("Reset portal")}</button></div></div>`;
}

function runBar() {
  const running = ["starting", "running", "waiting"].includes(L.status);
  const inj = L.prepared && L.prepared.injected;
  const label = L.cfg.form === "inject" && inj ? th("Try it yourself · {label} on step {n}", {label: esc(t(inj.label)), n: inj.step}) : L.cfg.form === "inject" ? th("Try it yourself") : th("Original mock · planted barriers");
  return `<div class="runbar"><div class="grow1"><span class="pill ${running ? "bad" : "g"}">${running ? "● " + th("running") : th(L.status)}</span><span class="pill g">${label}</span></div>
    ${running ? `<button class="ghost bad" data-act="stop">■ ${th("Stop")} <kbd style="font-size:.7rem">Esc</kbd></button>` : `<button class="ghost" data-act="setup">⚙ ${th("Setup")}</button>`}<button class="ghost" data-act="reset">↺ ${th("Reset portal")}</button></div>`;
}

function liveFeedHtml(P) {
  const tail = L.feed.slice(-14);
  return `<div class="feed" id="feed" aria-label="${esc(t("Live agent log"))}">${tail.map((e, i) => feedItem(e, i >= tail.length - 2, P)).join("")}</div>`;
}

function currentCard(P) {
  const c = L.current;
  if (!c) return "";
  if (c.type === "thinking") return thinkingCard(c);
  if (c.type === "read") return readCardHtml(c.ev.llm, false, P);
  if (c.type === "blocked") return blockedCardHtml(c.ev.barrier, P) + blockedLLMHtml(c.ev.llm, P);
  if (c.type === "patch") return patchCardHtml(c.ev, P, false, true) + decisionCard(c.ev);
  if (c.type === "approval") return approvalResultCard(c.ev);
  if (c.type === "verified") {
    const rec = patchRecordFor(c.ev.barrier.element_id);
    return verifiedCardHtml(c.ev.barrier, P, c.ev.attempt, rec ? {precheck: rec.precheck, patch_engine: rec.engine} : null, null);
  }
  if (c.type === "handoff") return handoffCardHtml(c.ev.barrier, P, "no");
  if (c.type === "result") return resultCard(c.summary);
  if (c.type === "stopped") return `<div class="card grow"><h3>■ ${th("Run stopped")}</h3><p class="big">${ax(c.text)}</p><div class="go"><button class="runbtn" data-act="run">▶ ${th("Run again")}</button><button class="ghost" data-act="setup">⚙ ${th("Setup")}</button><button class="ghost" data-act="reset">↺ ${th("Reset portal")}</button></div></div>`;
  if (c.type === "error") return `<div class="card badc grow"><h3>${th("Agent error")}</h3><p class="big">${ax(c.text)}</p><p class="note">${th("Nothing was submitted. The recorded replay (key L) is unaffected.")}</p><div class="go"><button class="runbtn" data-act="run">▶ ${th("Try again")}</button><button class="ghost" data-act="reset">↺ ${th("Reset portal")}</button></div></div>`;
  return "";
}

function liveShead(P) {
  const country = P ? procCountry(P.key) : "";
  let kicker = th("Live run"), title = th("Run the agent now on the local mock portal"), sub = th("A real Playwright + Chromium run, keyboard only, driven by the screen-reader view. You approve or reject every patch."), tone = TONE.listen;
  if (L.offline) { title = th("Live run is not available here"); sub = th("Open the page through {cmd} to run the agent.", {cmd: code("python start_demo.py")}); }
  else if (L.view === "run") {
    const c = L.current;
    const s = L.attempt ? th("Attempt {a} · step {s}/{n}", {a: L.attempt, s: L.step, n: P.steps.length}) : th("Starting Chromium…");
    tone = TONE[L.stage] || TONE.listen;
    title = L.status === "starting" && !L.attempt ? th("Starting the agent…") : th("Walking step {n}: {name}", {n: L.step, name: esc(stepName(P.key, L.step))});
    sub = th("{s} · Tab, Space, Enter and typing only · local mock, nothing is submitted.", {s});
    if (c && c.type === "thinking") { title = th(PURPOSE[c.purpose] || "Claude {model} is thinking", {model: esc(pretty(c.model))}); tone = TONE.llm; }
    if (c && c.type === "read") { title = th("LLM reads {heard}", {heard: c.ev.llm.heard ? q(c.ev.llm.heard, pageLang(P)) : th("(no name)")}); sub = lx(c.ev.llm.output.field_meaning); tone = TONE.llm; kicker = th("Live run · LLM reads a label"); }
    if (c && c.type === "blocked") { const b = c.ev.barrier; title = th("Blocked at step {n}: {kind}", {n: b.step, kind: esc(kindName(b.kind))}); sub = th("Attempt {a} · WCAG {sc} {title} (Level {l}) on {id}", {a: c.ev.attempt, sc: esc(b.sc), title: esc(scTitle(b.sc, b.sc_title)), l: esc(b.level), id: code("#" + b.element_id)}); kicker = th("Live run · blocked"); }
    if (c && c.type === "patch") { title = visiblePending() ? th("Approve the fix for {id}?", {id: code("#" + c.ev.focus)}) : th(isLLM(c.ev.engine) ? "LLM proposes a fix for {id}" : "Rule engine proposes a fix for {id}", {id: code("#" + c.ev.focus)}); sub = th("Pre-checked on a staging copy. Nothing is applied until you decide."); tone = TONE.human; kicker = th("Live run · human approves"); }
    if (c && c.type === "approval") { title = c.ev.approved ? th("Approved: patch written, restarting from step 1") : th("Rejected: nothing applied"); tone = TONE.human; }
    if (c && c.type === "verified") { title = th("Restarted from step 1 · {id} verified", {id: code("#" + c.ev.barrier.element_id)}); sub = th("Attempt {a} · judged by keyboard replay, the accessibility tree and axe-core. The LLM does not grade its own fix.", {a: c.ev.attempt}); tone = TONE.verified; kicker = th("Live run · verified"); }
    if (c && c.type === "handoff") { title = th("{kind} → hand off to a human", {kind: esc(kindName(c.ev.barrier.kind))}); sub = th("Never bypassed. The submit button is never pressed."); tone = TONE.human; }
    if (c && c.type === "result") { title = th("Run finished"); sub = th("{n} attempt(s) · saved to {dir} · recorded replay untouched.", {n: L.result ? L.result.attempts : "", dir: code(L.result ? L.result.folder : "runs/live")}); tone = TONE.verified; kicker = th("Live run · result"); }
    if (c && c.type === "stopped") { title = th("Run stopped"); tone = TONE.human; }
    if (c && c.type === "error") { title = th("The agent hit an error"); tone = TONE.blocked; }
  } else if (L.cfg.form === "inject") {
    kicker = th("Try it yourself"); tone = TONE.blocked;
    title = th("Plant a barrier, then let the agent find it");
    sub = th("Pick a barrier and where it goes. The page on the left already contains it. The agent starts at step 1 without knowing where it is.");
  }
  document.getElementById("shead").innerHTML = `<div class="kicker" style="--tone:${tone}"><i></i>${kicker}${country ? " · " + esc(country) : ""}</div><h2>${title}</h2><p>${sub}</p>`;
}

function liveViewer(P) {
  const screen = document.getElementById("screen");
  const img = document.getElementById("frame");
  img.hidden = true;
  screen.querySelectorAll("iframe.fallback, .fallback-note").forEach(x => x.remove());
  const viewer = document.getElementById("viewer");
  const c = L.current;
  const tone = c ? ({blocked: " tone-bad", verified: " tone-ok", handoff: " tone-hum", patch: " tone-hum", approval: " tone-hum", read: " tone-llm", thinking: " tone-llm", result: L.result && L.result.final === "rejected" ? " tone-bad" : L.result && L.result.final === "handoff" ? " tone-hum" : " tone-ok"}[c.type] || "") : (L.highlight && L.highlight.tone === "plant" ? " tone-hum" : "");
  viewer.className = "viewer" + tone;
  if (L.offline || !P) {
    screen.querySelectorAll(".curtain").forEach(x => x.remove());
    screen.insertAdjacentHTML("beforeend", `<div class="curtain">${th("Start {cmd} to see the live mock portal here", {cmd: code("python start_demo.py")})}</div>`);
    document.getElementById("url").textContent = t("no local server");
    document.getElementById("frameTag").textContent = "";
    setStamp(null);
    return;
  }
  screen.querySelectorAll(".curtain").forEach(x => x.remove());
  const file = P.steps[Math.max(0, Math.min(P.steps.length, L.step) - 1)];
  document.getElementById("url").innerHTML = urlBar("portal/sandbox", P, file);
  document.getElementById("frameTag").textContent = L.view === "run" && L.attempt ? t("attempt {a} · step {s}/{n}", {a: L.attempt, s: L.step, n: P.steps.length}) : (L.prepared && L.prepared.injected ? t("barrier planted") : t("ready"));
  ensureFrame(P, file);
  setStamp(L.view === "setup" ? (L.prepared && L.prepared.injected && L.cfg.form === "inject" ? ["hum", "PLANTED BARRIER"] : null) : L.stamp);
}

function ensureFrame(P, file) {
  const screen = document.getElementById("screen");
  let f = screen.querySelector("iframe.livef");
  if (!f) {
    screen.insertAdjacentHTML("afterbegin", `<iframe class="livef" title="Live mock portal, view only" tabindex="-1" aria-hidden="true"></iframe>`);
    f = screen.querySelector("iframe.livef");
    f.addEventListener("load", () => {
      f.dataset.loaded = f.dataset.cur;
      f.dataset.busy = "";
      if (f.dataset.want !== f.dataset.cur) loadFrame(f);
      else applyFrameState();
    });
  }
  const src = `portal/sandbox/${P.key}/${file}?v=${encodeURIComponent(L.frameVersion)}`;
  scaleFrame();
  if (f.dataset.want !== src) { f.dataset.want = src; if (!f.dataset.busy) loadFrame(f); }
  else applyFrameState();
}

function loadFrame(f) {
  f.dataset.busy = "1";
  f.dataset.cur = f.dataset.want;
  f.src = f.dataset.want;
}

function scaleFrame() {
  const screen = document.getElementById("screen");
  const f = screen.querySelector("iframe.livef");
  if (!f) return;
  const W = 900, s = screen.clientWidth / W;
  f.style.width = W + "px";
  f.style.height = Math.ceil(screen.clientHeight / s) + "px";
  f.style.transform = `scale(${s})`;
}

const FRAME_CSS = `.ma-hl{outline:4px solid var(--ma)!important;outline-offset:3px!important;box-shadow:0 0 0 9px color-mix(in srgb,var(--ma) 22%,transparent)!important;border-radius:4px}
.ma-plant{outline:4px dashed var(--ma)!important;outline-offset:4px!important}
*{scroll-behavior:smooth}`;

function applyFrameState() {
  const f = document.querySelector("#screen iframe.livef");
  if (!f || f.dataset.busy || f.dataset.loaded !== f.dataset.want) return;
  let doc;
  try { doc = f.contentDocument; } catch (e) { return; }
  if (!doc || !doc.body) return;
  if (!doc.getElementById("ma-style")) { const st = doc.createElement("style"); st.id = "ma-style"; st.textContent = FRAME_CSS; doc.head.appendChild(st); }
  const vals = L.values[`${L.attempt}:${L.step}`] || {};
  Object.entries(vals).forEach(([id, v]) => { const el = doc.getElementById(id); if (!el) return; if (el.type === "checkbox") el.checked = !!v; else el.value = v; });
  doc.querySelectorAll(".ma-hl,.ma-plant").forEach(el => el.classList.remove("ma-hl", "ma-plant"));
  const h = L.highlight;
  if (h && h.id) {
    const el = doc.getElementById(h.id);
    if (el) {
      el.style.setProperty("--ma", HL[h.tone] || HL.focus);
      el.classList.add(h.tone === "plant" ? "ma-plant" : "ma-hl");
      const r = el.getBoundingClientRect();
      const vh = f.contentWindow.innerHeight;
      if (r.top < 60 || r.bottom > vh - 60) el.scrollIntoView({block: "center"});
    }
  }
}

function renderLive(animate = true) {
  if (MODE !== "live") return;
  const P = procMeta();
  document.getElementById("app").classList.toggle("anim", !!animate);
  document.getElementById("main").classList.remove("wide");
  liveHeader();
  setRail(L.view === "run" ? (L.stage || "listen") : null);
  liveShead(P);
  liveViewer(P);
  const capText = L.view === "run" ? L.caption.text : "";
  const cm = L.caption.meta;
  const capMeta = P ? t("{lang} · NVDA-style, from the accessibility tree · {meta}", {lang: P.lang, meta: L.view === "run" ? (Array.isArray(cm) ? t(cm[0], cm[1]) : cm) : t("waiting for Run")}) : "";
  const said = document.getElementById("said");
  if (said.dataset.text !== capText || said.dataset.lang !== LANG || !capText) {
    said.dataset.text = capText;
    said.dataset.lang = LANG;
    setCaption(capText, L.caption.tone, capMeta, !!capText && animate, P);
  } else {
    document.getElementById("capMeta").textContent = capMeta;
    const cap = document.getElementById("caption");
    cap.className = "caption " + (L.caption.tone || "") + (cap.classList.contains("glossed") ? " glossed" : "");
  }
  const panel = document.getElementById("panel");
  const tl = document.getElementById("tlCard");
  if (L.view === "setup" || L.offline) {
    panel.innerHTML = setupPanel();
    tl.hidden = true;
  } else {
    const c = L.current;
    const focusCard = currentCard(P);
    const big = c && ["patch", "result"].includes(c.type);
    panel.innerHTML = runBar() + (big ? "" : liveFeedHtml(P)) + focusCard;
    tl.hidden = !!big;
    if (!big) tl.innerHTML = timelineHtml(P, L.events, L.attempt, L.step, c && c.type === "verified");
    trimFeed(1);
  }
  liveFooter();
  if (location.hash !== "#live") history.replaceState(null, "", location.pathname + location.search + "#live");
  window.liveStatus = L.status;
}

function liveClick(ev) {
  const b = ev.target.closest("button");
  if (!b || b.disabled) return false;
  if (b.dataset.proc) { if (L.cfg.procedure !== b.dataset.proc) setCfg("procedure", b.dataset.proc); return true; }
  if (b.dataset.set) { setCfg(b.dataset.set, b.dataset.v); return true; }
  const act = b.dataset.act;
  if (!act) return false;
  if (act === "run") startRun();
  else if (act === "stop") stopRun();
  else if (act === "reset") resetPortal();
  else if (act === "approve") decideLive(true);
  else if (act === "reject") decideLive(false);
  else if (act === "setup") { L.view = "setup"; prepare(); renderLive(); }
  return true;
}

function setCfg(name, v) {
  if (["starting", "running", "waiting"].includes(L.status)) return;
  if (name === "speed") { L.cfg.speed = parseFloat(v) || 1; renderLive(false); return; }
  if (name === "llm") { L.cfg.llm = v; renderLive(false); return; }
  if (name === "procedure") { L.cfg.procedure = v; L.cfg.target = L.options.barriers[v].defaults[L.cfg.barrier]; }
  if (name === "form") L.cfg.form = v;
  if (name === "barrier") { L.cfg.barrier = v; L.cfg.target = L.options.barriers[L.cfg.procedure].defaults[v]; }
  if (name === "target") L.cfg.target = v;
  L.view = "setup";
  if (L.status === "done" || L.status === "stopped" || L.status === "error") { resetLocal(); L.status = "idle"; }
  renderLive(false);
  prepare();
}

function liveKey(ev) {
  const k = ev.key;
  if ((k === "a" || k === "A") && visiblePending()) { decideLive(true); return true; }
  if ((k === "r" || k === "R") && visiblePending()) { decideLive(false); return true; }
  if (k === "Escape" && ["starting", "running", "waiting"].includes(L.status)) { stopRun(); return true; }
  return false;
}

function liveChange(ev) {
  if (ev.target.id === "targetSel") { setCfg("target", ev.target.value); return true; }
  return false;
}

function liveTick() {
  if (MODE !== "live") return;
  const el = document.getElementById("thinkSecs");
  if (el && L.current && L.current.type === "thinking") el.innerHTML = thinkLine(Math.max(0, Math.round(Date.now() / 1000 - L.current.since)));
  if (L.busy) liveFooter();
}
