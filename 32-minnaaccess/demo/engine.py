import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional, Protocol

from llm import HAIKU, SONNET
from procedures import PERSONA


def fold(text):
    text = unicodedata.normalize("NFD", text or "").replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in text if unicodedata.category(c) != "Mn").lower().strip()


@dataclass
class Focus:
    element_id: str
    role: str
    name: str
    value: str = ""
    checked: Optional[bool] = None


@dataclass
class Observation:
    step: int
    focus: Optional[Focus]
    tab_repeats: int
    filled: set = field(default_factory=set)
    caption: str = ""
    heading: str = ""
    procedure: str = ""


@dataclass
class Action:
    kind: str
    value: str = ""
    reason: str = ""
    decided_by: str = "rule"
    llm: Optional[dict] = None


@dataclass
class Barrier:
    kind: str
    step: int
    element_id: str
    sc: str
    sc_title: str
    heard: str
    evidence: str
    context_text: str = ""
    level: str = "A"
    check: str = ""


@dataclass
class Patch:
    file: str
    before: str
    after: str
    summary: str
    explanation_local: str = ""
    engine: str = "rule"
    llm: Optional[dict] = None


SC_CATALOG = {
    "unnamed_field": ("3.3.2", "Labels or Instructions", "A"),
    "ambiguous_label": ("2.4.6", "Headings and Labels", "AA"),
    "keyboard_trap": ("2.1.1", "Keyboard", "A"),
    "mouse_only": ("2.1.1", "Keyboard", "A"),
    "captcha": ("1.1.1", "Non-text Content", "A"),
}

JIS_TITLES = {
    "3.3.2": "ラベル又は説明",
    "2.4.6": "見出し及びラベル",
    "2.1.1": "キーボード",
    "1.1.1": "非テキストコンテンツ",
}

CODE_NAME = re.compile(r"^[a-z]{2,}(_[a-z0-9]+)+$", re.I)


def caption_core(caption):
    core = re.split(r"[（(*]", caption or "", maxsplit=1)[0]
    return core.strip()


def label_check(name, caption):
    if not (name or "").strip():
        return "unnamed", "accessible name is empty"
    core = caption_core(caption)
    if CODE_NAME.match(name.strip()) or (core and fold(core) not in fold(name)):
        return "name_mismatch", f"accessible name “{name}” does not contain the visible label “{core}”"
    return "ok", f"accessible name “{name}” contains the visible label"


class DecisionEngine(Protocol):
    name: str

    def choose_action(self, obs: Observation) -> Action: ...

    def propose_patch(self, barrier: Barrier, source: str, file: str, feedback: str = "") -> Patch: ...


