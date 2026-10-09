const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const LANGS = ["en", "ja", "vi"];
const UI = window.UI_STRINGS || {};
const TR = window.TR_CACHE || {};
const LIVE_TR = {};
const i18nMissing = new Set();
const i18nRequested = new Set();
window.i18nMissing = i18nMissing;
window.i18nRequested = i18nRequested;

function pickLang() {
  const url = new URLSearchParams(location.search).get("lang");
  if (LANGS.includes(url)) return url;
  try { const s = localStorage.getItem("minna-lang"); if (LANGS.includes(s)) return s; } catch (e) { void e; }
  return "vi";
}
let LANG = pickLang();

const CJK_RX = /[　-〿぀-ヿ㐀-鿿豈-﫿＀-￯]/;
const VN_CHARS = "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ";
const VN_RX = new RegExp(`[${VN_CHARS}${VN_CHARS.toUpperCase()}̀-ͯ]`);
const langOf = text => CJK_RX.test(text) ? "ja" : VN_RX.test(text) ? "vi" : "en";
const pageLang = P => String((P && P.lang) || "en").slice(0, 2);
const norm = s => String(s ?? "").replace(/\s+/g, " ").trim();

function t(s, v) {
  let out = s;
  if (LANG !== "en") {
    const e = UI[s];
    if (e && e[LANG]) out = e[LANG];
    else i18nMissing.add(s);
  }
  return v ? out.replace(/\{(\/?\w+)\}/g, (m, k) => (v[k] ?? m)) : out;
}

function th(s, v) {
  const tpl = t(s);
  return tpl.split(/(\{\/?\w+\})/).map(part => {
    const m = part.match(/^\{(\/?\w+)\}$/);
    return m && v && m[1] in v ? String(v[m[1]]) : esc(part);
  }).join("");
}

const QM = {en: ["“", "”"], vi: ["“", "”"], ja: ["「", "」"]};
const qm = () => QM[LANG];

function qs(text, lang) {
  const l = lang || langOf(text);
  return `<span class="src" data-src="${l}" lang="${l}">${esc(text)}</span>`;
}

function q(text, lang) {
  const [a, b] = qm();
  return `${a}${qs(text, lang)}${b}`;
}

function code(text) {
  return `<code class="src code" data-src="code">${esc(text)}</code>`;
}

function foreignTest() {
  if (LANG === "en") return ch => CJK_RX.test(ch) || VN_RX.test(ch);
  if (LANG === "ja") return ch => VN_RX.test(ch);
  return ch => CJK_RX.test(ch);
}

const CODE_RX = /<\/?[a-z][^<>]*>|\b[\w-]+="[^"]*"|\bfld_[\w]+|#[a-z][\w-]*|\b[\w-]+\.(?:html|csv|js|txt|py)\b|\bpreventDefault\(\)|\baria-label\b/gi;

