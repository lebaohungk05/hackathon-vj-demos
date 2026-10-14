# Formats and templates

Ask which format(s) and which look before building. Several formats at once is normal.

## Excel - the reference implementation

`assets/build.py` and `assets/xlsx_style.py` beside this skill are a working build entry point
and block engine. Copy it next to your content
modules and `from xlsx_style import build_workbook`; its only third-party requirement is
`openpyxl`. Content is data, layout is code, so one renderer serves every language and edition.

If the repository you are in already has its own copy, use that one - it is the one its tests
cover. The skill's copy exists so the skill works in a repository that has nothing.

Content is a list of `(sheet_name, blocks, tab_colour, hidden)`, and each block is a tuple whose
first element names its type:

| Block | Shape | Renders as |
|---|---|---|
| `title` | `("title", text)` | Sheet heading |
| `subtitle` | `("subtitle", text)` | One line under it, muted |
| `section` | `("section", text)` or `("section", text, band_colour)` | Banded heading |
| `table` | `("table", headers, rows)` | Bordered table; a cell may be `(text, url)` for a link |
| `note` `ok` `warn` `info` | `("warn", text)` | Tinted callout with a word label |
| `code` | `("code", [lines])` | Monospace block |
| `image` | `("image", filename, caption, where)` | Screenshot, caption below, location label above |
| `blank` | `("blank", n)` | Spacer |

Things that engine already solves, and that any replacement has to solve too:

- **Row heights are estimated, not left to Excel.** Wrapped text is clipped otherwise. CJK
  characters count as two units - a Japanese edition sized on Latin assumptions comes out one
  line short on every wrapped row.
- **Images are fitted inside a box**, aspect preserved, never enlarged, and real rows are
  reserved for their height so they do not float over the caption.
- **A missing image renders as a placeholder**, and the build prints what is still missing. A
  slot can be committed before its capture exists; a forgotten capture is otherwise invisible.
- **Tab colours group sheets.** When a workbook holds two alternative methods, numbering alone
  does not say so - 1.2 and 2.1 sit next to each other and read as one sequence.
- **Hidden sheets** are hidden by index, not by name, so every language edition hides the same
  one. Hide rather than delete: out of scope this week usually means back in scope later.
- **Numbering must stay contiguous in what the reader sees.** Hiding sheet 2.3 leaves tabs
  reading 2.2, 2.4 - which looks like a missing sheet. Renumber the visible ones and take the
  hidden one out of the sequence entirely.

## Word

No house template yet. Agree the style with the user first - headings, numbering, whether steps
are a table or a list - then keep it identical across the document set. Record the choice in the
project's notes so the next document matches.

`python-docx` is the tool. The same rules apply: content as data, one renderer, parity check
between languages, read the file back to verify.

## PowerPoint

**No template ships with this skill.** Ask the user for one and where it lives - a deck built on
invented masters looks wrong next to every other deck the team has produced, and that is obvious
to everyone in the room except its author.

Templates are usually customer-branded, so they are not committed here: one would then travel
into every repository this skill is installed in.

Read the template before building - open it with `python-pptx` and take the slide masters,
layouts, fonts and colour scheme from it rather than inventing them:

```python
from pptx import Presentation
prs = Presentation(TEMPLATE)
for i, layout in enumerate(prs.slide_layouts):
    print(i, layout.name, [ph.placeholder_format.type for ph in layout.placeholders])
```

Build on a copy of the template so the masters survive. Do not restyle text runs by hand when a
layout placeholder already carries the style.

## Look

Ask, and hold to the answer:

| Look | Means |
|---|---|
| **Professional** | Banded headings, bordered tables, a restrained accent colour, callouts with word labels |
| **Minimal** | No banding, no callout tints, whitespace and type weight only |
| **Dense** | Smaller type, tighter rows, more per page - for a reference someone scans, not follows |
| **Match an existing file** | Read that file and copy its widths, fonts and colours; do not approximate |

Colour must never be the only carrier of meaning - a callout gets a word label too, for print and
for readers who cannot distinguish the tints.
