import csv
import difflib
import re
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

from barriers import write_atomic
from engine import JIS_TITLES, SC_CATALOG, Barrier, Focus, Observation, RuleBasedEngine, fold, label_check
from llm import Cancelled

ROOT = Path(__file__).resolve().parent
AXE = ROOT.parent / "sim" / "vendor" / "axe.min.js"
MAX_ROUNDS = 6
MAX_TABS = 30
VIEWPORT = {"width": 860, "height": 720}
ROLE_SPOKEN = {
    "vi-VN": {"textbox": "ô nhập", "button": "nút", "combobox": "hộp xổ xuống", "checkbox": "hộp kiểm", "link": "liên kết"},
    "ja-JP": {"textbox": "編集", "button": "ボタン", "combobox": "コンボボックス", "checkbox": "チェックボックス", "link": "リンク"},
}
CHECKED_SPOKEN = {"vi-VN": ("đã chọn", "chưa chọn"), "ja-JP": ("チェック", "チェックなし")}
ANSI = {"red": "\033[91m", "green": "\033[92m", "yellow": "\033[93m", "cyan": "\033[96m", "magenta": "\033[95m", "dim": "\033[2m", "end": "\033[0m"}
AXE_JS = """async () => { const r = await axe.run(document); return r.violations.map(v => ({rule: v.id, impact: v.impact,
  help: v.help, tags: v.tags, targets: v.nodes.map(n => n.target.join(' '))})); }"""


def color(text, c):
    return f"{ANSI[c]}{text}{ANSI['end']}"


def console(text):
    try:
        print(text, flush=True)
    except (UnicodeEncodeError, OSError):
        pass


def quiet(text):
    pass


@dataclass
class Workspace:
    base: str
    walk_dir: Path
    walk_url: str
    staging_dir: Path
    staging_url: str
    original_url: str = "portal/original"
    frames_dir: Optional[Path] = None
    frames_url: str = ""

    def page_url(self, key, file):
        return f"{self.base}/{self.walk_url}/{key}/{file}"


def make_guard(host):
    def guard(route):
        if urlparse(route.request.url).hostname == host:
            return route.continue_()
        return route.abort()
    return guard


class Recorder:
    def __init__(self, proc, ws, listener=None):
        self.proc = proc
        self.ws = ws
        self.events = []
        self.frame_no = 0
        self.listener = listener

    def add(self, attempt, step, kind, text, **extra):
        ev = {"i": len(self.events), "t": round(time.time(), 2), "attempt": attempt, "step": step, "kind": kind, "text": text, **extra}
        self.events.append(ev)
        if self.listener:
            self.listener(ev)
        return ev

    def shot(self, page, highlight_id=None, tone="#d1242f"):
        if not self.ws.frames_dir:
            return None
        self.frame_no += 1
        name = f"{self.proc.key}_frame_{self.frame_no:03d}.png"
        if highlight_id:
            page.evaluate(
                "([id, c]) => { const e = document.getElementById(id); if (e) { e.dataset.prevOutline = e.style.outline; "
                "e.style.outline = '5px solid ' + c; e.style.outlineOffset = '3px'; } }", [highlight_id, tone])
        page.screenshot(path=str(self.ws.frames_dir / name))
        if highlight_id:
            page.evaluate("id => { const e = document.getElementById(id); if (e) e.style.outline = e.dataset.prevOutline || ''; }", highlight_id)
        return f"{self.ws.frames_url}/{name}"


def focused(page):
    eid = page.evaluate("() => { const e = document.activeElement; return (!e || e === document.body) ? null : (e.id || e.tagName.toLowerCase()); }")
    if eid is None:
        return None
    snap = page.locator("*:focus").first.aria_snapshot(timeout=2000).splitlines()[0].strip()
    m = re.match(r'^- (\w+)(?: "((?:[^"\\]|\\.)*)")?(.*)$', snap)
    role, name = (m.group(1), (m.group(2) or "").replace('\\"', '"')) if m else ("generic", "")
    value = page.evaluate("() => document.activeElement.value ?? ''")
    checked = page.evaluate("() => document.activeElement.type === 'checkbox' ? document.activeElement.checked : null")
    return Focus(eid, role, name, value, checked)