class RuleBasedEngine:
    name = "rule-based (deterministic)"

    CONTINUE = re.compile(r"^(tiep tuc|continue|next|次へ)$")
    FORBIDDEN = re.compile(r"(nop ho so|gui|submit|dang nhap|login|thanh toan|申請する|送信|ログイン)")
    CAPTCHA = re.compile(r"(captcha|ma xac nhan|画像認証)")
    DECLARATION = re.compile(r"(cam doan|誓約|同意)")
    TRAP_REPEATS = 2

    def __init__(self, procedure=None):
        self.procedure = procedure

    def guard(self, obs):
        f = obs.focus
        if f is None:
            return Action("tab", decided_by="rule (guard)")
        name = fold(f.name)
        if obs.tab_repeats >= self.TRAP_REPEATS:
            return Action("barrier", "keyboard_trap", f"Tab pressed {obs.tab_repeats + 1} times, focus never left this field", "rule (guard)")
        if f.role == "textbox":
            if self.CAPTCHA.search(name):
                return Action("handoff", "captcha", "CAPTCHA input: never attempted, handed to a human", "rule (guard)")
            if f.element_id in obs.filled:
                return Action("tab", decided_by="rule (guard)")
            status, why = label_check(f.name, obs.caption)
            if status == "unnamed":
                return Action("barrier", "unnamed_field", f"Screen reader reads the field only as its role, with no name ({why}): a blind user cannot tell what to type", "rule (guard)")
            if status == "name_mismatch":
                return Action("barrier", "ambiguous_label", f"Screen reader reads a code instead of the label ({why})", "rule (guard)")
            return None
        if f.role == "checkbox":
            if self.DECLARATION.search(name) and not f.checked:
                return Action("press", "Space", "declaration checkbox", "rule (guard)")
            return Action("tab", decided_by="rule (guard)")
        if f.role in ("button", "link"):
            if self.FORBIDDEN.search(name):
                return Action("refuse", "", "guard: never submit, never log in", "rule (guard)")
            if self.CONTINUE.match(name):
                return Action("press", "Enter", "continue to next step", "rule (guard)")
        return Action("tab", decided_by="rule (guard)")

    def choose_action(self, obs):
        guarded = self.guard(obs)
        if guarded is not None:
            return guarded
        name = fold(obs.focus.name)
        for key, value in (self.procedure.rule_data if self.procedure else []):
            if fold(key) in name:
                return Action("fill", value, f"field name matches task data '{key}'", "rule")
        return Action("handoff", "unknown_field", "Field meaning is uncertain for the rule table", "rule")

    def propose_patch(self, barrier, source, file, feedback=""):
        handler = getattr(self, f"_patch_{barrier.kind}")
        after, summary = handler(barrier, source)
        return Patch(file, source, after, summary, engine="rule")

    def _patch_unnamed_field(self, b, src):
        eid = re.escape(b.element_id)
        pattern = re.compile(rf'<div class="lbl">(.*?)</div>(\s*)<input id="{eid}"', re.S)
        if pattern.search(src):
            out = pattern.sub(rf'<label class="lbl" for="{b.element_id}">\1</label>\2<input id="{b.element_id}"', src, count=1)
            return out, f"Turn the visual caption into a real <label for=\"{b.element_id}\"> so the field gets an accessible name"
        out = src.replace(f'id="{b.element_id}"', f'id="{b.element_id}" aria-label="{caption_core(b.context_text)}"', 1)
        return out, f"Add aria-label to #{b.element_id}"

    def _patch_ambiguous_label(self, b, src):
        cleaned = re.sub(rf'(<input id="{re.escape(b.element_id)}"[^>]*?)\s+aria-label="[^"]*"', r"\1", src, count=1)
        out, _ = self._patch_unnamed_field(b, cleaned)
        return out, f"Remove the code-like aria-label from #{b.element_id} and link the visible caption as its <label>"

    def _patch_keyboard_trap(self, b, src):
        eid = re.escape(b.element_id)
        script = re.compile(rf"<script[^>]*>(?:(?!</script>).)*getElementById\('{eid}'\)(?:(?!</script>).)*</script>\n?", re.S)
        m = script.search(src)
        body = re.search(r"if \(e\.key === 'Tab'\) \{ e\.preventDefault\(\); (.*?) \}", m.group(0), re.S) if m else None
        if body:
            tag = re.match(r"<script[^>]*>", m.group(0)).group(0)
            fixed = f"{tag}\ndocument.getElementById('{b.element_id}').addEventListener('blur', function () {{ {body.group(1)} }});\n</script>\n"
            return src.replace(m.group(0), fixed, 1), f"Stop swallowing the Tab key on #{b.element_id}; keep the formatting but run it on blur"
        return src.replace(m.group(0), "", 1), f"Remove the script that pulls focus back into #{b.element_id}"

    def _patch_mouse_only(self, b, src):
        eid = re.escape(b.element_id)
        pattern = re.compile(rf'<div([^>]*\bid="{eid}"[^>]*)>(.*?)</div>', re.S)
        out = pattern.sub(r'<button type="button"\1>\2</button>', src, count=1)
        return out, f"Replace the clickable <div id=\"{b.element_id}\"> with a native <button>, so Tab, Enter and Space work"


