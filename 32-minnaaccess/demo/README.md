# MinnaAccess live demo

An agent walks two local mock e-government procedures keyboard-only, the way a blind screen-reader user does, finds the steps where such a user gets stuck, proposes a fix, waits for a human to approve it, restarts from step 1 and verifies the fix with deterministic checks.

| Key | Procedure | Planted barriers (original mock) |
|---|---|---|
| `vn` | Cấp Phiếu lý lịch tư pháp, 4 steps (proposal Appendix A) | unnamed “Họ và tên” (SC 3.3.2), Tab trap on “Số điện thoại” (2.1.1), mouse-only “Tiếp tục” (2.1.1), image CAPTCHA (1.1.1), plus the abbreviated label “Nơi ĐKTT” |
| `jp` | 住民票の写し交付申請, 3 steps, fictional みどり市 (clearly marked MOCK) | 本籍地 field whose accessible name is the code `fld_hnsk_01` (2.4.6), focus trap on 郵便番号 (2.1.1) |

All pages are local mock pages with fake data. The agent's browser can only reach `127.0.0.1` (every other request is aborted), it never presses Nộp hồ sơ / 申請する / login, and every CAPTCHA goes to a human. No real .gov.vn or Japanese government site is touched.

## Start (one command)

```bash
cd "32-minnaaccess/demo"
python start_demo.py            # checks prerequisites, starts one server on 127.0.0.1:8765, opens the browser
```

Options: `--live` (open the Live run tab first), `--kiosk` (full-screen Chromium), `--scene jp-listen`, `--auto 6` (replay autoplay), `--port 8770`, `--no-browser`, `--check` (only check prerequisites). `python present.py` is the same command.

Requirements: Python 3.10+, `pip install playwright`, `python -m playwright install chromium`. Optional: the `claude` CLI logged in (only for live LLM calls). Fonts are bundled in `fonts/fonts.css` and nothing is loaded from a CDN, so the page works offline.

If port 8765 is taken by another MinnaAccess server, `start_demo.py` says so and opens it; if another program holds it, a free port is used and printed.

## The page

The interface defaults to Vietnamese for a new browser session. EN / JA / VI switches the dashboard language; an explicit `?lang=` or a saved preference takes priority. The mock procedure retains its own language. Historical replay screenshots retain the original recorded content.

The default presentation hides the event log and secondary timeline. **Chi tiết / Details** restores them without restarting the run, and the choice is remembered. Patch explanations and approval controls remain visible; **Code change** expands the patch. Barrier controls appear when **Try it yourself** is selected.

Request parsing rejects malformed JSON, non-object bodies and invalid body lengths. Approval clicks carry the run and proposal sequence; stale or duplicate decisions cannot replace an accepted decision. Run folders include a random suffix to avoid same-second collisions.

Two tabs in the top-right corner (key **L** toggles):

**Recorded run** (stage backup, arrow keys). The approved recorded run from `out/`. Right / Left or PageDown / PageUp (clicker) step scenes, Space autoplay, `1` Vietnam, `2` Japan, `3` vs axe-core, `4` Engine, Home / End. Every scene has its own URL (`#vn-blocked-hoten`, `#jp-read-honseki`, `#jp-audit`, `#engine`…). Opens from disk too (`dashboard.html`), without the Live tab.

**Live run** (`dashboard.html#live`). Press **Run agent now**: the server starts Chromium, walks the chosen procedure and streams every step to the page:

- left: the mock portal page the agent is on (live iframe, view only), the focused element outlined (blue = focus, purple = LLM typed it, red = barrier, green = verified, amber = hand-off), the screen-reader caption below;
- right: the agent log, LLM cards (model, cached or live, latency), the deterministic checks, the patch with a plain-language explanation in English and Vietnamese / Japanese, and **Approve / Reject** buttons (keys **A** / **R**). Nothing is written to the portal before Approve; Reject ends the run and leaves the barrier to a human; **Esc** stops the run;
- the result card: attempts, fixed and verified, left to a human, form submitted = no, and axe-core 4.10.2 on the same starting pages for comparison.

Settings: procedure, **Start from** (Original mock with the planted barriers, or Try it yourself), **LLM answers** (Cached replies, offline, default; or Live Claude calls, 10–50 s per call, disabled if the CLI is missing), Speed (Stage 1× / Fast 3×). The header always says which LLM source is in use. If a live call fails or times out (90 s), the agent uses the cached answer, then the rule engine, and says so in the log.

**Try it yourself**: choose a barrier (No label 3.3.2, Code name 2.4.6, Tab trap 2.1.1, Mouse only 2.1.1, CAPTCHA 1.1.1) and where to put it (3 places per barrier per procedure). The server plants it in a clean copy of the form; the left pane shows it with a dashed outline. The agent starts at step 1 without being told where it is. Every listed combination has its LLM answers cached, so it works offline.

**Reset portal** stops any run and restores the original mock pages.

