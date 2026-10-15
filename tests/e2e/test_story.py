import urllib.request

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")

pytestmark = pytest.mark.e2e

STEPS = 6
VIEWPORTS = [(1920, 1080), (1366, 768), (1280, 620)]
LANGS = ("en", "ja", "vi")

HEADER_CHECK = """(mode) => { const out = []; const W = innerWidth, H = innerHeight;
  const head = document.querySelector('header.masthead'); const rail = document.querySelector('#rail');
  if (!head || !rail) return ['header or rail missing'];
  const hd = head.getBoundingClientRect(), rl = rail.getBoundingClientRect();
  if (hd.bottom > rl.top + 0.5) out.push('header overlaps rail');
  const name = (e) => e.id || e.getAttribute('data-lang') || e.getAttribute('data-view') || e.className || e.tagName;
  const sel = '.di-logo, .brand, .brand h1, .event-tag, .tabs, .tab, #langseg, #langseg button, #engToggle, #prev, #next, #more';
  for (const e of head.querySelectorAll(sel)) { if (!e.getClientRects().length || getComputedStyle(e).visibility === 'hidden') continue;
    const r = e.getBoundingClientRect(); if (!r.width || !r.height) { out.push('collapsed: ' + name(e)); continue; }
    if (r.left < hd.left - 0.5 || r.right > hd.right + 0.5 || r.top < hd.top - 0.5 || r.bottom > hd.bottom + 0.5) out.push('clipped by header: ' + name(e));
    if (r.left < -0.5 || r.right > W + 0.5 || r.top < -0.5 || r.bottom > H + 0.5) out.push('outside viewport: ' + name(e));
    if (e.tagName === 'BUTTON' && e.scrollWidth > e.clientWidth + 1) out.push('label overflow: ' + name(e)); }
  const must = mode === 'eng' ? ['#prev', '#next', '#more', '#langseg', '.tabs', '#engToggle'] : ['#more', '#langseg', '.tabs', '#engToggle'];
  if (!must.every((q) => head.querySelector(q) && head.querySelector(q).getClientRects().length)) out.push('header control hidden');
  if (mode === 'story' && head.querySelector('#prev, #next')) out.push('story mode keeps navigation in the header');
  return out; }"""

DASH_CHECK = r"""() => { const out = []; const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let node;
  while ((node = walker.nextNode())) { const el = node.parentElement; if (!el || el.closest('script, style, [hidden]') || !el.getClientRects().length) continue;
    if (/[–—]/.test(node.nodeValue)) out.push((el.id || el.className || el.tagName) + ': ' + node.nodeValue.trim().slice(0, 60)); }
  document.querySelectorAll('[title], [placeholder], [aria-label]').forEach((el) => { if (el.closest('[hidden]')) return;
    ['title', 'placeholder', 'aria-label'].forEach((a) => { const v = el.getAttribute(a); if (v && /[–—]/.test(v)) out.push(a + ' ' + v.slice(0, 60)); }); });
  return out; }"""


@pytest.fixture(scope="module")
def browser():
    with playwright_sync.sync_playwright() as pw:
        browser = pw.chromium.launch()
        yield browser
        browser.close()


def reset_server(base_url):
    req = urllib.request.Request(base_url + "/api/reset", data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        assert r.status == 200


def open_page(browser, base_url, query, viewport=(1536, 864)):
    context = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]})
    page = context.new_page()
    page.problems = []
    page.on("console", lambda m: page.problems.append(f"console {m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: page.problems.append(f"pageerror: {e}"))
    page.goto(base_url + "/" + query)
    settle(page)
    return page


def settle(page, timeout=60000):
    page.wait_for_function("() => window.__rb && window.__rb.state() && !window.__rb.busy()", timeout=timeout)
    page.wait_for_timeout(250)


def mode(page):
    return page.evaluate("() => window.__rb.mode()")


def set_lang(page, lang):
    page.click(f"#langseg button[data-lang='{lang}']")
    page.wait_for_function(f"() => window.__rb.lang() === '{lang}' && document.documentElement.lang === '{lang}'")
    page.wait_for_timeout(250)


def assert_screen_clean(page, where):
    current = mode(page)
    header = page.evaluate(HEADER_CHECK, current)
    assert not header, f"{where} [{current}]: header {header}"
    dashes = page.evaluate(DASH_CHECK)
    assert not dashes, f"{where} [{current}]: em/en dash in UI text {dashes[:4]}"


def test_story_view_is_the_default(browser, base_url):
    reset_server(base_url)
    page = open_page(browser, base_url, "?lang=en")
    try:
        assert mode(page) == "story"
        assert page.evaluate("() => document.body.classList.contains('mode-story')")
        assert page.is_visible("#story") and page.is_hidden("#trace")
        assert page.locator("#story #next").is_visible()
        assert page.locator("header #next").count() == 0
        assert page.problems == []
    finally:
        page.context.close()


def test_story_walkthrough_to_approval(browser, base_url):
    reset_server(base_url)
    page = open_page(browser, base_url, "?view=story&lang=en")
    try:
        for expected in range(STEPS):
            page.click("#next")
            settle(page)
            assert page.evaluate("() => window.__rb.state().step") == expected
            assert page.inner_text("#storyTitle").strip() and page.inner_text("#storyLine").strip()
        assert page.is_hidden("#next") and page.is_visible("#approve")
        page.click("#approve")
        settle(page)
        assert page.evaluate("() => window.__rb.state().plan.status") == "approved"
        assert page.problems == []
    finally:
        page.context.close()


def test_engineering_toggle_and_url(browser, base_url):
    reset_server(base_url)
    page = open_page(browser, base_url, "?view=story&lang=en")
    try:
        page.click("#engToggle")
        page.wait_for_function("() => window.__rb.mode() === 'eng' && document.body.classList.contains('mode-eng')")
        assert page.get_attribute("#engToggle", "aria-pressed") == "true"
        assert page.evaluate("() => localStorage.getItem('rb.mode')") == "eng"
        assert page.is_visible("#trace") and page.is_hidden("#story")
        assert page.locator("header #next").count() == 1
        page.keyboard.press("e")
        page.wait_for_function("() => window.__rb.mode() === 'story'")
        assert page.locator("#story #next").count() == 1
        page.goto(base_url + "/?view=eng&lang=en")
        settle(page)
        assert mode(page) == "eng"
        assert page.problems == []
    finally:
        page.context.close()


@pytest.mark.parametrize("viewport", VIEWPORTS, ids=lambda v: f"{v[0]}x{v[1]}")
def test_header_fits_and_no_dashes(browser, base_url, viewport):
    reset_server(base_url)
    page = open_page(browser, base_url, "?view=story&lang=en", viewport)
    try:
        for lang in LANGS:
            set_lang(page, lang)
            assert_screen_clean(page, f"{viewport} intro {lang}")
        set_lang(page, "en")
        for _ in range(STEPS):
            page.click("#next")
            settle(page)
        for lang in LANGS:
            set_lang(page, lang)
            assert_screen_clean(page, f"{viewport} decision step {lang}")
        page.click("#engToggle")
        page.wait_for_function("() => window.__rb.mode() === 'eng'")
        page.wait_for_timeout(300)
        for lang in LANGS:
            set_lang(page, lang)
            assert_screen_clean(page, f"{viewport} decision step {lang}")
        assert page.problems == []
    finally:
        page.context.close()
