# Azure DevOps Ticket Standard (Agent-Ready Tickets)

A ticket is "agent-ready" when Claude Code can implement it **without asking a human anything**. Every Task work item MUST contain the sections below, in this order, inside the Description field (HTML/Markdown). Stories/PBIs use the lighter story format at the bottom.

## Task work item — required fields

### Work item system fields
| Field | Rule |
|---|---|
| Title | Verb-first, ≤ 100 chars, unique within the story. Format: `[Component] Action — object` e.g. `[API] Add POST /v1/exports endpoint`. Use plain language — see "Title wording" below. |
| Type | Task |
| Parent | Always linked to a User Story / PBI |
| Area Path / Iteration | Always set |
| Tags | `claude-code` + feature tag |
| Original Estimate | Hours (used to verify the task is ≤ 1 day; if larger → split) |
| Predecessor links | Set for every blocking dependency |

### Title wording (plain-language rule)
- Short: name one concrete action and its object.
- Specific: a reader can tell what changes from the title alone.
- Plain: no ornate/marketing words ("seamless", "empower", "elegant", "robust").
- Re-identifiable: easy to find and recognize later in a backlog list.

Good: `[API] Add POST /v1/exports endpoint`
Bad: `[API] Elegantly empower seamless export experiences`

### Description — required sections

```
## Context
Why this task exists. 2–4 sentences linking it to the parent story.
What is already done / will be done by other tasks (with ticket IDs).

## Scope
- Repo + branch to base from (e.g. repo `data-platform`, branch `develop`)
- Files/modules expected to change (paths). "New file" is allowed but state the path.
- Explicitly OUT of scope (what NOT to touch).

## Technical approach
Concrete instructions: which pattern/class/function to follow or extend,
library versions, config keys, schema names. Reference an existing example
in the codebase when one exists ("follow the pattern in src/jobs/ingest_x.py").

## Acceptance criteria
- [ ] Checkbox list, each item objectively verifiable
- [ ] Include at least one negative/edge case
- [ ] Include the test requirement (e.g. "unit tests in tests/..., coverage of new code")

## Definition of Done
- [ ] Code merged via PR to <branch>, PR linked to this work item
- [ ] CI green (build + tests + lint)
- [ ] Docs/README updated if behavior changed
- [ ] No secrets/credentials committed

## Dependencies
- Blocked by: #<id> (reason)
- Blocks: #<id>

## Validation steps
Exact commands or manual steps a reviewer runs to verify
(e.g. `pytest tests/exports -q`, sample curl request + expected response).
```

### Quality gates before creating a ticket
Reject (rewrite) the ticket if ANY is true:
- Title uses vague/ornate wording or doesn't name a concrete action/object → rewrite.
- Acceptance criteria contain subjective words ("works well", "fast enough") without numbers.
- Scope lists zero file paths and zero modules.
- Estimated effort > 1 dev-day → split it.
- It depends on a decision not yet made → create a spike/decision task first.

## User Story / PBI format

```
## Story
As a <role>, I want <capability>, so that <benefit>.

## Background
Business context, links to PRD/design doc.

## Feature-level acceptance criteria
- [ ] End-to-end observable outcomes (not implementation details)

## Child tasks
Auto-populated by links; list planned tasks here during planning.

## Non-functional requirements
Performance, security, i18n (e.g. JP/VN locale), data retention — only if applicable.
```

## Bug work item (when used)
Same as Task, plus: **Repro steps**, **Expected vs Actual**, **Environment/version**, and root-cause field after fix.