Live runs write only to `portal/sandbox/` (working copy) and `runs/live/<time>/` (run.json, agent log, starting pages). Live LLM answers go to `runs/llm_cache/`. The recorded replay (`out/`, `out_rule/`, `cache/`) is never modified by the web page.

## Three-minute stage script

| Time | On screen | Say |
|---|---|---|
| 0:00–0:20 | Recorded run, scene 1 (`vn-listen`) | Blind users move by Tab and listen. One unnamed field or Tab trap and they cannot submit. Only 2.9% of surveyed people with disabilities used local e-service portals successfully (UN survey 2022, proposal ref. [2]). |
| 0:20–1:30 | Press **L** → Live run, Vietnam, Original mock, Cached replies, **Run agent now** | It hears “ô nhập”: a field with no name. Blocked, WCAG 3.3.2. The LLM wrote a patch and explained it in Vietnamese; deterministic checks pre-tested it. **A** to approve. It restarts from step 1, verifies, then finds the Tab trap on step 2 (invisible on the first pass), then the mouse-only button. **A**, **A**. At step 4 the CAPTCHA goes to a human. Result card: 3 fixed, 1 to a human, submitted: no; axe-core found 1 of the 4. |
| 1:30–2:15 | **⚙ Change setup** → Try it yourself → ask a judge to pick a barrier and a place → **Run agent now** | This is not a recording: you planted the barrier, the agent does not know where. It finds it, proposes a fix, you approve (or **R** to reject and show that nothing changes). |
| 2:15–2:45 | **L** → recorded run, key **3** (vs axe-core), then `jp-audit` | Same pages: MinnaAccess 4/4, axe-core 1/4. Team simulation: 48/50 vs 23/50. The JIS X 8341-3 試験結果 table comes from the same run; it is not a conformance claim. |
| 2:45–3:00 | Key **4** (Engine) | LLM reads labels and writes patches; rules forbid submit and send CAPTCHAs to people; a human approves every patch; code, not the LLM, decides pass or fail. |

Backup: if anything fails live, stay on the Recorded run tab and use the arrow keys; it needs no network and no LLM. `python record_video.py` makes a video backup.

## Other commands

```bash
python tests/e2e_test.py                  # end-to-end test: replay at 4 viewports, live approve + reject, try-it, reset, zero console errors (about 4.5 min)
python tests/e2e_test.py --shots          # same, and writes screenshots to shots/
python tests/e2e_test.py --quick          # replay at 1536x864 only + all live tests (about 2 min)
python shoot.py                           # 1920x1080 PNG of every recorded scene into shots/scenes/ + layout check
python run_demo.py --replay --auto-approve --headless   # re-record out/ from the cache (offline, about 30 s)
python run_demo.py --engine rule --auto-approve --headless   # rule-only baseline into out_rule/
python run_demo.py --out somewhere/       # record into another folder instead of out/
python prewarm_cache.py                   # fill cache/ for every Try-it-yourself scenario (cache first, claude CLI when missing)
python record_video.py                    # stage backup video into video/
```

## Files

| Path | What |
|---|---|
| `start_demo.py`, `present.py` | One-command start: prerequisite check, server, browser |
| `server.py` | Local server + live API (`/api/health`, `/api/live/options|state|prepare|start|decision|stop|reset`), live runner thread |
| `agent.py` | The keyboard-only walk, screen-reader lines, barrier detection, staging pre-check, approval gate, restart loop, axe comparison, audit rows |
| `engine.py` | `RuleBasedEngine` and `LLMEngine` (prompts, JSON schemas, patch validation, rule fallback) |
| `llm.py` | claude CLI client: schema output, validation retry, cache by prompt hash, timeout, cancel, cached fallback |
| `barriers.py` | Clean forms and the five injectable barriers |
| `run_demo.py` | Command-line recorded run into `out/` |
| `dashboard.html`, `ui/` | The page: `dashboard.css`, `common.js`, `replay.js`, `live.js`, `main.js` |
| `portal/original`, `portal/clean` | Mock portals with the planted barriers / without them; `portal/sandbox` is the live working copy |
| `cache/` | Shipped LLM answers (replay and Try it yourself) |
| `out/`, `out_rule/` | Recorded LLM run and rule-only baseline shown by the Recorded run tab |
| `runs/` | Live runs from the web page |
| `tests/e2e_test.py` | Playwright end-to-end test |
| `QA_REPORT.md` | Bugs found, fixes, test results |

## Limits

The portals are small mock pages written by the team. Screen-reader lines are built from Chromium's accessibility tree and phrased like NVDA, not recorded from NVDA. Live Claude calls through the CLI take 10–50 s each, so a live-LLM run of a full procedure takes minutes; the stage default is cached replies. LLM answers in a live run can differ from the cached ones (for example a date format); the deterministic checks do not depend on them. Numbers labelled “Team simulation (proposal §2.4)” come from `../sim/out/test/metrics.json`, not from this run.
