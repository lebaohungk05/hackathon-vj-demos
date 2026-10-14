---
name: feature-workflow
description: Orchestrates the full planner → coder → reviewer ↔ coder → tester ↔ coder+reviewer loop for a feature or bug fix. Invoke when the user asks to "implement", "build", "fix", or "do" any non-trivial change. Main agent runs this — subagents do not call each other.
---

# Feature workflow

You are the **main orchestrator**. Subagents do not invoke each other — you do. Run this loop end-to-end and report progress between phases. Do not write code yourself; delegate to the right subagent.

## State you must track

- `iteration_review` — coder ↔ reviewer loop count (max **3**)
- `iteration_test`   — coder/reviewer ↔ tester loop count (max **2**)
- `last_findings`    — most recent reviewer or tester output to pass to coder

If a cap is hit, **stop and ask the user** — do not silently keep looping.

## Phase 1 — Plan

1. Dispatch the `planner` subagent with the user's request verbatim plus any relevant context you've gathered.
2. Read the plan. If it contains open questions → relay them to the user and **stop**. Wait for answers.
3. If the plan looks risky or large (touches infra, migrations, auth, multi-service) → show the plan to the user and ask `Proceed? (y/n)` before continuing.
4. Otherwise proceed to Phase 1.5.

## Phase 1.5 — Branch

Before any code, on the **repo currently open in the IDE** (the working repo), create a feature branch from the base branch named in `CLAUDE.md` (default `develop`):
`git fetch && git switch <base> && git pull && git switch -c feat/<short-desc>`

There is no ADO ticket in this workflow, so there is no ticket state to change. If the working tree has uncommitted changes, ask the user before branching.

## Phase 2 — Code (review loop)

```
iteration_review = 0
loop:
  dispatch `coder` with: <the plan>  OR  <reviewer findings + plan>
  dispatch `reviewer` on the resulting diff
  iteration_review += 1

  if reviewer VERDICT == APPROVE:               break
  if reviewer VERDICT == NEEDS_DISCUSSION:      stop, ask user
  if iteration_review >= 3:                     stop, ask user
  # else: VERDICT == REQUEST_CHANGES → loop with findings
```

Pass the reviewer's **blocking issues** verbatim to the next coder run. Do not paraphrase — the coder needs exact file:line references.

## Phase 3 — Test (test loop)

```
iteration_test = 0
loop:
  dispatch `tester` to add missing coverage + run the suite
  iteration_test += 1

  if tester reports ALL_GREEN:                  break
  if iteration_test >= 2:                       stop, ask user
  if tester reports PRODUCTION_BUG_FOUND:
      dispatch `coder` with the failing test + tester's diagnosis
      dispatch `reviewer` on the fix
      # then loop back to tester
```

The tester is **not allowed** to modify production code to make tests pass. If a test fails because production code is wrong, the tester reports it and you hand off to the coder.

## Phase 4 — Wrap-up

- Run a final `secrets-scan` skill against the staged diff.
- Summarize to the user:
  - Files changed (count + paths)
  - Tests added (count)
  - Review iterations used
  - Anything skipped or deferred
- **Finish:** run the pre-PR local checks from `CLAUDE.md`, commit on the feature branch, push, and open a PR on the working repo targeting the base branch (GitHub: `gh pr create`; Azure Repos: `az repos pr create`). `git push` / PR creation prompt via the permission `ask` gate. For a trivial or exploratory change where a PR isn't wanted, summarize and ask before opening one.

## Choosing not to use this workflow

Skip the full loop for:
- Single-line fixes, typos, comment changes — just edit.
- Read-only questions about the codebase — just answer.
- Refactors with no behavior change and existing test coverage — coder + reviewer is enough, skip planner and tester.

Use judgment. When in doubt, ask the user whether they want the full workflow.