def announce(f, lang):
    if f is None:
        return "(focus left the page)"
    spoken = ROLE_SPOKEN[lang]
    parts = [f.name] if f.name else []
    parts.append(spoken.get(f.role, f.role))
    if f.role == "checkbox":
        parts.append(CHECKED_SPOKEN[lang][0] if f.checked else CHECKED_SPOKEN[lang][1])
    if f.role in ("textbox", "combobox") and f.value:
        parts.append(f.value)
    return ", ".join(parts)


def caption_of(page, eid):
    return page.evaluate("id => { const e = document.getElementById(id); const f = e && e.closest('.field'); "
                         "return f ? f.innerText.replace('*','').replace(/\\s+/g,' ').trim() : ''; }", eid)


def has_captcha(page):
    tree = page.locator("body").aria_snapshot()
    return bool(re.search(r'img "[^"]*captcha', fold(tree))), tree


def find_mouse_only(page):
    return page.evaluate("""() => [...document.querySelectorAll('[onclick]')]
      .filter(e => !['BUTTON','A','INPUT','SELECT','TEXTAREA'].includes(e.tagName) && e.tabIndex < 0 && !e.getAttribute('role'))
      .map(e => ({id: e.id, text: e.textContent.trim(), tag: e.tagName.toLowerCase()}))""")


def make_barrier(kind, step, eid, heard, evidence, ctx="", check=""):
    sc, title, level = SC_CATALOG[kind]
    return Barrier(kind, step, eid, sc, title, heard, evidence, ctx, level, check)


def axe_page(page):
    page.add_script_tag(path=str(AXE))
    return page.evaluate(AXE_JS)


def precheck(ctx, ws, proc, barrier, file, after):
    stage = ws.staging_dir / proc.key
    shutil.rmtree(stage, ignore_errors=True)
    shutil.copytree(ws.walk_dir / proc.key, stage)
    (stage / file).write_text(after, encoding="utf-8")
    page = ctx.new_page()
    checks = []
    url = f"{ws.base}/{ws.staging_url}/{proc.key}/{file}"
    try:
        page.goto(url)
        eid = barrier.element_id
        exists = page.locator(f"#{eid}").count() == 1
        checks.append({"name": "Target element still present", "passed": exists, "detail": f"#{eid}"})
        if exists and barrier.kind in ("unnamed_field", "ambiguous_label"):
            page.focus(f"#{eid}")
            f = focused(page)
            status, why = label_check(f.name if f else "", caption_of(page, eid))
            checks.append({"name": "Accessibility tree: accessible name matches the visible label", "passed": status == "ok", "detail": why})
        if exists and barrier.kind == "keyboard_trap":
            page.focus(f"#{eid}")
            page.keyboard.type("1234567", delay=5)
            page.keyboard.press("Tab")
            page.wait_for_timeout(150)
            now = page.evaluate("() => document.activeElement && document.activeElement.id")
            checks.append({"name": "Keyboard replay: Tab leaves the field", "passed": bool(now) and now != eid, "detail": f"focus moved to #{now}"})
        if exists and barrier.kind == "mouse_only":
            ok_focus = page.evaluate("id => { const e = document.getElementById(id); e.focus(); return document.activeElement === e; }", eid)
            role = page.locator(f"#{eid}").aria_snapshot().split()[1] if ok_focus else ""
            checks.append({"name": "Keyboard replay: element takes focus with role button", "passed": ok_focus and role == "button", "detail": f"focusable={ok_focus}, role={role or 'none'}"})
            if ok_focus:
                before = page.url
                page.keyboard.press("Enter")
                page.wait_for_timeout(400)
                checks.append({"name": "Keyboard replay: Enter activates it", "passed": page.url != before, "detail": f"navigated to {Path(urlparse(page.url).path).name}"})
                page.goto(url)
        violations = [v["rule"] for v in axe_page(page) if any(f"#{eid}" in t for t in v["targets"])]
        checks.append({"name": "axe-core: no rule fails on this element", "passed": not violations, "detail": ", ".join(violations) or "0 violations on the element"})
    finally:
        page.close()
    return {"passed": all(c["passed"] for c in checks), "checks": checks}