function markRuns(text) {
  const isF = foreignTest();
  const chars = [...text];
  const flags = chars.map(isF);
  if (!flags.some(Boolean)) return esc(text);
  const pairs = [["“", "”"], ["\"", "\""], ["「", "」"], ["『", "』"], ["（", "）"], ["(", ")"], ["'", "'"], ["‘", "’"]];
  const mark = new Array(chars.length).fill(false);
  for (let i = 0; i < chars.length; i++) {
    const pair = pairs.find(p => p[0] === chars[i]);
    if (!pair) continue;
    const j = chars.indexOf(pair[1], i + 1);
    if (j < 0 || j - i > 120) continue;
    const inner = chars.slice(i + 1, j);
    const words = inner.join("").split(/\s+/).filter(Boolean);
    const fw = words.filter(w => [...w].some(isF)).length;
    if (fw && (pair[0] !== "(" && pair[0] !== "（" || fw * 2 >= words.length)) { for (let k = i + 1; k < j; k++) mark[k] = true; i = j; }
  }
  const wordRx = /[^\s,.;:!?()（）“”"「」]+/g;
  let m;
  const words = [];
  while ((m = wordRx.exec(text)) !== null) words.push([m.index, m.index + m[0].length, m[0]]);
  const idx = [];
  let pos = 0;
  chars.forEach((c, i) => { idx[i] = pos; pos += c.length; });
  const charAt = off => idx.indexOf(off);
  words.forEach(([s, e, w]) => {
    if (![...w].some(isF)) return;
    const a = charAt(s), b = charAt(e) < 0 ? chars.length : charAt(e);
    for (let k = a; k < b; k++) mark[k] = true;
  });
  for (let i = 1; i < chars.length - 1; i++) {
    if (!mark[i] && mark[i - 1] && /[\s,]/.test(chars[i])) {
      let j = i;
      while (j < chars.length && /[\s,]/.test(chars[j]) && !mark[j]) j++;
      if (j < chars.length && mark[j] && j - i <= 2) for (let k = i; k < j; k++) mark[k] = true;
    }
  }
  let html = "", buf = "", cur = false;
  const flush = () => { if (!buf) return; html += cur ? qs(buf, langOf(buf)) : esc(buf); buf = ""; };
  chars.forEach((c, i) => { if (mark[i] !== cur) { flush(); cur = mark[i]; } buf += c; });
  flush();
  return html;
}

function dx(text) {
  const s = String(text ?? "");
  let html = "", last = 0, m;
  CODE_RX.lastIndex = 0;
  while ((m = CODE_RX.exec(s)) !== null) {
    html += markRuns(s.slice(last, m.index)) + code(m[0]);
    last = m.index + m[0].length;
  }
  return html + markRuns(s.slice(last));
}

function trGet(text, lang) {
  const k = norm(text);
  return (TR[k] && TR[k][lang]) || (LIVE_TR[k] && LIVE_TR[k][lang]) || null;
}

let trTimer = null;
const trQueue = new Map();
function needTr(text, kind) {
  const k = norm(text);
  if (!k || LANG === "en" && kind === "llm") return;
  const key = `${LANG}|${kind}|${k}`;
  if (i18nRequested.has(key)) return;
  i18nRequested.add(key);
  if (!(typeof HTTP !== "undefined" && HTTP)) return;
  trQueue.set(key, {text: k, kind, lang: LANG});
  clearTimeout(trTimer);
  trTimer = setTimeout(flushTr, 300);
}

async function flushTr() {
  const items = [...trQueue.values()];
  if (!items.length) return;
  const byLang = {};
  items.forEach(it => (byLang[it.lang] = byLang[it.lang] || []).push(it));
  let pending = 0, gotNew = false;
  for (const [lang, list] of Object.entries(byLang)) {
    try {
      const r = await fetch("/api/translate", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({lang, items: list.map(x => ({text: x.text, kind: x.kind}))})});
      const data = await r.json();
      Object.entries(data.translations || {}).forEach(([src, dst]) => {
        LIVE_TR[src] = LIVE_TR[src] || {};
        if (!LIVE_TR[src][lang]) gotNew = true;
        LIVE_TR[src][lang] = dst;
        trQueue.delete(`${lang}|llm|${src}`);
        trQueue.delete(`${lang}|label|${src}`);
      });
      const still = new Set(data.pending || []);
      list.forEach(x => { if (!still.has(x.text) && !(data.translations || {})[x.text]) trQueue.delete(`${lang}|${x.kind}|${x.text}`); });
      pending += still.size;
    } catch (e) {
      list.forEach(x => trQueue.delete(`${lang}|${x.kind}|${x.text}`));
    }
  }
  if (gotNew && typeof rerender === "function") rerender();
  if (pending && trQueue.size) { clearTimeout(trTimer); trTimer = setTimeout(flushTr, 2500); }
}

function lx(text) {
  const s = norm(text);
  if (!s) return "";
  if (LANG === "en") return dx(s);
  const hit = trGet(s, LANG);
  if (hit) return dx(hit);
  const viaAgent = agentTx(s);
  if (viaAgent !== null) return viaAgent;
  needTr(s, "llm");
  return dx(s);
}

function lxPlain(text) {
  const s = norm(text);
  if (LANG === "en" || !s) return s;
  return trGet(s, LANG) || (needTr(s, "llm"), s);
}

