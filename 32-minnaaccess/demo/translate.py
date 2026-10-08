import argparse
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from engine import clean_text
from llm import HAIKU, SONNET, ClaudeCLI, InfraError

ROOT = Path(__file__).resolve().parent
I18N = ROOT / "i18n"
CACHE_FILE = I18N / "translations.json"
JS_FILE = I18N / "translations.js"
LIVE_FILE = ROOT / "runs" / "translations_live.json"
LANGS = ("en", "ja", "vi")
LANG_NAME = {"en": "English", "ja": "Japanese", "vi": "Vietnamese"}
CJK = re.compile(r"[぀-ヿ㐀-鿿！-｠]")
BATCH = 18

STYLE = {
    "ja": "Write natural Japanese as used in Japanese government and IT accessibility documents (です・ます調 for sentences, "
          "short noun phrases stay noun phrases). Use common katakana for UI terms (スクリーンリーダー, ラベル, フォーカス, ボタン). ",
    "vi": "Write natural, plain Vietnamese as a Vietnamese public official would read it, with full diacritics. "
          "Use common terms: trình đọc màn hình, nhãn, ô nhập, nút, phím Tab, rào cản. ",
    "en": "Write plain, natural English. ",
}

LLM_SYSTEM = (
    "You translate short texts shown on the dashboard of MinnaAccess, an accessibility test agent that walks mock Vietnamese and "
    "Japanese e-government forms keyboard-only like a blind screen-reader user. Translate every item into {lang}. {style}"
    "Keep these exactly as they are, in their original script: words or phrases quoted from the form (Vietnamese such as "
    "\"Họ và tên\", \"Nơi ĐKTT\", Japanese such as 本籍地 or 「次へ」), personal data values, HTML tags and attributes "
    "(<label>, for=\"hoten\", aria-label), element ids and codes (#hoten, fld_hnsk_01), file names, WCAG numbers, key names "
    "(Tab, Enter, Space, Shift+Tab) and product names (NVDA, axe-core, Claude). Do not add or drop information, do not add notes. "
    "Return JSON only: {{\"items\": [{{\"id\": <same id>, \"text\": <translation>}}]}} with one entry per input item."
)

LABEL_SYSTEM = (
    "You translate field labels, button names, page headings and screen-reader announcements copied from mock Vietnamese and "
    "Japanese government web forms, so that a reader who does not know the source language understands what the form says. "
    "Translate every item into {lang}. {style}Keep it as short as the original: a label stays a label. Translate administrative "
    "terms by meaning (Nơi ĐKTT = place of permanent residence registration, 本籍地 = registered domicile). Keep numbers, dates, "
    "e-mail addresses, codes such as fld_hnsk_01, asterisks and punctuation. Japanese personal names in katakana and Vietnamese "
    "personal names stay as they are. Return JSON only: {{\"items\": [{{\"id\": <same id>, \"text\": <translation>}}]}} with one "
    "entry per input item."
)

SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {
        "type": "object", "properties": {"id": {"type": "integer"}, "text": {"type": "string"}}, "required": ["id", "text"]}}},
    "required": ["items"],
}


