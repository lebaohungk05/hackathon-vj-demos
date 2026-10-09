(() => {
  const toggle = document.getElementById("detailToggle");
  const drawer = document.getElementById("drawer");
  const tl = document.getElementById("tlToggle");
  const TL_KEY = "minna-timeline";
  let showTimeline = false;
  try { showTimeline = localStorage.getItem(TL_KEY) === "true"; } catch (e) { void e; }
  const applyTimeline = () => {
    tl.checked = showTimeline;
    document.body.classList.toggle("show-timeline", showTimeline);
  };
  const setOpen = open => {
    drawer.hidden = !open;
    toggle.setAttribute("aria-expanded", String(open));
  };
  window.drawerOpen = () => !drawer.hidden;
  window.closeDrawer = () => setOpen(false);
  toggle.addEventListener("click", ev => {
    setOpen(drawer.hidden);
    if (ev.detail > 0) toggle.blur();
  });
  tl.addEventListener("change", () => {
    showTimeline = tl.checked;
    try { localStorage.setItem(TL_KEY, String(showTimeline)); } catch (e) { void e; }
    applyTimeline();
    window.dispatchEvent(new Event("resize"));
  });
  document.addEventListener("click", ev => {
    if (drawer.hidden || drawer.contains(ev.target) || toggle.contains(ev.target)) return;
    setOpen(false);
  });
  document.addEventListener("keydown", ev => {
    if (ev.key === "Escape" && !drawer.hidden) { setOpen(false); toggle.focus(); ev.stopImmediatePropagation(); ev.preventDefault(); }
  }, true);
  applyTimeline();
})();
