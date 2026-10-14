# Project rules

This file is automatically loaded into every Claude Code session in this repo. Keep it short and durable — facts that change every sprint belong in a ticket, not here.

## Tech stack

- **Infra**: Azure, Terraform (IaC)
- **Repo & PM**: Azure DevOps (Boards, Repos, Pipelines), GitHub
- **Backend**: Python (FastAPI) + TypeScript services
- **ORM**: SQLAlchemy 2.x, SQLModel
- **Databases**: PostgreSQL, Azure SQL, Cosmos DB
- **Frontend**: React + TailwindCSS
- **Testing**: pytest (unit/integration), Playwright (E2E)
- **Containers**: Docker / docker compose
- **CI/CD**: Azure DevOps Pipelines, GitHub Actions
- **Lint/format**: ruff + mypy (Python), eslint + prettier + tsc (TS/React), terraform fmt + tflint, hadolint (Dockerfile)

## Repo-specific overrides (RiceBridge Ops)

This repo is a **public** Python hackathon demo. Where the company defaults below disagree with this section, **this section wins**.

- **What it is**: `src/ricebridge` — a stdlib `http.server` backend, a vanilla HTML/JS/CSS UI in `src/ricebridge/web/`, a numpy/pandas simulation in `src/ricebridge/sim/`. Architecture and ADRs: `docs/design/`.
- **Stack actually used**: Python 3.10+ (no FastAPI/SQLAlchemy/DB), `ruff` + `pytest`, Playwright for Python in `tests/e2e/`. There is no Node/React/Terraform here; the FastAPI/React/Terraform/pnpm rules apply only if such code is added.
- **Run**: `pip install -e ".[dev]"`, then `python -m ricebridge --stage --open`.
- **Check before a PR**: `ruff check src tests scripts && pytest && pytest tests/e2e -m e2e`. `mypy --strict` is not enforced.
- **Branches**: base branch is `dev`. Never push to `dev` or `main`; open a PR into `dev`. After the PR is merged, delete the branch locally and on the remote. No `Co-Authored-By`/attribution lines in commits or PR bodies.
- **Frozen inputs**: do not change LLM prompt strings, schemas or the images in `data/vision/testset/` without regenerating the caches (`data/llm_cache/`, `data/i18n/`, `data/vision/cache/`). Cache keys are hashes of them. See `docs/design/adr/0003-committed-deterministic-caches.md`.
- **Guardrail boundary**: the LLM never approves plans, edits readings or sets water thresholds; deterministic tools decide, a human approves.
- **Docs** go in `docs/research`, `docs/design`, `docs/manual`, `docs/report`.
- **Public repo**: no internal project names, work-item IDs, colleague e-mails or customer data in files; the Azure DevOps task-breakdown skill is intentionally not included.

## Security rules (non-negotiable)

1. **Never read or write secrets.** No `.env`, `*.pem`, `*.key`, `~/.aws`, `~/.ssh`, `~/.azure`, or anything under `secrets/`. If a task seems to require a real secret, stop and ask the user to provide it via env var at runtime.
2. **Never commit secrets.** Verify `git diff --staged` does not include connection strings, tokens, SAS URLs, or keys. Use Azure Key Vault references in code.
3. **No destructive ops without confirmation.** `git push --force`, `terraform destroy`, `az group delete`, `DROP`/`TRUNCATE` on any non-local DB — always ask first.
4. **Treat `main` and release branches as protected.** Always work on a feature branch. Open a PR; do not push directly.
5. **Pin and verify external code.** No `curl | sh`. No installing global packages without asking. No new dependencies without a stated reason.
6. **SQL must be parameterized.** Never build queries by string concatenation. With SQLAlchemy use bound parameters / ORM expressions; with raw SQL use `text()` + params.
7. **Validate all external input.** FastAPI: Pydantic models at the boundary. React: never inject user input into `dangerouslySetInnerHTML`.
8. **AuthN/AuthZ at every endpoint.** New FastAPI routes must declare a security dependency unless explicitly public — and if public, say so in the docstring.
9. **PII / customer data.** Never paste production data into prompts, logs, or tests. Use anonymized fixtures.
10. **No telemetry exfiltration.** Don't add network calls, analytics, or "phone home" code to internal libs without an explicit ask.

## Coding standards

- **Python**: 3.11+, type hints required on public functions, `ruff` clean, `mypy --strict` for new modules. Prefer SQLModel for new tables, SQLAlchemy Core for complex queries.
- **TypeScript**: strict mode on, no `any` in new code, prefer functional React components + hooks, Tailwind utility-first (no ad-hoc CSS files unless asked).
- **FastAPI**: routers in `app/api/`, schemas in `app/schemas/`, models in `app/models/`, services in `app/services/`. Dependency-inject DB sessions; do not create sessions inside handlers.
- **Terraform**: one module per logical unit, remote state in Azure Storage, never commit `*.tfstate` or `*.tfvars` containing secrets. Use `azurerm` provider with a pinned version.
- **Docker**: multi-stage builds, non-root user in final stage, no secrets in `ARG`/`ENV`, pin base image by digest in production.
- **Tests**: every bug fix gets a regression test. New endpoints get at least one happy-path + one auth-failure test. Playwright tests live in `e2e/` and run against a disposable env.

## Workflow