class Run:
    def __init__(self, ctx, page, proc, engine, rec, approve, on_change, ws,
                 log: Callable = console, cancelled: Callable = lambda: False, pace: float = 0.0):
        self.ctx, self.page, self.proc, self.engine, self.rec, self.approve, self.on_change = ctx, page, proc, engine, rec, approve, on_change
        self.ws, self.log, self.cancelled, self.pace = ws, log, cancelled, pace
        self.barriers, self.patches, self.advisories, self.pending_verify = [], [], [], []
        self.pre_nav_shot = None

    def tick(self, scale=1.0):
        if self.cancelled():
            raise Cancelled()
        if self.pace:
            time.sleep(self.pace * scale)

    def hear(self, attempt, step, text, **extra):
        self.log(f"    {color('SR hears', 'cyan')}  “{text}”")
        return self.rec.add(attempt, step, "hear", text, **extra)

    def act(self, attempt, step, text, action, **extra):
        tag = color(f"[{action.decided_by}]", "magenta" if action.decided_by.startswith("LLM") else "dim")
        self.log(f"    {color('agent', 'dim')}     {text} {tag}")
        return self.rec.add(attempt, step, "action", text, engine=action.decided_by, llm=action.llm, **extra)

    def note_llm(self, attempt, step, action):
        if not action.llm:
            return
        out = action.llm["output"]
        self.log(color(f"    LLM ({action.llm['model']}, {action.llm['source']}, {action.llm['ms']} ms): {out['field_meaning']} | {out['reasoning']}", "magenta"))
        if not out.get("label_clear_for_screen_reader") and out.get("advisory") and action.kind == "fill":
            adv = {"step": step, "element": action.llm["field"], "heard": action.llm["heard"], "advisory": out["advisory"],
                   "model": action.llm["model"], "attempt": attempt}
            if not any(a["element"] == adv["element"] for a in self.advisories):
                self.advisories.append(adv)
                self.rec.add(attempt, step, "advisory", out["advisory"], engine=f"LLM {action.llm['model']}", llm=action.llm, focus=action.llm["field"])

    def walk_step(self, attempt, step):
        page, proc = self.page, self.proc
        heading = page.locator("h2").first.inner_text()
        self.hear(attempt, step, f"{page.title()}. {heading}", page=proc.steps[step - 1])
        captcha, tree = has_captcha(page)
        self.rec.add(attempt, step, "tree", tree)
        last = step == len(proc.steps)
        if last:
            self.rec.add(attempt, step, "reached", f"Reached the final confirmation step ({proc.step_names[-1]})", shot=self.rec.shot(page))
            self.log(color(f"  ✓ reached confirmation page at step {step}", "green"))
        if captcha:
            heard = "hình ảnh, CAPTCHA" if proc.lang == "vi-VN" else "画像, CAPTCHA"
            self.hear(attempt, step, heard, focus="captcha-img")
            b = make_barrier("captcha", step, "captcha-img", heard, "Image CAPTCHA with no audio or text alternative. The agent does not attempt it.")
            shot = self.rec.shot(page, "captcha-img", "#bf8700")
            self.rec.add(attempt, step, "handoff", "CAPTCHA detected: stop and hand off to a human officer. The submit button is never pressed.",
                         shot=shot, barrier=asdict(b), engine="rule (guard)", focus="captcha-img")
            self.log(color("  ■ CAPTCHA → hand off to human. Not bypassed. Not submitted.", "yellow"))
            self.barriers.append({**asdict(b), "attempt": attempt, "status": "handoff"})
            return "handoff", None
        filled, seen, prev, repeats = set(), [], None, 0
        for _ in range(MAX_TABS):
            self.tick()
            page.keyboard.press("Tab")
            page.wait_for_timeout(40)
            f = focused(page)
            key = f.element_id if f else None
            repeats = repeats + 1 if key and key == prev else 0
            if key and key != prev and key in seen:
                break
            if key and key not in seen:
                seen.append(key)
            prev = key
            self.hear(attempt, step, announce(f, proc.lang), focus=key)
            caption = caption_of(page, f.element_id) if f else ""
            action = self.engine.choose_action(Observation(step, f, repeats, filled, caption, heading, proc.key))
            self.note_llm(attempt, step, action)
            if action.kind == "fill":
                page.keyboard.press("Control+A")
                page.keyboard.type(action.value, delay=8)
                filled.add(f.element_id)
                ev = self.act(attempt, step, f"type “{action.value}” ({action.reason})", action, focus=f.element_id, value=action.value, op="fill")
                if action.llm:
                    ev["shot"] = self.rec.shot(page, f.element_id, "#6a3fc1")
            elif action.kind == "press":
                self.act(attempt, step, f"press {action.value} ({action.reason})", action, focus=f.element_id, op="press", value=action.value)
                if action.value == "Enter":
                    self.pre_nav_shot = self.rec.shot(page, f.element_id, "#1d7a46")
                    with page.expect_navigation():
                        page.keyboard.press("Enter")
                    return "next", None
                page.keyboard.press(action.value)
            elif action.kind == "refuse":
                self.act(attempt, step, f"skip “{f.name}” ({action.reason})", action, focus=f.element_id, op="refuse")
            elif action.kind == "barrier":
                b = make_barrier(action.value, step, f.element_id, announce(f, proc.lang), action.reason, caption,
                                 "Tab replay" if action.value == "keyboard_trap" else "accessibility-tree check")
                return "barrier", (b, action)
            elif action.kind == "handoff":
                self.act(attempt, step, f"hand off “{f.name}” ({action.reason})", action, focus=f.element_id, op="handoff")
                b = make_barrier("ambiguous_label" if action.value == "unknown_field" else "captcha", step, f.element_id, announce(f, proc.lang), action.reason, caption)
                self.rec.add(attempt, step, "handoff", f"Field meaning uncertain: handed to a human. {action.reason}", barrier=asdict(b),
                             shot=self.rec.shot(page, f.element_id, "#bf8700"), engine=action.decided_by, focus=f.element_id)
                self.barriers.append({**asdict(b), "attempt": attempt, "status": "handoff"})
                return "handoff", None
        if last:
            return "done", None
        mouse = find_mouse_only(page)
        if mouse:
            m = mouse[0]
            ev = (f"Full Tab cycle ({len(seen)} stops) never reached “{m['text']}”: it is a <{m['tag']}> with onclick, "
                  "not focusable, so Enter and Space cannot activate it")
            return "barrier", (make_barrier("mouse_only", step, m["id"], "(never announced: not in Tab order)", ev, m["text"], "Tab-order scan"), None)
        return "stuck", None

    def attempt(self, attempt):
        page, proc = self.page, self.proc
        self.log(color(f"\n=== [{proc.key.upper()}] Attempt {attempt}: restart the whole procedure from step 1 ===", "cyan"))
        self.rec.add(attempt, 1, "restart", f"Attempt {attempt}: start from step 1")
        self.tick(2)
        page.goto(self.ws.page_url(proc.key, "step1.html") + f"?attempt={attempt}")
        step = 1
        while True:
            self.log(color(f"  -- step {step}/{len(proc.steps)} --", "dim"))
            outcome, payload = self.walk_step(attempt, step)
            self.on_change()
            if outcome == "next":
                self.rec.add(attempt, step, "pass", f"Step {step} passed by keyboard only", shot=self.pre_nav_shot)
                for b in [b for b in self.pending_verify if b["step"] == step]:
                    self.rec.add(attempt, step, "verified",
                                 f"Verified by keyboard replay: step {step} now passes; #{b['element_id']} ({b['kind'].replace('_', ' ')}, WCAG {b['sc']}) no longer blocks",
                                 barrier=b, shot=self.pre_nav_shot, focus=b["element_id"])
                    b["status"] = "fixed"
                    b["verified_attempt"] = attempt
                    self.pending_verify.remove(b)
                    self.log(color(f"  ✓ VERIFIED (deterministic replay): #{b['element_id']} fixed", "green"))
                step = self.proc.steps.index(Path(urlparse(page.url).path).name) + 1
                continue
            if outcome == "barrier":
                return self.handle_barrier(attempt, *payload)
            return outcome

    def handle_barrier(self, attempt, b, action):
        page, proc = self.page, self.proc
        self.log(color(f"  ✗ BARRIER at step {b.step}: WCAG {b.sc} {b.sc_title} on #{b.element_id}", "red"))
        self.log(f"    evidence: {b.evidence}")
        if action and action.llm:
            self.note_llm(attempt, b.step, action)
        shot = self.rec.shot(page, b.element_id)
        self.rec.add(attempt, b.step, "barrier", b.evidence, shot=shot, barrier=asdict(b),
                     engine=action.decided_by if action else "rule (guard)", llm=action.llm if action else None, focus=b.element_id)
        self.on_change()
        file = proc.steps[b.step - 1]
        src = (self.ws.walk_dir / proc.key / file).read_text(encoding="utf-8")
        feedback, patch, check = "", None, None
        for round_no in (1, 2):
            self.tick()
            t0 = time.time()
            patch = self.engine.propose_patch(b, src, file, feedback)
            self.log(color(f"  patch by {patch.engine} in {time.time() - t0:.1f}s: {patch.summary}", "yellow"))
            check = precheck(self.ctx, self.ws, proc, b, file, patch.after)
            for c in check["checks"]:
                self.log(f"    precheck {'PASS' if c['passed'] else 'FAIL'}  {c['name']}: {c['detail']}")
            if check["passed"] or patch.engine == "rule":
                break
            feedback = "Deterministic pre-check failed: " + "; ".join(f"{c['name']}: {c['detail']}" for c in check["checks"] if not c["passed"])
            self.rec.add(attempt, b.step, "precheck_fail", feedback, engine=patch.engine)
            if round_no == 2:
                patch = RuleBasedEngine(proc).propose_patch(b, src, file)
                patch.engine = "rule fallback (LLM patch failed deterministic pre-check twice)"
                check = precheck(self.ctx, self.ws, proc, b, file, patch.after)
        diff = "".join(difflib.unified_diff(src.splitlines(True), patch.after.splitlines(True), f"a/{proc.key}/{file}", f"b/{proc.key}/{file}", n=1))
        for line in diff.splitlines():
            self.log("    " + (color(line, "green") if line.startswith("+") else color(line, "red") if line.startswith("-") else line))
        self.rec.add(attempt, b.step, "patch", patch.summary, diff=diff, file=file, shot=shot, engine=patch.engine, llm=patch.llm,
                     explanation_local=patch.explanation_local, precheck=check, barrier=asdict(b), focus=b.element_id)
        self.on_change()
        ok, who = self.approve({"procedure": proc.key, "attempt": attempt, "step": b.step, "element": b.element_id,
                                "summary": patch.summary, "explanation_local": patch.explanation_local, "diff": diff,
                                "engine": patch.engine, "precheck": check})
        self.rec.add(attempt, b.step, "approval", f"{'Approved' if ok else 'Rejected'} by {who}", approved=ok, who=who, focus=b.element_id)
        record = {**asdict(b), "attempt": attempt, "status": "approved" if ok else "rejected", "patch": patch.summary,
                  "patch_local": patch.explanation_local, "patch_engine": patch.engine, "diff": diff, "precheck": check}
        self.barriers.append(record)
        self.on_change()
        if not ok:
            self.log(color("  patch rejected: barrier stays open and goes to a human", "yellow"))
            return "rejected"
        write_atomic(self.ws.walk_dir / proc.key / file, patch.after)
        self.patches.append({"file": file, "summary": patch.summary, "diff": diff, "engine": patch.engine})
        self.pending_verify.append(record)
        return "patched"

    def run(self):
        final = "max_rounds"
        for attempt in range(1, MAX_ROUNDS + 1):
            result = self.attempt(attempt)
            if result != "patched":
                final = result
                break
        for b in self.pending_verify:
            b["status"] = "approved, not re-verified"
        return final


