---
name: update-evm-pv
description: Update the "PV (Kế hoạch)" (Planned Value) tab of an existing EVM report workbook — edit weekly planned man-days, add/remove work-item rows, rename items, reorder rows, and re-spread all planned man-days capacity-balanced across weeks (like generate-evm-report, but in place). Use whenever the user wants to edit the PLAN inside an already-created EVM file (not regenerate it from scratch) and says things like "cập nhật PV", "sửa kế hoạch EVM", "update PV", "sửa man-day tuần", "thêm hạng mục vào EVM", "xóa hạng mục EVM", "đổi tên hạng mục EVM", "đổi thứ tự hạng mục EVM", "sắp xếp lại PV", "cân lại tuần", "rải lại theo capacity", "replan EVM", "edit EVM plan", "add/remove row in EVM". Runs update_evm_pv.py (xlwings) against a workbook path the user provides each time. NOT for building a new report from ADO — that is generate-evm-report.
---

# Update EVM — PV (Kế hoạch) tab

Edit the **PV (Kế hoạch)** tab of an *existing* EVM workbook in place. This skill does **not** regenerate the report (use `generate-evm-report` for that) — it surgically edits the plan and lets Excel auto-recalculate every dependent sheet.

The work is done by **`update_evm_pv.py`** (in this skill folder, uses **xlwings** → real Excel, so conditional formatting on SPI/CPI is preserved and formula references / SUM ranges auto-adjust on insert/delete).

## How the workbook is wired (read this before editing)

All formula sheets (`EV (Tiến độ lũy kế)`, `EV (Hoàn thành thực tế)`, `SPI`, `CPI`) reference `PV (Kế hoạch)` / `AC` by the **same absolute row index**. Consequences the script already handles — but you must understand them:

| Operation | Sheets touched | Notes |
|---|---|---|
| **set** man-day | PV only (`D:AA`) | EV/SPI auto-recalc |
| **rename** | PV col C **+ AC col C** | AC's title is hardcoded (not a mirror formula), so it is synced too |
| **add** row | **all 6 sheets**, same index | Excel shifts formulas + SUM ranges; new row copies formulas from the row above |
| **remove** row | **all 6 sheets**, same index | SUM ranges auto-shrink |
| **move** (reorder) | PV/EV-cum/AC manual data | payloads permuted; formula cells stay & recompute |

- **Rows 3 → boundary−1** are data rows. The gray boundary row (`"Không chèn thêm dòng vào dưới dòng này"`) is detected dynamically — never hardcode row 32. Capacity = `boundary − 3` rows; `add` inserts above the boundary, growing it.
- **Column layout is auto-detected** (`detect_layout`), so the script handles two variants:
  - **base template**: `B=No | C=Hạng mục | D…=weeks | Tổng`
  - **assignee variant**: `B=No | C=Hạng mục | D=Người phụ trách | E…=weeks | Tổng`
  The **first week column** is found as the first `"Tuần N"` header; any column between title (C) and that is the **assignee column** (`ASSIGNEE_COL`, position-based — no fragile Vietnamese string matching). The `Tổng` column is found by its header. So never assume weeks start at D.
- Weeks are addressed by **1-based number** (`week 1` = first week column, whichever it is).
- Work items are matched by the **`#<id>`** prefix in col C (e.g. `#5803 …`), or by `title_contains`, or by absolute `row`.

## Step 1 — Get the workbook (local, or SharePoint/OneDrive via Graph)

The script edits a **local** `.xlsx`. Two ways to get one:

- **Local / OneDrive-synced path** — ask the user, e.g. `C:\Users\…\OneDrive - DataImpact\…\EVM_report.xlsx`. Edit in place.
- **SharePoint / OneDrive cloud file** (a share link like `…sharepoint.com/:x:/s/…` or a `/sites/…` path) — not synced locally and WebFetch 403s. If Azure CLI is logged in as an account **in the file's tenant** (`az account show`), use **Microsoft Graph** to round-trip:
  ```bash
  TOKEN=$(az account get-access-token --resource https://graph.microsoft.com --query accessToken -o tsv)

  # (a) Resolve ANY share link straight to the file — the simplest path when the user pastes a link:
  ENC=$(python -c "import base64,sys;print('u!'+base64.b64encode(sys.argv[1].encode()).decode().rstrip('=').replace('+','-').replace('/','_'))" "<SHARE_URL>")
  # GET /shares/$ENC/driveItem   → returns .id (itemId) and .parentReference.driveId

  # (b) Or navigate by site/path if you only have a folder path:
  #   GET /sites/{host}:/sites/{SiteName}          → siteId
  #   GET /sites/{siteId}/drive/root:/{path}:/children

  # download:   GET  /drives/{driveId}/items/{itemId}/content  -o local.xlsx   (or /sites/{siteId}/drive/items/{itemId}/content)
  # …edit local.xlsx with this script…
  # upload back: PUT /drives/{driveId}/items/{itemId}/content  --data-binary @local.xlsx
  ```
  Token needs Sites/Files access (the Azure CLI first-party app usually has it — a throwaway upload+delete confirms write). **This only works if the signed-in az account can access the file**; a different tenant or missing `az login` will fail.

