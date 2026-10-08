let MODE = "replay";

function setMode(mode) {
  if (mode === "replay" && !scenes.length) mode = "live";
  MODE = mode;
  document.getElementById("modeReplay").setAttribute("aria-selected", String(mode === "replay"));
  document.getElementById("modeLive").setAttribute("aria-selected", String(mode === "live"));
  document.body.dataset.mode = mode;
  const screen = document.getElementById("screen");
  if (mode === "replay") {
    screen.querySelectorAll("iframe.livef, .curtain").forEach(x => x.remove());
    lastRendered = null;
    render();
  } else {
    setPlaying(false);
    screen.querySelectorAll("iframe.fallback, .fallback-note").forEach(x => x.remove());
    renderLive();
    schedulePoll(20);
  }
}

function onHash() {
  if (location.hash === "#live") { if (MODE !== "live") setMode("live"); return; }
  const i = sceneFromHash();
  if (i >= 0) { if (MODE !== "replay") { cur = i; setMode("replay"); } else if (i !== cur) go(i); }
  else if (MODE === "replay" && scenes.length) history.replaceState(null, "", location.pathname + location.search + "#" + scenes[cur].key);
}

function rerender() {
  if (MODE === "replay") render(false); else renderLive(false);
}

function cycleLang() {
  setLang(LANGS[(LANGS.indexOf(LANG) + 1) % LANGS.length]);
}

document.addEventListener("click", ev => {
  const langBtn = ev.target.closest("#langs button[data-lang]");
  if (langBtn) { setLang(langBtn.dataset.lang); if (ev.detail > 0) langBtn.blur(); return; }
  const modeBtn = ev.target.closest(".modes button");
  if (modeBtn) { setMode(modeBtn.dataset.mode); return; }
  if (MODE === "live") { liveClick(ev); return; }
  const b = ev.target.closest("button[data-i]");
  if (b) { go(+b.dataset.i); if (ev.detail > 0) b.blur(); return; }
  const p = ev.target.closest("#procs button[data-jump]");
  if (p) { go(+p.dataset.jump); if (ev.detail > 0) p.blur(); }
});

document.addEventListener("change", ev => { if (MODE === "live") liveChange(ev); });

document.addEventListener("keydown", ev => {
  if (ev.ctrlKey || ev.altKey || ev.metaKey) return;
  const tag = (ev.target.tagName || "").toLowerCase();
  if (tag === "select" || tag === "input" || tag === "textarea") return;
  if (ev.key === "l" || ev.key === "L") { setMode(MODE === "live" ? "replay" : "live"); ev.preventDefault(); return; }
  if (ev.key === "g" || ev.key === "G") { cycleLang(); ev.preventDefault(); return; }
  const handled = MODE === "live" ? liveKey(ev) : replayKey(ev);
  if (handled) ev.preventDefault();
});

let resizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => { if (MODE === "replay") render(false); else { scaleFrame(); renderLive(false); } fitHeader(); }, 120);
});
window.addEventListener("hashchange", onHash);
setInterval(liveTick, 1000);

(async function boot() {
  setLang(LANG, true);
  const hasReplay = initReplay();
  if (!hasReplay && !HTTP) {
    document.getElementById("app").outerHTML = `<div class="empty"><div>${th("No recorded run next to this page ({file}).", {file: code("out/run_data.js")})}<br><br>${th("Run {cmd} in the demo folder.", {cmd: code("python start_demo.py")})}</div></div>`;
    return;
  }
  const wantLive = location.hash === "#live" || !hasReplay;
  if (wantLive) { MODE = "live"; await liveInit(); setMode("live"); }
  else { setMode("replay"); await liveInit(); }
  if (AUTO > 0 && hasReplay && !wantLive) { window.autoDone = false; setPlaying(true, AUTO); }
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { fitHeader(); rerender(); });
  window.appReady = true;
})();