function glossText(text, srcLang) {
  const s = norm(text);
  if (!s || srcLang === LANG) return null;
  const full = trGet(s, LANG);
  if (full && !s.includes(", ")) return {html: dx(full), plain: full};
  const parts = s.split(", ");
  let known = 0, neutral = 0;
  const html = [], plain = [];
  parts.forEach(p => {
    const role = ROLE_GLOSS[p] && ROLE_GLOSS[p][LANG];
    const hit = role || trGet(p, LANG) || (langOf(p) === LANG ? p : null);
    if (hit) { known++; html.push(dx(hit)); plain.push(hit); }
    else if (langOf(p) === "en") { neutral++; html.push(code(p)); plain.push(p); }
    else { html.push(qs(p, langOf(p))); plain.push(p); needTr(p, "label"); }
  });
  if (!known && full) return {html: dx(full), plain: full};
  if (!known) { if (neutral < parts.length) needTr(s, "label"); return null; }
  return {html: html.join(LANG === "ja" ? "、" : ", "), plain: plain.join(LANG === "ja" ? "、" : ", ")};
}

function gloss(text, srcLang) {
  const g = glossText(text, srcLang);
  return g ? `<span class="gloss"><span class="gl">${LANG.toUpperCase()}</span>${g.html}</span>` : "";
}

function quoteBlock(text, srcLang, cls) {
  return `<span class="${cls || "qb"}">${q(text, srcLang)}</span>${gloss(text, srcLang)}`;
}

function labelPlain(text, srcLang) {
  if (srcLang === LANG) return norm(text);
  const g = glossText(text, srcLang);
  return g ? g.plain : null;
}

const ROLE_GLOSS = {
  "ô nhập": {en: "edit box", ja: "入力欄"},
  "nút": {en: "button", ja: "ボタン"},
  "hộp xổ xuống": {en: "combo box", ja: "コンボボックス"},
  "hộp kiểm": {en: "check box", ja: "チェックボックス"},
  "liên kết": {en: "link", ja: "リンク"},
  "đã chọn": {en: "checked", ja: "チェックあり"},
  "chưa chọn": {en: "not checked", ja: "チェックなし"},
  "hình ảnh": {en: "image", ja: "画像"},
  "編集": {en: "edit box", vi: "ô nhập"},
  "ボタン": {en: "button", vi: "nút"},
  "コンボボックス": {en: "combo box", vi: "hộp xổ xuống"},
  "チェックボックス": {en: "check box", vi: "hộp kiểm"},
  "リンク": {en: "link", vi: "liên kết"},
  "チェック": {en: "checked", vi: "đã chọn"},
  "チェックなし": {en: "not checked", vi: "chưa chọn"},
  "画像": {en: "image", vi: "hình ảnh"},
};

const PROC_EN = {
  vn: {title: "Criminal record certificate", short: "Criminal record", country: "Vietnam", steps: ["Applicant", "Contact", "Purpose", "Confirmation"],
    goal: "reach the Confirmation step and stop before the submit button", submit: "Nộp hồ sơ"},
  jp: {title: "Copy of residence record (mock)", short: "Residence record", country: "Japan", steps: ["Applicant", "Request details", "Confirmation"],
    goal: "reach the confirmation step and stop before the submit button", submit: "申請する"},
};
const procTitle = key => PROC_EN[key] ? t(PROC_EN[key].title) : key;
const procShort = key => PROC_EN[key] ? t(PROC_EN[key].short) : key;
const procCountry = key => PROC_EN[key] ? t(PROC_EN[key].country) : key;
const stepName = (key, n) => PROC_EN[key] ? t(PROC_EN[key].steps[n - 1] || "") : "";
const procKeyByTitle = title => Object.keys(PROC_EN).find(k => (window.RUN && window.RUN.procedures || []).some(P => P.key === k && P.title === title)) || (/[぀-ヿ㐀-鿿]/.test(title) ? "jp" : "vn");

const SC_TITLE = {"3.3.2": "Labels or Instructions", "2.4.6": "Headings and Labels", "2.1.1": "Keyboard", "1.1.1": "Non-text Content"};
const scTitle = (sc, fallback) => t(SC_TITLE[sc] || fallback || "");
const KIND_WORDS = {"unnamed field": "unnamed_field", "ambiguous label": "ambiguous_label", "keyboard trap": "keyboard_trap", "mouse only": "mouse_only", "captcha": "captcha"};
const kindName = k => t(KIND[k] || "Unclear field");