INTERPRET_SYSTEM = (
    "You are the field-interpretation module of MinnaAccess, an accessibility test agent that walks government web forms "
    "keyboard-only, the way a blind screen-reader user does, on LOCAL MOCK pages with FAKE data. "
    "For one focused form field you decide what it asks for and which value from the applicant profile to type. "
    "You never judge whether the page passes or fails accessibility; deterministic checks do that. "
    "Interpret Vietnamese administrative abbreviations (e.g. ĐKTT = đăng ký thường trú, permanent registered residence) and "
    "Japanese municipal terms (e.g. 本籍地 = registered domicile in the family register; foreign residents have none, forms ask for nationality instead). "
    "Abbreviations that a screen reader spells out letter by letter (such as ĐKTT) or internal codes are not clear to many blind users "
    "even when you can decode them: then set label_clear_for_screen_reader to false and write a one-line advisory with the expanded label. "
    "Choose handoff if the meaning is genuinely uncertain or the value is not derivable from the profile. "
    "Keep reasoning to 2 short plain-language sentences. Output JSON only."
)

INTERPRET_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["fill", "handoff"]},
        "value": {"type": "string"},
        "field_meaning": {"type": "string"},
        "label_clear_for_screen_reader": {"type": "boolean"},
        "advisory": {"type": "string"},
        "reasoning": {"type": "string"},
    },
    "required": ["decision", "value", "field_meaning", "label_clear_for_screen_reader", "advisory", "reasoning"],
}

PATCH_SYSTEM = (
    "You are the repair module of MinnaAccess. You receive one accessibility barrier that a deterministic keyboard and "
    "accessibility-tree check found on a LOCAL MOCK government form page, plus the page source. Write the smallest HTML/JS "
    "change that removes the barrier while keeping the page's behaviour (navigation, formatting) intact. "
    "Return edits as exact find/replace pairs: each 'find' must be copied verbatim from the source and occur exactly once. "
    "Do not add external URLs, network calls, new scripts from other origins, or anything that submits the form. "
    "Prefer native HTML (label, button) over ARIA. Then explain the fix in plain language a non-developer official can follow: "
    "'explanation' in English, 'explanation_local' in the page language. You do not decide whether the fix works; "
    "the agent re-runs the whole procedure and deterministic checks decide. Output JSON only."
)

PATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "edits": {"type": "array", "minItems": 1, "maxItems": 4, "items": {
            "type": "object", "properties": {"find": {"type": "string"}, "replace": {"type": "string"}}, "required": ["find", "replace"]}},
        "explanation": {"type": "string"},
        "explanation_local": {"type": "string"},
        "technique": {"type": "string"},
    },
    "required": ["edits", "explanation", "explanation_local", "technique"],
}

UNSAFE = re.compile(r"(https?://|<script[^>]*\bsrc=|fetch\(|XMLHttpRequest|\.submit\(|dataset\.submitted|<form|<iframe|eval\()", re.I)


def clean_text(value):
    if not isinstance(value, str):
        return value
    for marker in ("</", "<invoke", "<parameter"):
        if marker in value:
            value = value[:value.find(marker)]
    return value.strip()


def clean_output(obj):
    return {k: clean_text(v) for k, v in obj.items()}


def apply_edits(source, edits):
    out = source
    for e in edits:
        if out.count(e["find"]) != 1:
            raise ValueError(f"find text occurs {out.count(e['find'])} times (must be exactly once): {e['find'][:80]!r}")
        out = out.replace(e["find"], e["replace"], 1)
    return out


def patch_problems(source, edits, element_id):
    if not edits:
        return "no edits"
    if sum(len(e["find"]) + len(e["replace"]) for e in edits) > 4000:
        return "edits too large"
    for e in edits:
        if UNSAFE.search(e["replace"]) and not UNSAFE.search(e["find"]):
            return f"unsafe content in replacement: {UNSAFE.search(e['replace']).group(0)}"
    try:
        after = apply_edits(source, edits)
    except ValueError as exc:
        return str(exc)
    if after == source:
        return "edits do not change the page"
    if f'id="{element_id}"' not in after:
        return f"element #{element_id} disappeared; keep its id"
    return None