**⚠️ The file must be CLOSED** (Excel desktop AND Excel Online / browser). An open file causes xlwings to hang on a write lock locally, or Graph upload to fail with **`resourceLocked`** / **423**. Ask the user to close it, then retry.

## Step 2 — Dump current state (always do this first)

```bash
python skills/update-evm-pv/update_evm_pv.py show --file "<PATH>"
```

Returns JSON: `boundary_row`, `total_col`, `capacity_rows`, `used_rows`, the `weeks` list (`n` + `date`), and every populated `item` (`row`, `no`, `id`, `title`, non-zero `weeks`). **Use this to map the user's intent to exact row numbers, week numbers, and ids** — never guess them.

## Step 3 — Decide the data source

- **Nhập tay (manual):** the user gives concrete values ("hạng mục #5803, tuần 3 = 2 md", "đổi tên #5806 thành …", "thêm hạng mục X", "đưa #5773 lên đầu"). Build ops directly.
- **Kéo từ ADO:** fetch the referenced work items via the **azure-devops MCP** (main agent may fetch directly for this skill, same as `generate-evm-report`). Then:
  - **planned man-days** = `OriginalEstimate hours / 8`, rounded to 2 dp. To spread a total across weeks, ask the PM for a **start week** + **capacity/week** and fill sequentially (same spreading rule as `generate-evm-report`).
  - match each ADO item to a PV row by `#<id>`: existing → `set`/`rename`; new → `add`.
  - If the user mixes both, ask which values come from ADO and which they'll type.

Confirm the planned change set with the user before writing (especially add/remove — they restructure all sheets).

## Step 4 — Write an ops file and apply

Build a JSON **list** of operations (processed in order; matches re-resolved each step) and run:

```bash
python skills/update-evm-pv/update_evm_pv.py apply --file "<PATH>" --ops "<scratchpad>/ops.json"
```

### Operation schema

```jsonc
// match := {"id": 5803} | {"title_contains": "config"} | {"row": 5}

// set one or many week cells (value null/"" clears the cell)
{"op": "set", "match": {"id": 5804}, "week": 3, "value": 2.5}
{"op": "set", "match": {"id": 5803}, "values": {"3": 2, "4": 3}}

// rename (syncs PV col C and AC col C)
{"op": "rename", "match": {"id": 5806}, "title": "#5806 New title"}

// add a new row. Position: "after"/"before": <match> | "index": <abs row> | omit → append.
//   Prefers the next blank templated row (fast, no insert); inserts on all sheets only when full.
//   Optional "assignee" is written to the Người phụ trách column when that layout is present.
{"op": "add", "after": {"id": 5772}, "title": "#5999 New item", "values": {"1": 2, "3": 1}}
{"op": "add", "title": "#5769 …", "assignee": "Tran Quang Bao", "values": {"1": 0.5}}

// remove a row (deletes on all sheets)
{"op": "remove", "match": {"id": 5773}}

// reorder. "index" = absolute target row (canonical; preferred). Also "after"/"before": <match>
{"op": "move", "match": {"id": 5773}, "index": 3}
```

`apply` prints `{"applied": N, "log": [...]}`. Re-run `show` to confirm the result if useful.

## Step 4b — Capacity-balanced re-spread (`replan`)

When the user wants the week distribution **balanced like `generate-evm-report`** (e.g. after adding items, the early weeks are overloaded), use `replan` instead of hand-computing week values:

```bash
python skills/update-evm-pv/update_evm_pv.py replan --file "<PATH>" --capacity 5 --start-week 1
```

