#!/usr/bin/env python
"""update_evm_pv.py — edit the "PV (Kế hoạch)" tab of an EVM report workbook.

Uses xlwings (real Excel) so conditional formatting on SPI/CPI is preserved and
Excel auto-adjusts formula references / SUM ranges when rows are inserted/deleted.

Cross-sheet model (all formula sheets reference PV/EV/AC by the SAME absolute row):
  - set / rename .......... touch PV only (rename also syncs AC col C, which is hardcoded)
  - add / remove .......... insert/delete the SAME row index on ALL 6 sheets
  - move (reorder) ........ permute the "manual payload" of each row; formula cells
                            stay put and recompute (no row insert/delete needed)

Usage:
  python update_evm_pv.py show  --file "PATH"
  python update_evm_pv.py apply --file "PATH" --ops ops.json

ops.json is a JSON list of operations (processed sequentially, matches re-resolved
each step). See README block at the bottom of this file for the op schema.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

# --- column / layout constants -------------------------------------------------
FIRST_WEEK_COL = 4          # column D — DEFAULT; detect_layout() may shift it right
TITLE_COL = 3               # column C ("Hạng mục công việc")
NO_COL = 2                  # column B ("No.")
ASSIGNEE_COL = None         # set by detect_layout() if a "Người phụ trách" column exists
TOTAL_HEADER = "Tổng"
HEADER_ROW = 2
FIRST_DATA_ROW = 3
BOUNDARY_MARKER = "Không chèn"   # text at the start of the gray boundary row


def _eprint(*a):
    print(*a, file=sys.stderr)


def detect_layout(pv):
    """Adapt to the sheet's actual column layout by reading header row 2.

    The base template is  B=No | C=Hạng mục | D..=weeks | Tổng. A newer variant
    inserts an assignee column: B=No | C=Hạng mục | D=Người phụ trách | E..=weeks.
    Sets the module globals FIRST_WEEK_COL and ASSIGNEE_COL so every downstream
    function works on either layout without hardcoding column positions."""
    global FIRST_WEEK_COL, ASSIGNEE_COL
    tc = total_col(pv)
    first_week = None
    for c in range(TITLE_COL + 1, tc):
        h = pv.range((HEADER_ROW, c)).value
        if isinstance(h, str) and re.search(r"Tuần\s*\d+", h):
            first_week = c
            break
    FIRST_WEEK_COL = first_week if first_week else TITLE_COL + 1
    # any column between the title and the first week column is the assignee column
    # (position-based, so no fragile Vietnamese string matching / NFC-NFD issues)
    ASSIGNEE_COL = FIRST_WEEK_COL - 1 if FIRST_WEEK_COL - 1 > TITLE_COL else None
    return {"first_week_col": FIRST_WEEK_COL, "assignee_col": ASSIGNEE_COL,
            "total_col": tc}


# --- sheet resolution (robust to minor naming differences) ---------------------
def resolve_sheets(wb):
    """Return a dict of logical name -> xlwings sheet, matched by prefix/keyword."""
    by = {s.name: s for s in wb.sheets}
    found = {}
    for name, sheet in by.items():
        low = name.lower()
        if low.startswith("pv"):
            found["pv"] = sheet
        elif "lũy kế" in low or "luy ke" in low:
            found["ev_cum"] = sheet
        elif "hoàn thành" in low or "hoan thanh" in low:
            found["ev_done"] = sheet
        elif low.startswith("spi"):
            found["spi"] = sheet
        elif low.startswith("ac"):
            found["ac"] = sheet
        elif low.startswith("cpi"):
            found["cpi"] = sheet
    missing = {"pv", "ev_cum", "ev_done", "spi", "ac", "cpi"} - set(found)
    if missing:
        raise SystemExit(f"ERROR: workbook is missing expected sheets: {missing}. "
                         f"Sheets present: {list(by)}")
    return found


def total_col(ws) -> int:
    """Column index of the 'Tổng' column (one past the last week column)."""
    c = FIRST_WEEK_COL
    last = ws.cells.last_cell.column
    while c <= last:
        v = ws.range((HEADER_ROW, c)).value
        if isinstance(v, str) and v.strip() == TOTAL_HEADER:
            return c
        c += 1
    raise SystemExit("ERROR: could not find the 'Tổng' header column on the PV sheet.")


def boundary_row(ws) -> int:
    """Row index of the gray 'Không chèn...' boundary row."""
    r = FIRST_DATA_ROW
    last = ws.cells.last_cell.row
    while r <= last:
        v = ws.range((r, TITLE_COL)).value
        if isinstance(v, str) and v.strip().startswith(BOUNDARY_MARKER):
            return r
        r += 1
    raise SystemExit(f"ERROR: could not find the boundary marker '{BOUNDARY_MARKER}'.")


def week_cols(ws):
    """Return list of (week_number:int, col:int, date:str) parsed from header row."""
    tc = total_col(ws)
    out = []
    for c in range(FIRST_WEEK_COL, tc):
        h = ws.range((HEADER_ROW, c)).value
        wn, date = None, ""
        if isinstance(h, str):
            m = re.search(r"Tuần\s*(\d+)", h)
            if m:
                wn = int(m.group(1))
            parts = h.split("\n", 1)
            if len(parts) == 2:
                date = parts[1].strip()
        out.append((wn if wn is not None else (c - FIRST_WEEK_COL + 1), c, date))
    return out


def parse_id(title) -> int | None:
    if isinstance(title, str):
        m = re.search(r"#(\d+)", title)
        if m:
            return int(m.group(1))
    return None


def data_rows(pv):
    """Yield (row, no, id, title) for every populated/usable data row above boundary."""
    b = boundary_row(pv)
    rows = []
    for r in range(FIRST_DATA_ROW, b):
        title = pv.range((r, TITLE_COL)).value
        no = pv.range((r, NO_COL)).value
        rows.append((r, no, parse_id(title), title))
    return rows, b


# --- matching -------------------------------------------------------------------
def find_row(pv, match: dict) -> int:
    """Resolve a match spec to an absolute PV row index. Raises if 0 or >1 matches."""
    if "row" in match:
        return int(match["row"])
    rows, _ = data_rows(pv)
    cands = []
    for r, no, wid, title in rows:
        if "id" in match and wid == int(match["id"]):
            cands.append(r)
        elif "title_contains" in match and isinstance(title, str) \
                and match["title_contains"].lower() in title.lower():
            cands.append(r)
    if not cands:
        raise SystemExit(f"ERROR: no PV row matches {match}")
    if len(cands) > 1:
        raise SystemExit(f"ERROR: {match} is ambiguous, matched rows {cands}")
    return cands[0]


# --- operations -----------------------------------------------------------------
def op_set(sheets, op):
    pv = sheets["pv"]
    r = find_row(pv, op["match"])
    wcols = {wn: c for wn, c, _ in week_cols(pv)}
    items = op["values"].items() if "values" in op else [(op["week"], op.get("value"))]
    for wk, val in items:
        wk = int(wk)
        if wk not in wcols:
            raise SystemExit(f"ERROR: week {wk} out of range (have {sorted(wcols)})")
        pv.range((r, wcols[wk])).value = None if val in ("", None) else float(val)
    return f"set row {r} weeks {[int(w) for w, _ in items]}"


def op_rename(sheets, op):
    pv, ac = sheets["pv"], sheets["ac"]
    r = find_row(pv, op["match"])
    pv.range((r, TITLE_COL)).value = op["title"]
    ac.range((r, TITLE_COL)).value = op["title"]   # AC col C is hardcoded, keep in sync
    return f"renamed row {r} -> {op['title']!r}"


def _insert_row_all(sheets, idx):
    """Insert a blank row at idx on every sheet, then fill new rows by copying the
    row above (formulas + format).

    Two passes are required: insert on ALL sheets FIRST, then copy. Inserting a row
    shifts every workbook formula that references rows >= idx by +1. If we copied a
    sheet's new row before a later sheet's insert, that later insert would shift the
    fresh cross-sheet references we just wrote (off-by-one). Doing all inserts first
    makes every reference shift consistently, so a relative copy lands on row idx
    everywhere."""
    # Copy only the used columns (B..Tổng). `cells.last_cell.column` is the sheet's
    # absolute last column (16384) — copying that many cells per row, 6 sheets ×
    # every add, is catastrophically slow and destabilizes Excel.
    tc = total_col(sheets["pv"])
    for ws in sheets.values():
        ws.api.Rows(idx).Insert()  # shifts down, blank row
    for ws in sheets.values():
        above = ws.range((idx - 1, 1), (idx - 1, tc))
        above.api.Copy(ws.range((idx, 1)).api)


def _next_empty_row(pv):
    """First data row (3..boundary-1) whose PV title cell is empty, else None."""
    b = boundary_row(pv)
    for r in range(FIRST_DATA_ROW, b):
        if not pv.range((r, TITLE_COL)).value:
            return r, b
    return None, b


def _write_new_item(sheets, idx, title, values, assignee=None):
    """Populate row `idx` for a new item. Assumes the row already holds the standard
    formulas (either a template empty row, or a freshly inserted+copied row).

    Week cells are written as one whole-row range per sheet — assigning cell-by-cell
    in a loop is ~24 COM round-trips per sheet and makes a 16-item batch crawl."""
    pv = sheets["pv"]
    tc = total_col(pv)
    n = tc - FIRST_WEEK_COL  # number of week columns
    week_row = [None] * n
    if values:
        wcols = {wn: c for wn, c, _ in week_cols(pv)}
        for wk, val in values.items():
            week_row[wcols[int(wk)] - FIRST_WEEK_COL] = None if val in ("", None) else float(val)
    pv.range((idx, TITLE_COL)).value = title                       # B=ROW()-2, AB=SUM kept
    if ASSIGNEE_COL and assignee is not None:
        pv.range((idx, ASSIGNEE_COL)).value = assignee             # "Người phụ trách"
    pv.range((idx, FIRST_WEEK_COL), (idx, tc - 1)).value = week_row
    sheets["ev_cum"].range((idx, FIRST_WEEK_COL), (idx, tc - 1)).value = [None] * n
    ac = sheets["ac"]                                              # AC No.+title hardcoded
    ac.range((idx, NO_COL)).value = idx - 2
    ac.range((idx, TITLE_COL)).value = title
    ac.range((idx, FIRST_WEEK_COL), (idx, tc - 1)).value = [None] * n
    sheets["cpi"].range((idx, NO_COL)).value = idx - 2
    # EV (done) + SPI: pure formulas already present — leave


def op_add(sheets, op):
    pv = sheets["pv"]
    explicit = ("index" in op) or ("after" in op) or ("before" in op)
    if explicit:
        b = boundary_row(pv)
        if "index" in op:
            idx = int(op["index"])
        elif "after" in op:
            idx = find_row(pv, op["after"]) + 1
        else:
            idx = find_row(pv, op["before"])
        if idx >= b or idx < FIRST_DATA_ROW:
            idx = b
        _insert_row_all(sheets, idx)            # structural insert (copies formulas)
        _write_new_item(sheets, idx, op.get("title", ""), op.get("values"), op.get("assignee"))
        return f"inserted row at {idx}: {op.get('title','')!r}"
    # append: reuse the next templated empty row (no insert); grow only when full
    idx, b = _next_empty_row(pv)
    if idx is None:
        _insert_row_all(sheets, b)
        idx = b
    _write_new_item(sheets, idx, op.get("title", ""), op.get("values"), op.get("assignee"))
    return f"added row at {idx}: {op.get('title','')!r}"


def op_remove(sheets, op):
    pv = sheets["pv"]
    r = find_row(pv, op["match"])
    for ws in sheets.values():
        ws.api.Rows(r).Delete()
    return f"removed row {r}"


def _payload_of(sheets, r, tc):
    """Read the movable manual payload of a data row (title + manual week data)."""
    pv, ev, ac = sheets["pv"], sheets["ev_cum"], sheets["ac"]
    span = lambda ws: ws.range((r, FIRST_WEEK_COL), (r, tc - 1)).value
    return {
        "pv_title": pv.range((r, TITLE_COL)).value,
        "pv_weeks": span(pv),
        "ev_weeks": span(ev),
        "ac_title": ac.range((r, TITLE_COL)).value,
        "ac_weeks": span(ac),
    }


def _write_payload(sheets, r, tc, p):
    pv, ev, ac = sheets["pv"], sheets["ev_cum"], sheets["ac"]
    pv.range((r, TITLE_COL)).value = p["pv_title"]
    pv.range((r, FIRST_WEEK_COL), (r, tc - 1)).value = p["pv_weeks"]
    ev.range((r, FIRST_WEEK_COL), (r, tc - 1)).value = p["ev_weeks"]
    ac.range((r, TITLE_COL)).value = p["ac_title"]
    ac.range((r, FIRST_WEEK_COL), (r, tc - 1)).value = p["ac_weeks"]


def op_move(sheets, op):
    """Move a row so it lands at an absolute target row, by permuting the manual
    payloads of the contiguous block between source and target. Formula cells stay
    put and recompute — no row insert/delete, so cross-sheet refs never break.

    Target resolution (`dst` = the row `moving` should occupy in the FINAL sheet):
      - index N : dst = N (canonical; call `show` first to get exact rows)
      - after X : land immediately below X
      - before X: land immediately above X
    """
    pv = sheets["pv"]
    tc = total_col(pv)
    b = boundary_row(pv)
    src = find_row(pv, op["match"])
    if "index" in op:
        dst = int(op["index"])
    elif "after" in op:
        x = find_row(pv, op["after"])
        dst = x if src < x else x + 1
    elif "before" in op:
        x = find_row(pv, op["before"])
        dst = x - 1 if src < x else x
    else:
        raise SystemExit("ERROR: move needs 'index', 'before', or 'after'")
    dst = max(FIRST_DATA_ROW, min(dst, b - 1))
    if dst == src:
        return f"move no-op (row {src})"

    lo, hi = min(src, dst), max(src, dst)
    rows = list(range(lo, hi + 1))
    payloads = [_payload_of(sheets, r, tc) for r in rows]
    moving = payloads.pop(src - lo)        # remove source from the sequence
    payloads.insert(dst - lo, moving)      # reinsert at the target slot
    for r, p in zip(rows, payloads):
        _write_payload(sheets, r, tc, p)
    return f"moved row {src} -> {dst}"


OPS = {"set": op_set, "rename": op_rename, "add": op_add,
       "remove": op_remove, "move": op_move}


# --- commands -------------------------------------------------------------------
def _quiet(app):
    """Suppress modal dialogs and screen refresh. (Calculation mode is set to manual
    separately, AFTER a workbook is open — Excel rejects the Calculation property
    when no workbook exists.)"""
    app.display_alerts = False
    app.screen_updating = False


def _teardown(app):
    """Force-terminate Excel. A graceful wb.close()/app.quit() can hang for minutes
    on some Excel builds (observed: quit=304s while save took 0.1s). The workbook is
    already saved by the time we get here, so killing the process is safe and instant."""
    try:
        app.kill()
    except Exception:
        try:
            app.quit()
        except Exception:
            pass


def cmd_show(args):
    import xlwings as xw
    app = xw.App(visible=False, add_book=False)
    _quiet(app)
    try:
        wb = app.books.open(args.file, update_links=False)
        sheets = resolve_sheets(wb)
        pv = sheets["pv"]
        detect_layout(pv)
        b = boundary_row(pv)
        tc = total_col(pv)
        wcols = week_cols(pv)
        # one bulk read of the whole data block (cols B..Tổng) instead of per-cell
        block = pv.range((FIRST_DATA_ROW, NO_COL), (b - 1, tc)).value
        if b - 1 == FIRST_DATA_ROW:           # single row → xlwings returns a flat list
            block = [block]
        items = []
        for i, vals in enumerate(block):
            r = FIRST_DATA_ROW + i
            no, title = vals[0], vals[1]
            wv = {}
            for wn, c, _ in wcols:
                v = vals[c - NO_COL]          # offset within the B..Tổng slice
                if v not in (None, 0):
                    wv[wn] = v
            items.append({"row": r, "no": no, "id": parse_id(title), "title": title,
                          "weeks": wv})
        out = {
            "file": args.file,
            "boundary_row": b,
            "total_col": total_col(pv),
            "capacity_rows": b - FIRST_DATA_ROW,
            "used_rows": sum(1 for it in items if it["title"]),
            "weeks": [{"n": wn, "date": d} for wn, _, d in wcols],
            "items": [it for it in items if it["title"]],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    finally:
        _teardown(app)


def cmd_apply(args):
    import xlwings as xw
    with open(args.ops, encoding="utf-8") as f:
        ops = json.load(f)
    if not isinstance(ops, list):
        raise SystemExit("ERROR: ops file must be a JSON list of operations")
    app = xw.App(visible=False, add_book=False)
    _quiet(app)
    log = []
    try:
        wb = app.books.open(args.file, update_links=False)
        app.calculation = "manual"  # avoid full recalc per insert; recalc once below
        sheets = resolve_sheets(wb)
        detect_layout(sheets["pv"])
        for i, op in enumerate(ops):
            fn = OPS.get(op.get("op"))
            if not fn:
                raise SystemExit(f"ERROR: op #{i} has unknown 'op': {op.get('op')!r}")
            log.append(fn(sheets, op))
        app.calculate()  # single recalc after all ops (calculation is manual)
        wb.save()
    finally:
        _teardown(app)
    print(json.dumps({"applied": len(log), "log": log}, ensure_ascii=False, indent=2))


def cmd_replan(args):
    """Re-spread every item's planned man-days across the week columns with a fixed
    weekly capacity — the same scheduling generate-evm-report uses, but applied in
    place (the file, rows, formatting and other sheets are untouched).

    Each item's total md is taken from its current PV row total (sum of D:AA), so the
    per-item totals are preserved; only the week-by-week distribution is rebuilt. Items
    with 0 md stay blank. man-days fill the current week up to `capacity`, then overflow
    to the next week (a single item may split across a week boundary). Values rounded
    to 2 dp."""
    import xlwings as xw
    app = xw.App(visible=False, add_book=False)
    _quiet(app)
    moved = 0
    try:
        wb = app.books.open(args.file, update_links=False)
        app.calculation = "manual"
        sheets = resolve_sheets(wb)
        pv = sheets["pv"]
        detect_layout(pv)
        b = boundary_row(pv)
        tc = total_col(pv)
        nweeks = tc - FIRST_WEEK_COL
        # current md per item (row order = schedule order), from existing row totals
        plan = []
        for r in range(FIRST_DATA_ROW, b):
            title = pv.range((r, TITLE_COL)).value
            if not title:
                continue
            vals = pv.range((r, FIRST_WEEK_COL), (r, tc - 1)).value
            if not isinstance(vals, list):
                vals = [vals]
            md = sum(v for v in vals if isinstance(v, (int, float)))
            plan.append((r, round(md, 4)))
        # clear all data-row week cells, then capacity-fill
        for r, _ in plan:
            pv.range((r, FIRST_WEEK_COL), (r, tc - 1)).value = [None] * nweeks
        cap = float(args.capacity)
        wk = args.start_week - 1          # 0-based week index
        rem = cap
        for r, md in plan:
            if md <= 1e-9:
                continue
            row = [0.0] * nweeks
            left = md
            while left > 1e-9 and wk < nweeks:
                take = min(left, rem)
                row[wk] += take
                left -= take
                rem -= take
                if rem <= 1e-9:
                    wk += 1
                    rem = cap
            if left > 1e-9:               # ran past the last week → dump in the last one
                row[nweeks - 1] += left
            pv.range((r, FIRST_WEEK_COL), (r, tc - 1)).value = [
                round(v, 2) if v > 1e-9 else None for v in row]
            moved += 1
        app.calculate()
        wb.save()
    finally:
        _teardown(app)
    print(json.dumps({"replanned_items": moved, "capacity": args.capacity,
                      "start_week": args.start_week}, ensure_ascii=False, indent=2))


def _fill_person(row, wk, rem, cap, md, nweeks):
    """Place `md` onto one person's timeline starting at (wk, rem). Mutates `row`
    (a per-week list) and returns the advanced (wk, rem)."""
    left = md
    while left > 1e-9 and wk < nweeks:
        take = min(left, rem)
        row[wk] += take
        left -= take
        rem -= take
        if rem <= 1e-9:
            wk += 1
            rem = cap
    if left > 1e-9:
        row[nweeks - 1] += left
    return wk, rem


def cmd_replan_team(args):
    """Per-assignee capacity scheduling. Each person has an independent weekly
    capacity (man-days/week) and their own timeline; tasks assigned to a person are
    packed sequentially (row order) on that timeline, so different people's work runs
    in parallel. A task's md may split across week boundaries. Per-item totals are
    preserved (md taken from current row totals). Items whose id is unscheduled or
    whose assignee has no capacity entry are left blank.

    Spec JSON:
      {
        "start_week": 1,
        "weekly_cap_by_person": {"Hoang Tung Anh": 5.0, "Do Hai Hung": 2.5, ...},
        "assignee_by_id": {"5803": "Do Hai Hung", ...},
        "unscheduled_ids": [5815]
      }
    """
    import xlwings as xw
    spec = json.load(open(args.spec, encoding="utf-8"))
    caps = {k: float(v) for k, v in spec["weekly_cap_by_person"].items()}
    assignee_by_id = {int(k): v for k, v in spec["assignee_by_id"].items()}
    unscheduled = {int(x) for x in spec.get("unscheduled_ids", [])}
    start = int(spec.get("start_week", 1))
    app = xw.App(visible=False, add_book=False)
    _quiet(app)
    scheduled, skipped = [], []
    try:
        wb = app.books.open(args.file, update_links=False)
        app.calculation = "manual"
        sheets = resolve_sheets(wb)
        pv = sheets["pv"]
        detect_layout(pv)
        b = boundary_row(pv)
        tc = total_col(pv)
        nweeks = tc - FIRST_WEEK_COL
        plan = []
        for r in range(FIRST_DATA_ROW, b):
            title = pv.range((r, TITLE_COL)).value
            if not title:
                continue
            vals = pv.range((r, FIRST_WEEK_COL), (r, tc - 1)).value
            if not isinstance(vals, list):
                vals = [vals]
            md = round(sum(v for v in vals if isinstance(v, (int, float))), 4)
            plan.append((r, parse_id(title), md))
        for r, _, _ in plan:
            pv.range((r, FIRST_WEEK_COL), (r, tc - 1)).value = [None] * nweeks
        cursor = {name: [start - 1, caps[name]] for name in caps}  # [week_idx, remaining]
        for r, wid, md in plan:
            if md <= 1e-9:
                continue
            name = assignee_by_id.get(wid)
            if wid in unscheduled or name not in caps:
                skipped.append(wid)
                continue
            wk, rem = cursor[name]
            row = [0.0] * nweeks
            wk, rem = _fill_person(row, wk, rem, caps[name], md, nweeks)
            cursor[name] = [wk, rem]
            pv.range((r, FIRST_WEEK_COL), (r, tc - 1)).value = [
                round(v, 2) if v > 1e-9 else None for v in row]
            scheduled.append(wid)
        app.calculate()
        wb.save()
    finally:
        _teardown(app)
    print(json.dumps({"scheduled": len(scheduled), "skipped_unscheduled": skipped,
                      "start_week": start}, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(description="Edit the PV (Kế hoạch) tab of an EVM report.")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("show", help="Dump PV tab state as JSON")
    s.add_argument("--file", required=True)
    s.set_defaults(func=cmd_show)
    a = sub.add_parser("apply", help="Apply a JSON list of operations")
    a.add_argument("--file", required=True)
    a.add_argument("--ops", required=True)
    a.set_defaults(func=cmd_apply)
    rp = sub.add_parser("replan", help="Capacity-balanced re-spread of all planned md")
    rp.add_argument("--file", required=True)
    rp.add_argument("--capacity", type=float, default=5.0,
                    help="man-days per week budget (default 5)")
    rp.add_argument("--start-week", type=int, default=1,
                    help="1-based week to start filling from (default 1)")
    rp.set_defaults(func=cmd_replan)
    rt = sub.add_parser("replan-team",
                        help="Per-assignee capacity scheduling from a spec JSON")
    rt.add_argument("--file", required=True)
    rt.add_argument("--spec", required=True, help="JSON: weekly_cap_by_person, assignee_by_id, ...")
    rt.set_defaults(func=cmd_replan_team)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
