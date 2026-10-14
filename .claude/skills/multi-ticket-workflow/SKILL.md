---
name: multi-ticket-workflow
description: Orchestrates implementation of one OR many Azure DevOps tickets in a single user request. For each ticket ID the main agent runs the full pipeline ticket-reader → planner → coder → reviewer ↔ coder → tester ↔ coder+reviewer, strictly sequentially (no parallel tickets). Invoke when the user references one or more ADO work item IDs (e.g. "AB#1234", "implement tickets 1234, 1235, 1236", "xử lý ticket 1234 và 1235") and asks to implement/fix/do them. Stops the whole batch on the first ticket that BLOCKs.
---

# Multi-ticket workflow

You are the **main orchestrator**. The user has given you a list of Azure DevOps ticket IDs. Process them **one ticket at a time**, fully completing each ticket's pipeline before starting the next. Subagents do not call each other — you dispatch them.

This skill is a superset of `feature-workflow`. The per-ticket pipeline is the same loop, with `ticket-reader` prepended.

## Inputs

The user message contains one or more ticket references in any of these forms:

- Bare IDs: `1234`, `#1234`, `AB#1234`
- Full URLs: `https://dev.azure.com/<org>/<project>/_workitems/edit/1234`
- Comma / space / "and" separated lists, including Vietnamese (e.g. `xử lý ticket 1234, 1235 và 1236`)

Normalize to an ordered list `[id_1, id_2, ..., id_n]`, preserving the order the user wrote. If you cannot parse any ID, ask the user before doing anything.

## State you must track (across the whole batch)

- `queue` — remaining ticket IDs in order
- `current_id` — the ticket being processed right now
- `completed[]` — IDs finished with `ALL_GREEN`
- `failed` — `null`, or `{id, phase, reason}` when a ticket BLOCKs

Also track per-ticket (reset at the start of each ticket):

- `iteration_review` — coder ↔ reviewer loop count (max **3**)
- `iteration_test`   — coder/reviewer ↔ tester loop count (max **2**)
- `last_findings`    — most recent reviewer or tester output to pass to coder

## Top-level loop (sequential — never parallel)

```
for current_id in queue:
    report to user: "▶ Starting ticket <current_id> (k/n)"
    run per-ticket pipeline (Phases 1–5 below)

    if pipeline ended with batch-stop condition:
        record failed = {id: current_id, phase, reason}
        STOP the batch — do not start the next ticket
        report to user with the failure details + which IDs are still in queue
        break

    completed.append(current_id)
    report to user: "✓ Ticket <current_id> done"

after the loop:
    if failed is null:
        run Phase 6 — Batch wrap-up
    else:
        report queue remaining + failed ticket details and stop
```

**Never run two tickets concurrently.** Even when the tickets look independent, the project rule is one-at-a-time so reviewers and CI see one logical change per ticket. If the user explicitly asks for parallel processing, push back and explain the rule before doing it.

## Per-ticket pipeline

### Phase 1 — Read ticket

1. Dispatch the `ticket-reader` subagent with **only** `current_id` (not the whole queue). If you pass extra IDs they will land in the brief's `## Remaining IDs` and you must ignore them — your `queue` is the source of truth.
2. Read the brief.
3. If `STATUS: BLOCKED` → batch-stop with `phase="ticket-reader"` and the reason from the brief.
4. If the brief's `## Gaps found` lists severe gaps that prevent planning, still proceed to the planner — the planner will judge and may BLOCK. Do not pre-empt that decision.

### Phase 2 — Plan

1. Dispatch the `planner` subagent. Pass the ticket-reader brief as input plus the user's original verbatim request.
2. Read the plan.
3. If `STATUS: BLOCKED` → batch-stop with `phase="planner"` and the open questions.
4. If the plan touches infra, migrations, auth, multi-service, or otherwise looks risky → show it to the user and ask `Proceed with ticket <current_id>? (y/n)` before continuing. On `n`, batch-stop with reason `user declined plan`.
5. Otherwise proceed to Phase 2.5.

### Phase 2.5 — Start work (ADO state + branch)

Done by **you, the main agent** (not a subagent), after the plan is approved and before any code:

