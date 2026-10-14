## What

<!-- What changed, in a few lines. -->

## Why

<!-- The problem or need. Link the ticket if any (AB#1234). -->

## How to verify

<!-- Commands to run or steps to click through. Screenshots for UI changes. -->

## Checklist

- [ ] Branched from `dev` and targeting `dev`
- [ ] `ruff check src tests scripts` and `pytest` pass locally
- [ ] If a prompt string, schema or test image changed: LLM/vision caches regenerated (see `docs/design/adr/0003-committed-deterministic-caches.md`)
- [ ] No secrets, tokens or personal data in the diff
- [ ] Docs updated if behaviour or layout changed
