"""Build every edition of one document - the skill's starting scaffold.

Copy this into `<workdir>/`, next to `xlsx_style.py` and a `content/` package, then:

    python build.py                                   # every edition
    python build.py --edition customer-en             # one of them
    python build.py --edition customer-en --edition customer-ja

Each entry in EDITIONS names a module under `content/` that exposes `sheets()`, returning a list
of `(sheet_name, blocks)` - optionally `(sheet_name, blocks, tab_colour)` or
`(sheet_name, blocks, tab_colour, hidden)`.

Exits non-zero when two editions of the same document drift apart structurally, so a dropped
section in a translation fails the build instead of reaching a customer.

Everything resolves from this file's own directory, so the command works the same from a
terminal, a hook or an editor.
"""
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from xlsx_style import build_workbook  # noqa: E402

# Callout labels, per language. Colour alone does not survive printing, and does not reach a
# reader who cannot distinguish the tints, so every callout carries a word.
LABELS_EN = {"ok": "CONCLUSION:", "warn": "WARNING:", "info": "NOTE:"}
LABELS_JA = {"ok": "結論:", "warn": "注意:", "info": "補足:"}
LABELS_VI = {"ok": "KẾT LUẬN:", "warn": "CẢNH BÁO:", "info": "GHI CHÚ:"}

# edition key -> (module under content/, output file name, labels)
EDITIONS = {
    "customer-en": ("customer_en", "Guide_EN.xlsx", LABELS_EN),
    "customer-ja": ("customer_ja", "Guide_JA.xlsx", LABELS_JA),
    "team-en": ("team_en", "Guide_Internal_EN.xlsx", LABELS_EN),
}

# Editions that are the same document in different languages, and must not drift. Add one group
# per document; editions with different content - customer versus team - belong in separate
# groups or none at all.
PARITY_GROUPS = [("customer-en", "customer-ja")]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--edition", choices=sorted(EDITIONS), action="append",
                        help="Build only this edition. Repeatable. Defaults to all.")
    parser.add_argument("--out-dir", type=Path, default=HERE / "out")
    parser.add_argument("--screenshots", type=Path, default=HERE / "screenshots")
    args = parser.parse_args()

    built: dict[str, list[tuple]] = {}
    for key in args.edition or sorted(EDITIONS):
        module_name, filename, labels = EDITIONS[key]
        try:
            module = importlib.import_module(f"content.{module_name}")
        except ModuleNotFoundError as missing:
            # EDITIONS ships with three entries; a document that has fewer is normal, and a
            # traceback is a poor way to say "you have not written that one yet".
            if missing.name != f"content.{module_name}":
                raise
            where = "requested" if args.edition else "listed in EDITIONS"
            print(f"{key}: skipped - content/{module_name}.py does not exist "
                  f"({where}). Create it, or drop the entry from EDITIONS.",
                  file=sys.stderr)
            continue
        sheets = module.sheets()
        built[key] = sheets
        path = build_workbook(sheets, args.out_dir / filename,
                              image_dir=args.screenshots, callout_labels=labels)
        blocks = sum(len(sheet[1]) for sheet in sheets)
        print(f"{key}: {path}  ({len(sheets)} sheets, {blocks} blocks)")

    report_missing_images(built, args.screenshots)
    return 0 if editions_match(built) else 1


def editions_match(built: dict[str, list[tuple]]) -> bool:
    """Every parity group must be structurally identical - block count and block types.

    Wording is what a translation is for; structure is not. A reader should be able to put two
    language editions side by side, and a reviewer who does not read one of them should still be
    able to see that nothing was dropped.
    """
    ok = True
    for group in PARITY_GROUPS:
        present = [key for key in group if key in built]
        if len(present) < 2:
            continue

        def shape(sheets: list[tuple]) -> list[tuple[int, list[str]]]:
            return [(len(sheet[1]), [b[0] for b in sheet[1]]) for sheet in sheets]

        reference = shape(built[present[0]])
        for other in present[1:]:
            if shape(built[other]) == reference:
                print(f"\n{present[0]} and {other} match structurally.")
                continue
            ok = False
            print(f"\nWARNING: {other} does not match {present[0]}.", file=sys.stderr)
            compared = shape(built[other])
            if len(compared) != len(reference):
                print(f"  sheet count: {present[0]}={len(reference)}, {other}={len(compared)}",
                      file=sys.stderr)
            for index, (left, right) in enumerate(zip(reference, compared)):
                if left == right:
                    continue
                name = built[present[0]][index][0]
                print(f"  sheet {index} ({name}): {left[0]} blocks vs {right[0]}",
                      file=sys.stderr)
                if left[1] != right[1]:
                    print(f"    {present[0]}: {left[1]}\n    {other}: {right[1]}",
                          file=sys.stderr)
    return ok


def report_missing_images(built: dict[str, list[tuple]], image_dir: Path) -> None:
    """List the screenshots the documents reference but the folder does not hold.

    A missing image renders as a placeholder rather than failing, so a slot can be committed
    before its capture exists. That is deliberate - and it also means a forgotten screenshot is
    invisible in the build output, which is what this prints.
    """
    wanted: dict[str, set[str]] = {}
    for key, sheets in built.items():
        for sheet in sheets:
            for block in sheet[1]:
                if block[0] == "image" and not (image_dir / block[1]).exists():
                    wanted.setdefault(block[1], set()).add(f"{key}/{sheet[0]}")

    if not wanted:
        return
    print(f"\n{len(wanted)} screenshot(s) still to capture into {image_dir}:")
    for filename in sorted(wanted):
        print(f"  {filename}")


if __name__ == "__main__":
    raise SystemExit(main())