1. **Set ADO state → in-progress.** Update the ticket (in the project the brief reports under `ADO Project`) to the in-progress state (e.g. `Doing` / `Active`) via `mcp__azure-devops__wit_update_work_item`. If this project's process uses a different name, pick the closest in-progress state and tell the user which you used.
2. **Branch on the working repo.** Remember the working repo (open in the IDE) may differ from the ticket's ADO repo. From the base branch named in `CLAUDE.md` (default `develop`):
   `git fetch && git switch <base> && git pull && git switch -c feat/<current_id>-<short-desc>`
   If the working tree has uncommitted changes (e.g. left over from a previous ticket that wasn't finished), **stop and ask the user** before branching — do not discard work.

If either step fails (MCP write denied, base branch missing, dirty tree), batch-stop with `phase="start-work"` and the exact error.

### Phase 3 — Code (review loop)

```
iteration_review = 0
loop:
  dispatch `coder` with: <the plan>  OR  <reviewer findings + plan>
  if coder STATUS == BLOCKED:           batch-stop, phase="coder"
  dispatch `reviewer` on the resulting diff
  iteration_review += 1

  if reviewer VERDICT == APPROVE:               break
  if reviewer VERDICT == NEEDS_DISCUSSION:      batch-stop, phase="reviewer"
  if iteration_review >= 3:                     batch-stop, phase="reviewer", reason="review cap exceeded"
  # else: VERDICT == REQUEST_CHANGES → loop with findings
```

Pass the reviewer's **blocking issues** verbatim to the next coder run (do not paraphrase — coder needs exact `file:line` references).

### Phase 4 — Test (test loop)

```
iteration_test = 0
loop:
  dispatch `tester` to add missing coverage + run the suite
  iteration_test += 1

  if tester VERDICT == ALL_GREEN:           break
  if tester VERDICT == BLOCKED:             batch-stop, phase="tester"
  if iteration_test >= 2:                   batch-stop, phase="tester", reason="test cap exceeded"
  if tester VERDICT == PRODUCTION_BUG_FOUND:
      dispatch `coder` with the failing test + tester's diagnosis
      if coder STATUS == BLOCKED:            batch-stop, phase="coder"
      dispatch `reviewer` on the fix
      if reviewer VERDICT != APPROVE:        batch-stop, phase="reviewer"
      # then loop back to tester
```

### Phase 5 — Per-ticket wrap-up

1. Run the `secrets-scan` skill against the staged diff.
2. Report a compact per-ticket summary to the user:
   - Ticket ID + title
   - Files changed (count + paths)
   - Tests added (count)
   - Review / test iterations used
   - Anything deferred
3. **Finish the ticket** (you, the main agent — never a subagent):
   a. Run the pre-PR local checks from `CLAUDE.md` (Python: `ruff check && mypy && pytest -q`; TS: `pnpm lint && pnpm test && tsc --noEmit`). If they fail, treat as a `coder` loop-back (don't open a PR on red).
   b. Stage and commit on the feature branch; commit message references the ticket (`… (AB#<current_id>)`).
   c. Push the branch and open a PR on the **working repo**, targeting the base branch, with the ticket ID in the title + description (GitHub: `gh pr create`; Azure Repos: `az repos pr create`). `git push` / PR creation prompt via the permission `ask` gate — expected.
   d. **Set ADO state → in-review** (e.g. `Review` / `Code Review`) via `mcp__azure-devops__wit_update_work_item`.
   e. Report the PR URL + the new ticket state in the per-ticket summary.

   The next ticket re-branches from the base branch in Phase 2.5, so it starts clean off `<base>`, not on top of this ticket's branch.

## Phase 6 — Batch wrap-up (only when every ticket completed)

Report to the user:

- `Completed:` list of IDs with a 1-line summary each.
- `Total changes:` aggregate files changed, tests added.
- `Suggested next steps:` e.g. `Commit and open PR(s)?` — ask before doing it.

## Batch-stop reporting (when any ticket fails)

When you batch-stop, the message to the user MUST include:

```
Batch stopped at ticket <id> in phase <phase>.
Reason: <reason>
Completed tickets: [<list>]
Remaining (not started): [<list>]
<the last subagent's output verbatim>
What would you like to do?
  (a) skip this ticket and continue with the queue
  (b) retry this ticket with new guidance
  (c) abort the batch
```

Wait for the user's choice. Do **not** auto-skip or auto-retry.

## When to invoke this skill vs `feature-workflow`

- One ticket → either works; this skill just wraps `feature-workflow` with the `ticket-reader` prefix. Use this skill when the user gave a ticket ID at all.
- Zero tickets (pure code request) → use `feature-workflow` directly; there is nothing for `ticket-reader` to fetch.
- Multiple tickets → always use this skill.

## Choosing not to use this workflow

Skip the full per-ticket loop for ticket items that are clearly:

- Single-line fixes, typos, comment changes — just edit, then advance the queue.
- Read-only questions about the codebase — just answer, then advance the queue.
- Pure refactors with no behavior change and existing coverage — `coder + reviewer` is enough (skip planner and tester), then advance the queue.

Use judgment per ticket. When in doubt for any ticket, ask the user whether to run the full loop for that one.
