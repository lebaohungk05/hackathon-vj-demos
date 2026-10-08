# MinnaAccess demo: QA report

Date: 2026-10-06. Tester: automated Playwright passes (headless Chromium 1920×1080, 1536×864, 1536×730, 1366×768, 1366×657, 1280×720; http://127.0.0.1:8765 served by `present.py` and `file://`), a headed Chromium pass, axe-core 4.10.2 on the dashboard itself, and a code review of every file in `demo/`.

Method: every scene opened through `go()`, the keyboard (← → PageUp PageDown Home End Space 1–4 f), the procedure pills, the chapter buttons and the ticks; direct hashes (valid and invalid), runtime hash changes, back/forward, reload, live resize (1536×864 → 1280×600 → 1920×1080 → 1000×700); `?live=1` against the `present.py` server and against `file://`; `?auto=1`; offline (every non-127.0.0.1 request aborted). Console errors/warnings, page errors, failed requests and HTTP ≥ 400 were recorded; a layout probe checked page scroll, elements outside the viewport, clipped containers, ellipsised text, line-clamped headings, wrapped pills/chips, broken frame images, empty feeds and blank panels.

## Part 1: bugs found (before fixing)

| # | Severity | Bug | Repro | Root cause |
|---|---|---|---|---|
| 1 | Critical | Two servers listen on port 8765 at once; requests are split between them at random (approve clicks lost, `/api/state` 404, frames 404). | Start `python present.py`, then `python run_demo.py --approve dashboard`. Both start "successfully"; `netstat` shows two listeners. | `ThreadingHTTPServer.allow_reuse_address = True`; on Windows `SO_REUSEADDR` lets a second socket bind a port that is already listening. Neither script checks whether the port is taken. |
| 2 | High | `dashboard.html?live=1` against the `present.py` server: `GET /api/state` 404 every second, console error each time, nothing tells the presenter why the run does not appear. | Open `http://127.0.0.1:8765/dashboard.html?live=1` while `present.py` serves. | `present.py` is a static server without the API; the page polls blindly and swallows the error. |
| 3 | High | `?live=1` from disk: `Fetch API cannot load file:///D:/api/state` console error every second. | Open `dashboard.html?live=1` with `file://`. | No check for `location.protocol` before polling. |
| 4 | High | Fonts come from Google Fonts. Offline (stage Wi-Fi) the request fails with `net::ERR_FAILED` in the console and the page falls back to Segoe UI, which changes line widths. | Abort every non-local request, load the dashboard. | `<link>` to fonts.googleapis.com. |
| 5 | High | The dashboard shows broken frames while a run is in progress. | Leave the dashboard open, run `python run_demo.py --replay --auto-approve` or `record_video.py`. | Recorded replay data and new runs share one folder: every run wipes `out/` (and `portal/live/`) at start. |
| 6 | High | No way to run the agent from the web page. The only interactive flow needed a terminal command with a flag plus a special URL, and the approval buttons lived only in that mode. On stage the page is a slideshow of recorded screenshots. | — | Agent loop lives in `run_demo.main()` with module globals (`OUT`, `LIVE`, `BASE`, fixed port), so a server cannot reuse it. |
| 7 | Medium | Resizing the window breaks the right column: at 1280×600 the panel content is clipped at the bottom (`panel 293>249`); after growing back the feed stays short. | Open any feed scene, resize the window. | `trimFeed()` only runs on scene change; no resize handler. |
| 8 | Medium | Feed lines and check details are cut with "…" on every viewport: barrier evidence ("Screen reader reads the field only as it…"), "Verified by keyboard replay: step 1 now…", "Full Tab cycle (3 stops) never reached…", pre-check detail ("accessible name “Họ và tên *” c…"), LLM meaning at 1536×730. 12 of 32 scenes. | Open `#vn-blocked-hoten`, `#vn-fix-hoten`, `#jp-verified-honseki`. | Single-line `text-overflow: ellipsis` on `.fi .t`, `.fi .s`, `.checks .d`. |
| 9 | Low | The screen-reader feed disappears completely on verified/read scenes (`vn-verified-*`, `vn-read-diachi`, `jp-read-honseki`), leaving an empty gap above the card. | Open `#vn-verified-hoten`. | The card is `flex-grow` and the trimming loop removes every feed item instead of keeping at least the last lines. |
| 10 | Low | Back/forward and unknown hashes desynchronise URL and scene: after `#does-not-exist` the URL keeps the bad hash, Back shows `#does-not-exist` while the scene stays on `vn-audit`. | Open `#does-not-exist`, then set `#vn-audit`, press Back. | `replaceState` on render plus a `hashchange` handler that ignores unknown keys without restoring the hash. |
| 11 | Low | Key `f` ("follow the live run" in the README) just jumps to the last scene in presenter mode. | Press `f`. | Left over from the old `?live=1` mode. |
| 12 | Medium | The dashboard of an accessibility product fails axe-core: `color-contrast` (serious) on 5–10 nodes per scene (`--dim` #6f6896 text on navy, table headers, caption meta, stamps), `region` (moderate) on the stage rail. | Run axe-core 4.10.2 on any scene. | Low-contrast token `--dim`; rail outside any landmark. |
| 13 | Low | The fake address bar always says `127.0.0.1:8765`, also when served on another port or opened from disk. | `python shoot.py` (random port) screenshots. | Hard-coded host. |
| 14 | Low | Audit subtitle says "An NVDA user and an officer confirm each row before signing". The proposal says the officer re-checks before the record is drawn up; nobody "signs" (and the team was asked to drop "ký"). | Open `#vn-audit`. | Copy. |
| 15 | Medium | `present.py` has no prerequisite check (Playwright, Chromium, axe-core, Claude CLI) and gives a traceback if the port is held by another program. | Run with Chromium missing or port 8765 taken by a non-Python app. | — |
| 16 | High | A missing or slow `claude` CLI freezes the run for up to 6 minutes with no feedback: 2 tries × 180 s timeout, and the retry also happens for timeouts and "CLI not found". No cancel. | `run_demo.py --live` with `claude` not on PATH or offline. | `ClaudeCLI.ask` retries every exception; `subprocess.run` cannot be cancelled. |
| 17 | Medium | A fresh LLM call overwrites the cache file used by the stage-safe replay, so the next `--replay` can show a different answer than the recorded `out/` run. | `run_demo.py --live`, then `--replay`. | One cache folder for both shipped replay answers and new live answers. |
| 18 | Medium | `--approve dashboard` waits forever if the tab is closed; only Ctrl+C ends it. | Start with `--approve dashboard`, close the tab. | `threading.Event().wait()` without cancel. |
| 19 | Low | Approve / Reject call `fetch` without error handling: if the server is gone, an unhandled promise rejection appears and the buttons stay "waiting". | Stop the server while a patch is pending, click Approve. | Inline `onclick="decide(true)"` with no `try`. |
| 20 | Low | After clicking a progress tick, the tick keeps focus; a later Enter (some clickers send it) jumps back to that tick. Ticks are 6 px tall at 1280×720. | Click tick 5, press → →, press Enter. | Focus not released after mouse click; tick height `.55rem`. |
| 21 | Low | Engine panel: "actions and stops by hard-coded guards" counts with a precedence bug (`a && b \|\| c`), so any event whose engine starts with "deterministic" is counted whatever its kind. | Read `enginePanel()`. | Missing parentheses. |
| 22 | Low | Verified card prints the patch engine through `pretty()`: a rule-fallback patch shows as "Rule fallback.(replay.miss…". | Any run where an LLM patch fell back to rules. | `pretty()` is meant for model ids only. |
| 23 | Low | `.tl` is both the traffic-light dots in the fake browser bar and the timeline card; the shared `.tl{flex:none}` rule couples them. | Read the CSS. | Name collision. |

Console/network summary on the served dashboard with internet: 0 errors in replay mode at all six viewports. Errors appear in `?live=1` (bugs 2–3) and offline (bug 4).

## Part 2: fixes (2026-10-07)

| # | Fix (root cause) |
|---|---|
| 1 | New `netutil.ExclusiveServer`: `allow_reuse_address = False` plus `SO_EXCLUSIVEADDRUSE` on Windows, so a second bind fails instead of silently sharing the port. `start_demo.py` detects a running MinnaAccess server via `/api/health` and reuses it, or picks a free port; `run_demo.py` uses a free port when 8765 is busy. One server (`server.py`) now serves the page, the mock portal and the API. |
| 2–3 | The old `?live=1` polling is gone. The Live tab only calls the API when the page is served over http and the server answered `/api/live/options`; from `file://` or without a server it shows how to start the server, with zero requests. |
| 4 | Inter and JetBrains Mono (latin, latin-ext, vietnamese subsets) inlined as data URIs in `fonts/fonts.css`; Japanese falls back to Yu Gothic UI / Meiryo. No CDN request remains (checked: 0 external requests). |
| 5 | Live runs write only to `portal/sandbox/`, `runs/live/<id>/` and `runs/llm_cache/`; `run_demo.py` gained `--out`. The e2e test hashes `out/` before and after and fails if it changes. |
| 6 | Agent loop extracted from `run_demo.py` into `agent.py` (parameterised by a `Workspace`, event listener, cancel flag, pace). `server.py` runs it in a thread per run with `/api/live/start|state|decision|stop|reset|prepare|options`; the page streams events by polling, plays them at stage speed, shows the live iframe with the focused element outlined, captions, LLM cards, checks and real Approve / Reject. Refactor verified: `run_demo.py --replay` produces the same 105 + 73 events as the recorded run. |
| 7 | Debounced `resize` handler re-renders the scene (replay) or rescales the iframe and re-lays out (live). |
| 8 | Feed lines, LLM meanings and check details wrap to 2 lines instead of one-line ellipsis. |
| 9 | Empty feed is hidden (`.feed:empty`) instead of leaving a gap. |
| 10 | Unknown hashes are replaced with the current scene; `#live` is a real route; `hashchange` switches mode or scene. |
| 11 | `f` removed; `L` toggles Recorded run / Live run; `A` / `R` approve / reject; `Esc` stops a live run. |
| 12 | `--dim` raised to #918bb8 (≥4.5:1 on every panel colour), solid amber backgrounds use #b45309, teal stamps use dark text, rail is a `<nav>` landmark, ticks have accessible names. axe-core 4.10.2 on 7 scenes incl. Live: 0 violations. |
| 13 | Address bar uses `location.host`. |
| 14 | Audit subtitle: “An NVDA user re-listens to each row and an officer re-checks it before the record is drawn up.” Engine panel: “re-check every record”. |
| 15 | `start_demo.py` checks Python, Playwright, Chromium, Claude CLI, axe-core, recorded replay + frames, cache, fonts, and prints ok / warn / FAIL lines; the page footer shows the same status. |
| 16 | `ClaudeCLI`: infrastructure errors (CLI missing, timeout, non-zero exit) are not retried; Popen with timeout (90 s in the web UI) and `cancel()` kills the process on Stop/Reset; on failure the cached answer is used, then the rule engine; `llm_start` / `llm_end` events show a live “Claude Haiku is reading the field… 12 s” card. If the CLI is missing, the Live Claude option is disabled and a forced live run falls back with a visible notice (tested). |
| 17 | Fresh answers are written only when the key is new; web live runs write to `runs/llm_cache/`, never to `cache/`. |
| 18 | Approval wait polls a cancel flag; Stop / Reset end it. `--approve dashboard` replaced by the Live tab. |
| 19 | All live buttons go through `api()` with try/catch and a toast; lost connection shows one toast, restored connection another. |
| 20 | Ticks are 1.6 rem tall hit areas and lose focus after a mouse click (Enter no longer jumps back). |
| 21 | Parenthesised the guard-count condition. |
| 22 | `engineName()` prints “Sonnet 5.5” or “the rule engine (LLM fallback)”. |
| 23 | Traffic-light dots renamed `.dots`, timeline card `.tlc`. |

Bugs found while building and testing the new live mode, also fixed: concurrent `prepare` requests raced on the sandbox folder (server lock, files overwritten in place instead of delete + copy, client serialises prepare calls and waits before Start); iframe reloads aborted mid-load (`net::ERR_ABORTED`) and briefly hit 404 on `portal.css` (iframe now loads one URL at a time); a reload of a finished run restored the old procedure instead of the setup; rejected runs showed a green frame and the “Verified” stage; the final “(focus left the page)” line replaced the last useful caption; handler exceptions closed the connection without a response (now JSON 500, client disconnects ignored).

New: `start_demo.py`, `server.py`, `agent.py`, `barriers.py`, `netutil.py`, `prewarm_cache.py`, `portal/clean/`, `ui/`, `fonts/`, `tests/e2e_test.py`. `cache/` now holds 66 answers: the recorded run plus every Try-it-yourself combination (5 barriers × 3 places × 2 procedures, 33 scenarios, each run end-to-end once: every planted barrier found, every non-CAPTCHA barrier fixed and verified, every CAPTCHA handed off).

## Part 3: test results

`python tests/e2e_test.py --shots` (headless Chromium, in-process server):

- Recorded run at 1920×1080, 1536×864, 1366×768, 1280×720: all 32 scenes stepped with → and checked for page scroll, elements outside the viewport, clipped panel/cards, wrapped pills/chips/buttons, cut header chips, broken frames, blank panels; keys Home, 1–4, PageDown/Up, Space; procedure pill; tick + Enter; direct hash, unknown hash, reload; resize to 1100×620 and back.
- `file://`: replay layout clean, Live tab explains how to start the server.
- Live run at 1536×864 and 1280×720: VN original approved three times → 3 fixed and verified, CAPTCHA to a human, submitted = no, axe-core 1 of 4 on the same pages; JP original rejected → result “rejected”, portal file unchanged. Live iframe present with the focused element outlined; layout checked while running, at the decision and on the result.
- Try it yourself (1366×768): Tab trap planted on VN Email → preview outline, file contains the trap, agent finds #email keyboard_trap, fixed and verified, axe-core misses it; CAPTCHA planted → handed to a human; Reset → sandbox byte-identical to the original pages and setup back to Original mock. Live setup and Try-it setup laid out at all four viewports.
- `out/` digest unchanged; 0 console errors or warnings, 0 failed requests, 0 HTTP ≥ 400.

Result: **267/267 checks passed** (260 s). `--quick`: 123/123 (104 s). Separately: a real live-Claude run (JP, CAPTCHA planted on step 2: 4 Haiku calls of 13–47 s, then hand-off) and a run with the CLI hidden (warning, cached answers, run completes) both behaved as designed. `python shoot.py`: all 32 scenes clean. Screenshots: `shots/replay_*.png`, `shots/live_*`, `shots/try_*`, `shots/scenes/`.

Remaining limits: live Claude calls take 10–50 s each, so a full live-LLM run takes minutes (cached replies are the stage default); Try-it-yourself offers the 3 cached places per barrier rather than every field; the agent's browser runs headless on the server, the page shows the same page in a view-only iframe rather than the agent's own window.