- Takes each item's **current row total** (sum of D:AA) as its man-days — per-item totals are preserved, only the week-by-week spread is rebuilt.
- Fills sequentially in **row order**, current week up to `--capacity` md, then overflow to the next week (an item may split across a week boundary), rounding to 2 dp. Items with 0 md stay blank.
- This is exactly `generate-evm-report`'s spreading rule, applied **in place** — the file, rows, formatting and other sheets are untouched.
- `--start-week N` begins filling at week N (default 1). Use a later week to leave past weeks alone.
- Prints `{"replanned_items": N, ...}`.

Note: `replan` re-distributes **all** items by row order, so it can change which week an existing item sits in. If the user only wants new items packed into leftover capacity without disturbing existing weeks, build `set` ops instead.

### Per-assignee scheduling (`replan-team`)

`replan` uses one flat team capacity. When each person has a different daily rate and tasks should run **in parallel per person**, use `replan-team` — each assignee gets an independent weekly capacity and timeline:

```bash
python skills/update-evm-pv/update_evm_pv.py replan-team --file "<PATH>" --spec team_spec.json
```

`team_spec.json`:
```json
{
  "start_week": 1,
  "weekly_cap_by_person": {"Hoang Tung Anh": 5.0, "Do Hai Hung": 2.5},
  "assignee_by_id": {"5803": "Do Hai Hung", "5770": "Hoang Tung Anh"},
  "unscheduled_ids": [5815]
}
```

**Before building the spec, collect the resource per person — do NOT guess rates:**
1. Get the **distinct assignees** for the items in scope — read them from the sheet's **Người phụ trách column** (assignee-variant layout, via `show`/openpyxl) or from ADO `System.AssignedTo`.
2. **Ask the PM the `md_per_day` (resource) for EACH distinct person**, and the **working days/week** (default 5). List the names back so none is missed. Then `weekly_cap = md_per_day × days_per_week` (e.g. 1.0 md/day × 5 = 5.0/week).
3. Ask what to do with any **unassigned / unknown-rate** items → put their ids in `unscheduled_ids` (left blank) or get an owner+rate first.

- **weekly_cap_by_person**: one entry per person from step 2. A person present in the sheet but missing here → their items are skipped (returned in `skipped_unscheduled`).
- **assignee_by_id**: the assignee per item (same source as step 1). Use the plain display name as the key in both maps.
- Each person's tasks are packed **in PV row order** on their own timeline; a task may split across a week boundary; per-item totals preserved.
- Items in `unscheduled_ids`, or whose assignee is missing from `weekly_cap_by_person`, are **left blank** and returned in `skipped_unscheduled` — surface these to the PM (e.g. an unassigned task).
- Peak weekly team load = sum of everyone's weekly caps (parallel work), so early weeks can far exceed any single person's capacity — that is expected, not an overload.

## Step 5 — Report to the user

- What changed (echo the `log`).
- Remind them: planned totals (`TỔNG CỘNG TỪNG TUẦN` / `LŨY KẾ`) and per-item `Tổng` recalculated automatically; SPI/CPI/EV update once they re-open the file.
- If `add`/`remove` was used, note that all sheets were kept structurally aligned.
- The EVM file is a per-project artifact (like `generate-evm-report`'s output) — do not commit it into the shared config base.

## Notes & guardrails

- **Test risky batches on a copy first** when unsure (`cp` the file to the scratchpad, apply, `show`, eyeball) — then run on the real file.
- `EV (Tiến độ lũy kế)` (% complete) and `AC` (actual cost) week cells are **PM-owned** — this skill does not fill them. `add` leaves them blank for the PM.
- AC col C/No. are kept in sync best-effort on add/rename; if the existing AC titles already drifted from PV (older files), surface that to the user rather than silently overwriting unrelated rows.
- The script needs **Excel installed** (xlwings). It opens the file invisibly, saves, then **force-terminates** Excel (`app.kill()`) — a graceful quit can hang for minutes on some Office builds even though the save itself finished in well under a second. The file is fully saved before the kill, so this is safe.
- A run can take a while (tens of seconds, occasionally minutes on a loaded machine) — that's Excel COM overhead, not a failure. Verify the result by reading the saved file with **openpyxl** (read-only, no Excel needed) rather than by watching the process.
- If you ever force-kill Excel repeatedly, the machine's COM can wedge and subsequent runs slow down; close stray `EXCEL.EXE` instances between runs.