class LLMEngine:
    def __init__(self, client, procedure, model=HAIKU, patch_model=SONNET):
        self.client = client
        self.procedure = procedure
        self.model = model
        self.patch_model = patch_model
        self.rules = RuleBasedEngine(procedure)
        self.name = f"LLM ({model} decisions, {patch_model} patches) with rule fallback"

    def _meta(self, rec, extra):
        return {"model": rec.model, "source": rec.source, "ms": rec.ms, "tries": rec.tries, "ok": rec.ok,
                "error": rec.error, "key": rec.key, **extra}

    def interpret(self, obs):
        f = obs.focus
        prompt = json.dumps({
            "procedure": self.procedure.title_en,
            "page_language": self.procedure.lang,
            "page_heading": obs.heading,
            "focused_field": {"role": f.role, "accessible_name_read_by_screen_reader": f.name,
                              "visible_caption_next_to_field": obs.caption},
            "applicant_profile": PERSONA,
            "task": "Decide what this field asks for and the exact value to type. Say whether the accessible name alone is clear "
                    "to a blind user; if not, give a one-line advisory.",
        }, ensure_ascii=False, indent=1)

        def validate(o):
            if o.get("decision") == "fill" and not (o.get("value") or "").strip():
                return "decision is fill but value is empty"
            if len(o.get("value") or "") > 120:
                return "value too long"
            return None

        return self.client.ask("interpret field", self.model, INTERPRET_SYSTEM, prompt, INTERPRET_SCHEMA, validate)

    def choose_action(self, obs):
        guarded = self.rules.guard(obs)
        f = obs.focus
        needs_llm = f is not None and f.role == "textbox" and f.element_id not in obs.filled and not (
            guarded and guarded.value in ("captcha", "keyboard_trap"))
        if not needs_llm:
            return guarded if guarded is not None else self.rules.choose_action(obs)
        out, rec = self.interpret(obs)
        out = clean_output(out) if out else out
        if out is None:
            fallback = guarded or self.rules.choose_action(obs)
            fallback.decided_by = f"rule fallback ({rec.source}: {rec.error[:60] or 'LLM unavailable'})"
            return fallback
        meta = self._meta(rec, {"purpose": "interpret field", "field": f.element_id, "heard": f.name, "caption": obs.caption,
                                "output": out})
        if guarded is not None:
            guarded.llm = meta
            guarded.decided_by = "deterministic check (LLM explained)"
            return guarded
        if out["decision"] == "fill":
            return Action("fill", out["value"], out["field_meaning"], f"LLM {rec.model}", meta)
        return Action("handoff", "unknown_field", out["reasoning"], f"LLM {rec.model}", meta)

    def propose_patch(self, barrier, source, file, feedback=""):
        prompt = json.dumps({
            "barrier": {"kind": barrier.kind, "wcag": f"{barrier.sc} {barrier.sc_title}", "element_id": barrier.element_id,
                        "screen_reader_heard": barrier.heard, "evidence": barrier.evidence,
                        "visible_caption": barrier.context_text},
            "page_language": self.procedure.lang,
            "file": file,
            "source": source,
            "previous_attempt_feedback": feedback,
        }, ensure_ascii=False, indent=1)
        out, rec = self.client.ask("write patch", self.patch_model, PATCH_SYSTEM, prompt, PATCH_SCHEMA,
                                   lambda o: patch_problems(source, o.get("edits") or [], barrier.element_id))
        if out is None:
            p = self.rules.propose_patch(barrier, source, file)
            p.engine = f"rule fallback ({rec.source}: {rec.error[:80] or 'LLM unavailable'})"
            return p
        after = apply_edits(source, out["edits"])
        meta = self._meta(rec, {"purpose": "write patch", "output": out})
        return Patch(file, source, after, clean_text(out["explanation"]), clean_text(out["explanation_local"]), f"LLM {rec.model}", meta)