- **Where code is written:** all code, branches, commits, and PRs go to the **repo currently open in the IDE** (the working repo). This is **not necessarily** the Azure DevOps repo/project the ticket lives in — a ticket in ADO project X may be implemented in a GitHub repo or a different Azure Repos repo. The ticket and its **state** live in ADO; the branch + PR live in the working repo. Link them by putting the ticket ID (`AB#<id>`) in the branch name, commit messages, and PR title/description.
- **Base branch:** branch feature work from **`dev`** (the integration branch of this repo; the company default `develop` does not exist here). `main` and release branches stay protected (security rule #4).
- Branch naming: `feat/<ticket>-short-desc`, `fix/<ticket>-…`, `chore/…`
- Commit messages: imperative mood, reference the ADO/GH ticket (e.g. `feat(api): add user export endpoint (AB#1234)`)
- Before opening a PR run locally: `ruff check && mypy && pytest -q` (Python) or `pnpm lint && pnpm test && tsc --noEmit` (TS).
- PR description: what changed, why, how to verify, screenshots for UI.

### Ticket lifecycle (when a ticket is involved)

The **main agent** drives these side-effects around the pipeline — subagents never do git or ticket mutations:

1. **Start** (after the plan is approved, before coding): set the ticket's ADO state to the in-progress state (e.g. `Doing` / `Active`), then create the feature branch from the base branch on the working repo: `git fetch && git switch <base> && git pull && git switch -c feat/<id>-<short-desc>`.
2. **Implement**: run the normal pipeline (planner → coder ↔ reviewer → tester).
3. **Finish** (once tester is `ALL_GREEN`): run the pre-PR local checks, commit (message references `AB#<id>`), push the branch, open a PR on the **working repo** targeting the base branch (GitHub: `gh pr create`; Azure Repos: `az repos pr create`) with the ticket ID linked, then set the ticket's ADO state to the in-review state (e.g. `Review` / `Code Review`).

State names vary by ADO process template — use the closest in-progress / in-review state and tell the user which. Setting ADO state is a **write by the main agent** via the azure-devops MCP; the `ticket-reader` fetch-only rule does not apply to the orchestrator. `git push` and PR creation still pass through the permission `ask` gate — that is expected.

## Default workflow for non-trivial changes

Two entry points:

- **No ticket** (pure code request) → invoke the **feature-workflow** skill.
- **One or more ADO ticket IDs** referenced (e.g. `AB#1234`, `xử lý ticket 1234 và 1235`) → invoke the **multi-ticket-workflow** skill. It loops the same pipeline below for each ticket, strictly sequentially (no parallel tickets), and stops the whole batch on the first ticket that BLOCKs.

Per-ticket pipeline:

```
ticket-reader (only if ticket(s) provided)
     │
     ▼
  planner → coder → reviewer ──(REQUEST_CHANGES, ≤3×)──▶ coder ──▶ reviewer
                                                                     │
                                                                APPROVE
                                                                     ▼
                                                                  tester
                                                                     │
                                            ┌────PRODUCTION_BUG_FOUND, ≤2×───┐
                                            ▼                                │
                                          coder ─▶ reviewer ─▶ tester ───────┘
                                                                     │
                                                                ALL_GREEN
                                                                     ▼
                                                                  done (next ticket, if any)
```

Rules:
- Subagents do **not** call each other. The main agent dispatches them and reads each agent's terminal `STATUS:` / `VERDICT:` line to route the next step.
- `ticket-reader` is the **only** agent allowed to fetch ADO work items. `planner` consumes its brief — it must not re-fetch.
- Multi-ticket runs are strictly sequential. Process ticket N's full pipeline before starting ticket N+1.
- Caps: review loop **3 iterations**, test loop **2 iterations**. On cap, stop and ask the user.
- A ticket that BLOCKs stops the **whole batch** — do not silently skip and continue.
- **Ticket side-effects are the main agent's job** (not subagents): at start set ADO state → in-progress and branch from the base branch on the working repo; at `ALL_GREEN` commit, push, open the PR, and set ADO state → in-review. See **Workflow → Ticket lifecycle** above.
- Skip the workflow only for: typos, one-liners, read-only questions, pure refactors with existing coverage (coder + reviewer is enough then).

## Docs organization

`docs/` is split into 4 subfolders by what kind of document it is — almost every piece of work
produces some subset of these 3-4 kinds, so file new docs directly into the right one instead of
dropping them at `docs/` root:

- **`docs/research/`** — open-ended investigation/exploration: comparing options, root-causing a
  bug, reading up on a library/tool. No fixed conclusion driving implementation yet.
- **`docs/design/`** — a plan or decision made before or to guide implementation: scope
  definitions, architecture/schema design, "how this will work" docs.
- **`docs/manual/`** — how-to/usage/setup guides meant to be followed step by step (not findings).
- **`docs/report/`** — measured outcomes, comparisons, findings-as-deliverable: benchmark
  results, before/after comparisons, anything that reports what was found or measured.

A single work item (e.g. one ADO task) commonly produces 2-3 of these as separate files — don't
force everything into one doc. A folder for one ongoing workstream with a natural mix (e.g. a
guide + a status README + raw data files) can stay as one unit under whichever category fits its
primary purpose — don't split a single active folder's internals across categories.

When linking between docs, use relative paths (`../research/name.md` etc.) — verify the link
resolves after moving/creating files, don't just pattern-match the old bare-filename style.

## When in doubt

- Use the **ticket-reader** subagent first whenever the user references an ADO ticket — never plan from the raw user message.
- Use the **planner** subagent for non-trivial work before coding.
- Use the **reviewer** subagent on your own diff before pushing.
- Ask the user rather than guessing on architecture, secrets, or production data.