def norm(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def source_lang(text):
    return "ja" if CJK.search(text) else "vi"


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def load_run(path):
    text = Path(path).read_text(encoding="utf-8")
    return json.loads(text[text.index("{"): text.rindex("}") + 1])


def strip_tags(html):
    return norm(re.sub(r"<[^>]+>", " ", html).replace(" *", " ").replace("*", ""))


def portal_texts():
    out = set()
    for html_file in (ROOT / "portal").glob("*/*/*.html"):
        if html_file.parts[-3] in ("sandbox", "sandbox_staging", "live", "staging"):
            continue
        html = html_file.read_text(encoding="utf-8")
        for pattern in (r"<title>(.*?)</title>", r"<h1>(.*?)</h1>", r"<h2>(.*?)</h2>", r"<label[^>]*>(.*?)</label>",
                        r"<div class=\"lbl\">(.*?)</div>", r"<button[^>]*>(.*?)</button>", r"<div class=\"btn\"[^>]*>(.*?)</div>",
                        r"<option[^>]*>(.*?)</option>", r"<li[^>]*>\d\. (.*?)</li>"):
            for m in re.finditer(pattern, html, re.S):
                text = strip_tags(m.group(1))
                if text and not text.isascii():
                    out.add(text)
    return out


def heard_parts(heard):
    parts = {heard}
    for piece in re.split(r"\. (?=\S)", heard):
        parts.add(piece)
    for piece in heard.split(", "):
        parts.add(piece)
    return {norm(p) for p in parts if p and not norm(p).isascii()}


def collect():
    llm_texts, seeds, labels = set(), {}, set()

    def add_llm(text, local=None, page_lang=None):
        text = norm(clean_text(text))
        if not text:
            return
        llm_texts.add(text)
        if local and page_lang in ("vi", "ja"):
            seeds.setdefault(text, {})[page_lang] = norm(clean_text(local))

    def add_label(text):
        for part in heard_parts(norm(text)):
            labels.add(part)

    cache_files = list((ROOT / "cache").glob("*.json")) + list((ROOT / "runs" / "llm_cache").glob("*.json"))
    for f in cache_files:
        d = load_json(f)
        o = d.get("output") or {}
        try:
            prompt = json.loads(d.get("prompt") or "{}")
        except ValueError:
            prompt = {}
        page_lang = str(prompt.get("page_language", ""))[:2]
        if d.get("purpose") == "interpret field":
            for k in ("field_meaning", "reasoning", "advisory"):
                add_llm(o.get(k))
            field = prompt.get("focused_field") or {}
            add_label(field.get("accessible_name_read_by_screen_reader") or "")
            add_label(field.get("visible_caption_next_to_field") or "")
            add_label(prompt.get("page_heading") or "")
        elif d.get("purpose") == "write patch":
            add_llm(o.get("explanation"), o.get("explanation_local"), page_lang)
            b = prompt.get("barrier") or {}
            add_label(b.get("screen_reader_heard") or "")
            add_label(b.get("visible_caption") or "")
    procs = []
    for f in (ROOT / "out" / "run.json", ROOT / "out_rule" / "run.json"):
        if f.exists():
            procs += load_run(f)["procedures"]
    for f in (ROOT / "runs" / "live").glob("*/run.json"):
        procs.append(load_run(f)["procedure"])
    for P in procs:
        page_lang = P["lang"][:2]
        for e in P["events"]:
            if e["kind"] == "hear":
                add_label(e["text"])
            if e.get("barrier"):
                add_label(e["barrier"].get("heard") or "")
                add_label(e["barrier"].get("context_text") or "")
            if e["kind"] == "patch" and str(e.get("engine", "")).startswith("LLM"):
                add_llm(e["text"], e.get("explanation_local"), page_lang)
            m = e.get("llm")
            if m and m.get("output"):
                o = m["output"]
                for k in ("field_meaning", "reasoning", "advisory"):
                    add_llm(o.get(k))
                if o.get("explanation"):
                    add_llm(o["explanation"], o.get("explanation_local"), page_lang)
                add_label(m.get("heard") or "")
                add_label(m.get("caption") or "")
        for a in P.get("advisories") or []:
            add_llm(a["advisory"])
    for text in portal_texts():
        add_label(text)
    try:
        import barriers
        for opts in barriers.options().values():
            for targets in opts["targets"].values():
                for t in targets:
                    add_label(t["name"])
    except Exception as exc:
        print("barrier targets skipped:", exc, file=sys.stderr)
    labels = {t for t in labels if t and not t.isascii() and len(t) < 160}
    return llm_texts, seeds, labels


def wanted(llm_texts, labels):
    jobs = []
    for text in sorted(llm_texts):
        for lang in ("ja", "vi"):
            jobs.append(("llm", lang, text))
    for text in sorted(labels):
        src = source_lang(text)
        for lang in LANGS:
            if lang != src:
                jobs.append(("label", lang, text))
    return jobs


class Translator:
    def __init__(self, model=HAIKU, timeout=150, workdir=None):
        self.model = model
        self.client = ClaudeCLI("live", workdir or (ROOT / "runs" / "translate_tmp"), timeout=timeout)

    @property
    def available(self):
        return self.client.available

    def translate(self, kind, lang, texts):
        system = (LLM_SYSTEM if kind == "llm" else LABEL_SYSTEM).format(lang=LANG_NAME[lang], style=STYLE[lang])
        payload = {"target_language": LANG_NAME[lang], "items": [{"id": i, "text": t} for i, t in enumerate(texts)]}
        prompt = json.dumps(payload, ensure_ascii=False, indent=1)
        last = None
        for _ in range(2):
            try:
                obj = self.client._invoke(self.model, system, prompt, SCHEMA)
            except (InfraError, ValueError) as exc:
                last = exc
                continue
            got = {int(it["id"]): norm(it["text"]) for it in obj.get("items", []) if isinstance(it, dict) and str(it.get("id", "")).isdigit()}
            if all(got.get(i) for i in range(len(texts))):
                return [got[i] for i in range(len(texts))]
            last = ValueError(f"{len(got)} of {len(texts)} items returned")
        raise InfraError(f"translation failed: {last}")


def write_js(cache):
    I18N.mkdir(exist_ok=True)
    JS_FILE.write_text("window.TR_CACHE = " + json.dumps(cache, ensure_ascii=False, sort_keys=True) + ";\n", encoding="utf-8")


def save(cache):
    I18N.mkdir(exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    write_js(cache)


def build(jobs_n=4, limit=None, dry=False):
    llm_texts, seeds, labels = collect()
    cache = load_json(CACHE_FILE)
    for text, by_lang in seeds.items():
        entry = cache.setdefault(text, {})
        for lang, value in by_lang.items():
            entry.setdefault(lang, value)
    todo = [(k, lang, t) for k, lang, t in wanted(llm_texts, labels) if not cache.get(t, {}).get(lang)]
    print(f"{len(llm_texts)} LLM texts, {len(labels)} source labels, {len(seeds)} seeded; {len(todo)} translations missing")
    if dry or not todo:
        save(cache)
        return cache
    groups = {}
    for kind, lang, text in todo:
        groups.setdefault((kind, lang), []).append(text)
    batches = [(kind, lang, texts[i:i + BATCH]) for (kind, lang), texts in groups.items() for i in range(0, len(texts), BATCH)]
    if limit:
        batches = batches[:limit]
    lock = threading.Lock()
    tr = Translator()

    def work(batch):
        kind, lang, texts = batch
        t0 = time.time()
        try:
            out = tr.translate(kind, lang, texts)
        except Exception as exc:
            print(f"  FAIL {kind} {lang} x{len(texts)}: {exc}", flush=True)
            return 0
        with lock:
            for src, dst in zip(texts, out):
                cache.setdefault(src, {})[lang] = dst
            save(cache)
        print(f"  ok {kind} -> {lang} x{len(texts)} in {time.time() - t0:.0f} s", flush=True)
        return len(texts)

    with ThreadPoolExecutor(max_workers=jobs_n) as pool:
        done = sum(pool.map(work, batches))
    print(f"translated {done} strings")
    return cache


class LiveTranslator:
    def __init__(self, translator=None):
        self.shipped = load_json(CACHE_FILE)
        self.live = load_json(LIVE_FILE)
        self.lock = threading.Lock()
        self.queue = []
        self.failed = set()
        self.wake = threading.Event()
        self.translator = translator
        self.thread = None

    def get(self, text, lang):
        text = norm(text)
        return (self.shipped.get(text) or {}).get(lang) or (self.live.get(text) or {}).get(lang)

    def lookup(self, items, lang):
        found, pending = {}, []
        with self.lock:
            for it in items:
                text, kind = norm(it.get("text")), it.get("kind") if it.get("kind") in ("llm", "label") else "llm"
                if not text or lang not in LANGS:
                    continue
                hit = self.get(text, lang)
                if hit:
                    found[text] = hit
                elif (kind, lang, text) in self.failed:
                    continue
                else:
                    pending.append(text)
                    if (kind, lang, text) not in self.queue:
                        self.queue.append((kind, lang, text))
        if pending:
            self._ensure_worker()
            self.wake.set()
        return found, pending

    def _ensure_worker(self):
        if self.translator is None:
            self.translator = Translator(timeout=90)
        if not self.translator.available:
            with self.lock:
                self.failed.update(self.queue)
                self.queue.clear()
            return
        if self.thread is None or not self.thread.is_alive():
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()

    def _loop(self):
        while True:
            self.wake.wait(5)
            self.wake.clear()
            with self.lock:
                if not self.queue:
                    continue
                kind, lang, _ = self.queue[0]
                batch = [q for q in self.queue if q[0] == kind and q[1] == lang][:BATCH]
            texts = [q[2] for q in batch]
            try:
                out = self.translator.translate(kind, lang, texts)
            except Exception:
                out = None
            with self.lock:
                for q in batch:
                    if q in self.queue:
                        self.queue.remove(q)
                if out is None:
                    self.failed.update(batch)
                    continue
                for src, dst in zip(texts, out):
                    self.live.setdefault(src, {})[lang] = dst
                try:
                    LIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
                    LIVE_FILE.write_text(json.dumps(self.live, ensure_ascii=False, indent=1), encoding="utf-8")
                except OSError:
                    pass
                if self.queue:
                    self.wake.set()


def review(dict_file, out_file, lang):
    text = Path(dict_file).read_text(encoding="utf-8")
    body = text[text.index("{"): text.rindex("}") + 1]
    pairs = json.loads(body)
    items = [{"id": i, "en": en, lang: v[lang]} for i, (en, v) in enumerate(pairs.items()) if isinstance(v, dict) and v.get(lang)]
    name = LANG_NAME[lang]
    system = (
        f"You are a native {name} editor reviewing the {name} user-interface strings of MinnaAccess, a presentation dashboard of an "
        "accessibility test agent that walks mock Vietnamese and Japanese e-government forms keyboard-only like a blind screen-reader "
        "user. Each item has the English source and the current translation. Placeholders in braces like {n} or {name} must be kept "
        "exactly. Official terms must stay correct: WCAG success criterion numbers, JIS X 8341-3 terms (達成基準, 試験結果, 適合, 不適合), "
        "TT 21/2023. Flag only translations that are wrong, unnatural, too literal, inconsistent in terminology, or much longer than "
        "needed for a compact UI label. Return JSON only: {\"items\": [{\"id\": <id>, \"text\": <improved translation>, \"why\": <short reason in English>}]} "
        "listing only the items you change."
    )
    schema = {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {
        "id": {"type": "integer"}, "text": {"type": "string"}, "why": {"type": "string"}}, "required": ["id", "text", "why"]}}},
        "required": ["items"]}
    client = ClaudeCLI("live", ROOT / "runs" / "translate_tmp", timeout=600)
    changes = []
    for i in range(0, len(items), 120):
        chunk = items[i:i + 120]
        obj = client._invoke(SONNET, system, json.dumps(chunk, ensure_ascii=False, indent=1), schema)
        by_id = {it["id"]: it for it in chunk}
        for it in obj.get("items", []):
            src = by_id.get(it["id"])
            if src:
                changes.append({"en": src["en"], "old": src[lang], "new": it["text"], "why": it["why"]})
        print(f"  reviewed {i + len(chunk)}/{len(items)}", flush=True)
    Path(out_file).write_text(json.dumps(changes, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(changes)} suggested changes written to {out_file}")


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Build the shipped translation cache (i18n/translations.json + .js) with the claude CLI")
    sub = ap.add_subparsers(dest="cmd")
    b = sub.add_parser("build", help="translate every LLM text and quoted form label that is not cached yet")
    b.add_argument("--jobs", type=int, default=4)
    b.add_argument("--limit", type=int)
    b.add_argument("--dry", action="store_true", help="only count and seed, no CLI calls")
    r = sub.add_parser("review", help="ask Sonnet to review the UI strings of one language")
    r.add_argument("lang", choices=["ja", "vi"])
    r.add_argument("--out", default=str(ROOT / "runs" / "review.json"))
    args = ap.parse_args(argv)
    if args.cmd == "review":
        review(ROOT / "i18n" / "ui_strings.json", args.out, args.lang)
    else:
        build(getattr(args, "jobs", 4), getattr(args, "limit", None), getattr(args, "dry", False))


if __name__ == "__main__":
    main()