def sc_of(tags):
    return [".".join(m.groups()) for t in tags if (m := re.fullmatch(r"wcag(\d)(\d)(\d+)", t))]


def run_axe(page, ws, proc, folder_url):
    results = {}
    for file in proc.steps:
        page.goto(f"{ws.base}/{folder_url}/{proc.key}/{file}")
        results[file] = axe_page(page)
    return results


def compare(proc, barriers, axe_original):
    rows = []
    for b in barriers:
        hits = [v for v in axe_original[proc.steps[b["step"] - 1]] if any(f"#{b['element_id']}" in t for t in v["targets"])]
        rows.append({"step": b["step"], "kind": b["kind"], "sc": b["sc"], "element": b["element_id"], "agent": True,
                     "axe": bool(hits), "axe_rules": [h["rule"] for h in hits]})
    agent_ids = {(b["step"], b["element_id"]) for b in barriers}
    extra = []
    for i, file in enumerate(proc.steps, 1):
        for v in axe_original[file]:
            for t in v["targets"]:
                if not any(f"#{eid}" in t for s, eid in agent_ids if s == i):
                    extra.append({"step": i, "rule": v["rule"], "impact": v["impact"], "sc": sc_of(v["tags"]), "target": t, "help": v["help"]})
    return rows, extra


