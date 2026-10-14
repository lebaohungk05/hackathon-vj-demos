---
name: doc-authoring
description: Author procedure and handover documents in two editions - a customer edition that is steps and screenshots only, and a team edition that keeps the reasoning - as Excel, Word or PowerPoint, in VI/EN/JA or a mix, then produce the screenshot brief and publish to SharePoint. Use whenever the user asks to write, build, update or translate a guide, runbook, handover doc, manual, procedure, or deliverable for a customer, or says things like "làm doc", "tạo tài liệu", "viết hướng dẫn", "làm excel cho khách", "làm slide", "tạo guide", "update doc", "sửa tài liệu", "kéo doc từ sharepoint", "write a guide", "build a runbook", "customer deliverable", "手順書", "資料を作成". Also use when the user wants an existing SharePoint document pulled down and edited.
---

# Document authoring

A document written from guesswork is a document that gets rewritten. This skill exists because
the expensive failures are always the same two: **assuming what the reader needs**, and
**assuming what the environment does**. Both are fixed by asking and by testing, never by
inference.

## The rule that governs everything else

**Ask. Do not infer.** Audience, format, language, template, scope, who performs each step,
where it gets stored - all of it is asked before a line is written, and re-asked whenever the
answer would change the work. A wrong assumption discovered at review costs the whole document.

The second rule follows from the first: **verify against the real system, not against
documentation or memory.** If the document says a dialog offers three options, open the dialog.
If it says a menu path exists, walk it. A step that was never run is a step that does not work.

## Workflow

| Phase | Output | Gate |
|---|---|---|
| 1. Intake | Answers to every question in `references/intake.md` | Nothing is written until all are answered |
| 2. Structure | Section list, numbered, with the edition split agreed | User confirms the outline before prose |
| 3. Draft | Both editions built from one source | Build passes, editions structurally identical |
| 4. Screenshot brief | Numbered capture list with redaction rules | User captures; you verify each one |
| 5. Review | Edits applied as they arrive | Rebuild and re-read after every change |
| 6. Publish | File on SharePoint, link returned | Only after the user says it is final |

Phases 4 and 5 interleave. Requirements arrive mid-flight - from the user, from their manager,
from a customer reply. Expect it, apply it, rebuild, and say what changed.

## Where the files go

This skill runs in repositories it knows nothing about, so it never scatters files through an
existing tree. Everything for one document lives in **one folder**, decided once, before
anything is written.

**Probe first.** If the repository already builds documents, extend that rather than adding a
second convention beside it:

```bash
ls docs/ 2>/dev/null
grep -rl "openpyxl\|python-docx\|python-pptx" --include=*.py . | head
```

Found one? Say so, and use its content modules, its screenshot folder and its build entry point.
Two conventions in one repository is worse than an imperfect one.

**Found nothing?** Propose this and get the location confirmed:

```
<workdir>/              ask for it - suggest docs/<slug>/, never assume
  build.py              copied from assets/ - python build.py --edition customer-en
  xlsx_style.py         copied from assets/
  content/
    __init__.py
    customer_en.py      one module per edition x language
    customer_ja.py
    team_en.py
  screenshots/          captures, named by the brief
  out/                  generated .xlsx / .docx / .pptx
```

- **Write nothing outside `<workdir>`** unless the user names a path.
- **Nothing at the repository root.** A generated deliverable there is noise in every diff and
  every file listing someone else opens.
- **Resolve paths from the module**, `Path(__file__).resolve().parent`, never from the working
  directory - that differs between a terminal, a hook and an editor.
- **Ask whether `out/` is committed.** Some teams review the .xlsx in the pull request; others
  treat it as a build artifact and gitignore it. Both are reasonable, and guessing annoys one of
  them.
- The folder must run standalone: `python build.py` with `openpyxl` installed and nothing else
  from the host project. If the repository has no Python at all, keep the same shape anyway.

`assets/build.py` is that entry point, ready to copy: it renders every edition, prints the
screenshots still missing, and **exits non-zero when two language editions drift apart**, naming
the sheet and the block that diverged. Edit its `EDITIONS` and `PARITY_GROUPS` tables to match
the document; everything else works as shipped.

## Two editions, one source

Every document is written **once** and rendered twice. Never maintain two copies by hand; they
drift, and the drift is invisible until a customer reads the wrong one.

| | Customer edition | Team edition |
|---|---|---|
| Contains | Steps, screenshots, required role | Everything the customer edition has, plus why |
| Explanations | **None.** A reader following a procedure reads a "conclusion" as a step they missed | Full: what was tried, what failed, what it cost |
| Failure modes | Only when unrecoverable from the steps alone | All of them, with the error text |
| Identifiers | Redacted - see `references/screenshots.md` | Intact |
| Verification | Not shown | Commands and API calls that prove each step |

Load `references/editions.md` before drafting. The customer edition is harder than it looks:
cutting is the work, and every callout you keep has to earn its place.

## Formats

Ask which - one or several. Never pick for the user.

| Format | Template | Notes |
|---|---|---|
| **Excel** | `assets/xlsx_style.py` - copy it next to your content modules and import `build_workbook`. Needs only `openpyxl` | Best for step-by-step with screenshots. See `references/formats.md` |
| **Word** | No template yet - agree a style with the user first, then keep it | Best for prose-heavy handover |
| **PowerPoint** | No template ships with this skill. **Ask the user for one** and read its masters, fonts and colours rather than inventing them | Best for a review meeting |

Also ask the **look**: professional / minimal / dense / branded. Excel and Word have no fixed
house style, so the answer changes the build.

## Language

Ask: **VI, EN, JA, or a mix.** Mixed is common and specific - for example English UI labels with
Japanese prose, because a portal may be in either language and the reader matches labels against
a screen. When two language editions exist, they must stay **block-for-block identical** and the
build must fail if they drift. See `references/formats.md` for the parity check.

## Screenshots

Screenshots come **after** the document is built, never before. You cannot write a useful capture
brief until the steps are final, and a screenshot taken for a step that later changes is wasted
work you asked someone else to do.

The brief is per-image and specific: file name, where in the product it is taken, what must be
in frame, what to black out, and whether it can be staged or has to be captured live. Load
`references/screenshots.md`.

Then **check every capture you get back** against the caption you wrote. A caption that does not
describe its picture is worse than no caption. Fix the caption to match the capture rather than
asking for a re-shoot, unless the capture shows the wrong thing entirely.

## SharePoint

Documents live on SharePoint, not in the repo. Load `references/sharepoint.md` for the search →
pull → edit → upload flow, and for what to do when the connector is not authorised.

Before creating anything new, **search SharePoint for an existing document with that name.**
Editing the existing file keeps its link, its history and its permissions; a duplicate quietly
splits the truth in two.

## Before you finish

Read `references/pitfalls.md` at the start of any build, not after the first failure. It lists
the mistakes that have already cost hours on this work - file locks, encoding, style objects,
heredocs - and the one habit that catches the rest:

**Verify by reading the file back.** Never trust the call that wrote it.

```python
wb = openpyxl.load_workbook(path)
for ws in wb:
    print(ws.title, ws.max_row, len(ws._images))
# then assert every string that must survive is still there, unchanged and untranslated
```

## Improving this skill

When a document needs something this skill does not cover, extend it - but keep the additions
**general**. A rule that only fits one customer belongs in that project's notes; a rule about how
documents are written belongs here.