const CHECK_NAMES = ["Target element still present", "Accessibility tree: accessible name matches the visible label", "Keyboard replay: Tab leaves the field",
  "Keyboard replay: element takes focus with role button", "Keyboard replay: Enter activates it", "axe-core: no rule fails on this element"];

function checkName(name) {
  if (CHECK_NAMES.includes(name)) return th(name);
  const m = name.match(/^Keyboard replay: restarted from step 1 in attempt (\d+) and passed step (\d+)$/);
  if (m) return th("Keyboard replay: restarted from step 1 in attempt {a} and passed step {s}", {a: m[1], s: m[2]});
  const ax = name.match(/^axe-core on the fixed page: (\d+) violation\(s\) on #(\S+)$/);
  if (ax) return th("axe-core on the fixed page: {n} violation(s) on {id}", {n: ax[1], id: code("#" + ax[2])});
  return dx(name);
}

function checkDetail(d) {
  const s = String(d ?? "");
  let m;
  if (/^#\S+$/.test(s)) return code(s);
  if (s === "accessible name is empty") return th("accessible name is empty");
  if ((m = s.match(/^accessible name “(.*)” does not contain the visible label “(.*)”$/))) return th("accessible name {name} does not contain the visible label {label}", {name: q(m[1]), label: q(m[2])});
  if ((m = s.match(/^accessible name “(.*)” contains the visible label$/))) return th("accessible name {name} contains the visible label", {name: q(m[1])});
  if ((m = s.match(/^focus moved to (#\S+)$/))) return th("focus moved to {id}", {id: code(m[1])});
  if ((m = s.match(/^navigated to (\S+)$/))) return th("navigated to {file}", {file: code(m[1])});
  if (s === "0 violations on the element") return th("0 violations on the element");
  if (s === "deterministic") return th("deterministic");
  if (/^focusable=/.test(s) || /^[\w-]+(, [\w-]+)*$/.test(s)) return code(s);
  return dx(s);
}

const AGENT_EXACT = [
  "(never announced: not in Tab order)", "(focus left the page)", "Image CAPTCHA with no audio or text alternative. The agent does not attempt it.",
  "CAPTCHA detected: stop and hand off to a human officer. The submit button is never pressed.", "CAPTCHA input: never attempted, handed to a human",
  "declaration checkbox", "guard: never submit, never log in", "continue to next step", "Field meaning is uncertain for the rule table",
  "Running axe-core 4.10.2 on the same starting pages for comparison.", "Claude CLI not found on this machine: using cached LLM answers, then the rule engine.",
  "Run stopped by the presenter. Nothing was submitted.", "Chromium for Playwright is not installed. Run: python -m playwright install chromium",
  "axe-core file missing (../sim/vendor/axe.min.js).", "A run is already in progress. Stop or reset it first.", "A run is in progress. Stop or reset it first.",
  "The previous run is still shutting down. Try Reset again in a few seconds.", "Hand off to human (never bypassed)", "no cached answer for this prompt in replay mode",
  "(nothing)", "(nothing but the role)", "(no name)", "LLM unavailable", "Failed to fetch", "unknown barrier", "unknown target for this barrier", "procedure must be vn or jp",
];
const WHO = ["presenter (web UI button)", "developer (auto-approve, recording mode)", "developer (CLI prompt)"];
const MODE_TEXT_EN = ["live Claude calls", "cache first, live Claude call when missing", "cached replies (offline)"];
const KIND_LABELS = ["Remove a field label", "Code instead of a label", "Keyboard trap", "Mouse-only button", "Image CAPTCHA"];

function failedCheck(x) {
  const c = CHECK_NAMES.find(n => x.startsWith(n + ": "));
  return c ? `${checkName(c)}: ${checkDetail(x.slice(c.length + 2))}` : dx(x);
}

function reasonTx(r) {
  const a = agentTx(r);
  return a !== null ? a : lx(r);
}

const AGENT_RULES = [
  [/^Attempt (\d+): start from step 1$/, m => th("Attempt {n}: start from step 1", {n: m[1]})],
  [/^Step (\d+) passed by keyboard only$/, m => th("Step {n} passed by keyboard only", {n: m[1]})],
  [/^Reached the final confirmation step \((.+)\)$/, m => th("Reached the final confirmation step ({name})", {name: q(m[1])})],
  [/^Verified by keyboard replay: step (\d+) now passes; #(\S+) \((.+?), WCAG ([\d.]+)\) no longer blocks$/, m => th("Verified by keyboard replay: step {s} now passes; {id} ({kind}, WCAG {sc}) no longer blocks", {s: m[1], id: code("#" + m[2]), kind: esc(kindName(KIND_WORDS[m[3]] || m[3]).toLowerCase()), sc: m[4]})],
  [/^type “([\s\S]*)”$/, m => th("type {value}", {value: q(m[1])})],
  [/^type “([\s\S]*)” \(([\s\S]*)\)$/, m => th("type {value} ({reason})", {value: q(m[1]), reason: reasonTx(m[2])})],
  [/^press (\S+) \((.*)\)$/, m => th("press {key} ({reason})", {key: esc(m[1]), reason: reasonTx(m[2])})],
  [/^skip “(.*)” \((.*)\)$/, m => th("skip {name} ({reason})", {name: q(m[1]), reason: reasonTx(m[2])})],
  [/^hand off “(.*)” \(([\s\S]*)\)$/, m => th("hand off {name} ({reason})", {name: q(m[1]), reason: reasonTx(m[2])})],
  [/^Field meaning uncertain: handed to a human\. ([\s\S]*)$/, m => th("Field meaning uncertain: handed to a human. {reason}", {reason: reasonTx(m[1])})],
  [/^Full Tab cycle \((\d+) stops\) never reached “(.*)”: it is a <(\w+)> with onclick, not focusable, so Enter and Space cannot activate it$/, m => th("Full Tab cycle ({n} stops) never reached {name}: it is a {tag} with onclick, not focusable, so Enter and Space cannot activate it", {n: m[1], name: q(m[2]), tag: code(`<${m[3]}>`)})],
  [/^Tab pressed (\d+) times, focus never left this field$/, m => th("Tab pressed {n} times, focus never left this field", {n: m[1]})],
  [/^Screen reader reads the field only as its role, with no name \((.*)\): a blind user cannot tell what to type$/, m => th("Screen reader reads the field only as its role, with no name ({why}): a blind user cannot tell what to type", {why: checkDetail(m[1])})],
  [/^Screen reader reads a code instead of the label \((.*)\)$/, m => th("Screen reader reads a code instead of the label ({why})", {why: checkDetail(m[1])})],
  [/^field name matches task data '(.*)'$/, m => th("field name matches task data {key}", {key: q(m[1], langOf(m[1]) === "en" ? "vi" : langOf(m[1]))})],
  [/^Turn the visual caption into a real <label for="(\S+)"> so the field gets an accessible name$/, m => th("Turn the visual caption into a real {tag} so the field gets an accessible name", {tag: code(`<label for="${m[1]}">`)})],
  [/^Add aria-label to #(\S+)$/, m => th("Add aria-label to {id}", {id: code("#" + m[1])})],
  [/^Remove the code-like aria-label from #(\S+) and link the visible caption as its <label>$/, m => th("Remove the code-like aria-label from {id} and link the visible caption as its {tag}", {id: code("#" + m[1]), tag: code("<label>")})],
  [/^Stop swallowing the Tab key on #(\S+); keep the formatting but run it on blur$/, m => th("Stop swallowing the Tab key on {id}; keep the formatting but run it on blur", {id: code("#" + m[1])})],
  [/^Remove the script that pulls focus back into #(\S+)$/, m => th("Remove the script that pulls focus back into {id}", {id: code("#" + m[1])})],
  [/^Replace the clickable <div id="(\S+)"> with a native <button>, so Tab, Enter and Space work$/, m => th("Replace the clickable {div} with a native {button}, so Tab, Enter and Space work", {div: code(`<div id="${m[1]}">`), button: code("<button>")})],
  [/^Deterministic pre-check failed: ([\s\S]*)$/, m => th("Deterministic pre-check failed: {list}", {list: m[1].split("; ").map(failedCheck).join("; ")})],
  [/^(Approved|Rejected) by (.*)$/, m => th(m[1] === "Approved" ? "Approved by {who}" : "Rejected by {who}", {who: WHO.includes(m[2]) ? th(m[2]) : dx(m[2])})],
  [/^Starting Chromium for (.+?) with a planted barrier \((.+), WCAG ([\d.]+)\)\. LLM answers: (.+)\.$/, m => th("Starting Chromium for {proc} with a planted barrier ({label}, WCAG {sc}). LLM answers: {mode}.", {proc: esc(procTitle(procKeyByTitle(m[1]))), label: esc(t(m[2])), sc: m[3], mode: esc(t(m[4]))})],
  [/^Starting Chromium for (.+?) \(original mock with the planted barriers\)\. LLM answers: (.+)\.$/, m => th("Starting Chromium for {proc} (original mock with the planted barriers). LLM answers: {mode}.", {proc: esc(procTitle(procKeyByTitle(m[1]))), mode: esc(t(m[2]))})],
  [/^Starting Chromium for (.+?) \(clean form\)\. LLM answers: (.+)\.$/, m => th("Starting Chromium for {proc} (clean form). LLM answers: {mode}.", {proc: esc(procTitle(procKeyByTitle(m[1]))), mode: esc(t(m[2]))})],
  [/^The agent stopped with an internal error \((\w+)\)\. Details are in (\S+)\. The replay mode still works\.$/, m => th("The agent stopped with an internal error ({type}). Details are in {path}. The replay mode still works.", {type: code(m[1]), path: code(m[2])})],
  [/^HTTP (\d+)$/, m => th("HTTP error {n}", {n: m[1]})],
  [/^server error: (.*)$/, m => th("Server error: {detail}", {detail: code(m[1])})],
];

function agentTx(text) {
  const s = String(text ?? "");
  if (AGENT_EXACT.includes(s) || WHO.includes(s) || MODE_TEXT_EN.includes(s) || KIND_LABELS.includes(s)) return th(s);
  for (const [rx, fn] of AGENT_RULES) {
    const m = s.match(rx);
    if (m) return fn(m);
  }
  return null;
}

function ax(text) {
  const a = agentTx(text);
  return a !== null ? a : lx(text);
}

function axPlain(text) {
  const d = document.createElement("div");
  d.innerHTML = ax(text);
  return d.textContent;
}

function heardHtml(text, P, cls) {
  const s = String(text ?? "");
  if (!s || /^\(.*\)$/.test(s)) return `<span class="${cls || "qb"}">${ax(s || "(nothing but the role)")}</span>`;
  return quoteBlock(s, pageLang(P), cls);
}

function fmtSecs(ms) {
  const n = (Number(ms) / 1000).toFixed(1);
  return t("{n} s", {n: LANG === "vi" ? n.replace(".", ",") : n});
}

function langSwitchHtml() {
  return LANGS.map(l => `<button type="button" data-lang="${l}" aria-pressed="${l === LANG}" lang="${l}" title="${esc(t("Language"))}: ${esc(LANG_NAMES[l])}">${l.toUpperCase()}</button>`).join("");
}
const LANG_NAMES = {en: "English", ja: "日本語", vi: "Tiếng Việt"};

function applyStatic() {
  document.documentElement.lang = LANG;
  document.querySelectorAll("[data-i18n]").forEach(el => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll("[data-i18n-aria]").forEach(el => el.setAttribute("aria-label", t(el.dataset.i18nAria)));
  document.querySelectorAll("[data-i18n-alt]").forEach(el => el.setAttribute("alt", t(el.dataset.i18nAlt)));
  document.querySelectorAll("[data-i18n-title]").forEach(el => el.setAttribute("title", t(el.dataset.i18nTitle)));
  const sw = document.getElementById("langs");
  if (sw) { sw.innerHTML = langSwitchHtml(); sw.setAttribute("aria-label", t("Language")); }
  document.title = t("MinnaAccess Live Demo");
}

function setLang(l, silent) {
  if (!LANGS.includes(l)) return;
  LANG = l;
  try { localStorage.setItem("minna-lang", l); } catch (e) { void e; }
  const u = new URL(location.href);
  if (u.searchParams.get("lang") !== l) { u.searchParams.set("lang", l); history.replaceState(null, "", u.pathname + u.search + u.hash); }
  applyStatic();
  if (!silent && typeof rerender === "function") rerender();
  window.uiLang = l;
}
window.uiLang = LANG;