def audit_rows(barriers):
    rows = []
    for b in barriers:
        handoff = b["status"] == "handoff"
        fixed = b["status"] == "fixed"
        rows.append({
            "step": b["step"], "element": b["element_id"], "sc": b["sc"], "sc_title": b["sc_title"],
            "jis_title": JIS_TITLES[b["sc"]], "level": b["level"], "attempt": b["attempt"],
            "vn_result": "Không đạt – chuyển chuyên viên" if handoff else "Không đạt → đã sửa, kiểm lại đạt" if fixed else "Không đạt – chưa sửa",
            "jis_result": "不適合（人による確認へ）" if handoff else "不適合 → 修正後の再試験で適合" if fixed else "不適合（未修正）",
            "heard": b["heard"], "evidence": b["evidence"],
            "action": "Hand off to human (never bypassed)" if handoff else b.get("patch", ""),
            "action_local": "人による確認へ（回避しない）" if handoff else b.get("patch_local", ""),
            "patch_engine": b.get("patch_engine", ""), "verified_attempt": b.get("verified_attempt"),
        })
    return rows


def write_jis_csv(proc, rows, path):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["手続き", "ステップ", "対象要素", "達成基準", "達成基準の名称", "適合レベル", "初回試験結果", "修正後の再試験", "判定方法", "注記"])
        for r in rows:
            first = "不適合"
            retest = "適合" if "適合" in r["jis_result"].split("→")[-1] and "不適合" not in r["jis_result"].split("→")[-1] else "人による確認へ" if "人" in r["jis_result"] else "未実施"
            w.writerow([proc.title, r["step"], f"#{r['element']}", r["sc"], r["jis_title"], r["level"], first, retest,
                        "キーボード操作の再実行・アクセシビリティツリー・axe-core（決定的チェック）",
                        "模擬サイトでのチーム試験。準拠の自己宣言には使用不可。"])


def build_proc_data(proc, run, rec, final=None, submitted=None, axe=None):
    return {
        "key": proc.key, "country": proc.country, "title": proc.title, "title_en": proc.title_en, "lang": proc.lang,
        "steps": proc.steps, "step_names": proc.step_names, "goal": proc.goal, "standard": proc.standard,
        "final": final, "rounds": max([e["attempt"] for e in rec.events] or [0]),
        "submitted": submitted, "reached_confirmation": any(e["kind"] == "reached" for e in rec.events),
        "events": rec.events, "barriers": run.barriers if run else [], "patches": run.patches if run else [],
        "advisories": run.advisories if run else [], "audit": audit_rows(run.barriers) if run else [], "axe": axe,
    }
