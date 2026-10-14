---
name: playwright-e2e
description: Use when writing or modifying Playwright E2E tests. Enforces Page Object Model, network mocking for third parties, isolated per-PR env, and stable selectors.
---

# Playwright E2E

## Layout

```
e2e/
  pages/                 # Page Object Model classes
  fixtures/              # test users, JSON payloads (anonymized)
  specs/                 # *.spec.ts test files
  playwright.config.ts
```

## Rules

1. **Run against a per-PR ephemeral env.** Never against shared staging or prod. The base URL is injected via `BASE_URL` env var.
2. **Stable selectors only**: `getByRole`, `getByLabel`, `getByTestId`. Never CSS classes that come from Tailwind.
3. **Page Object Model**: one class per page or large component. Selectors live in the POM, not in specs.
4. **No `page.waitForTimeout`.** Use `expect(locator).toBeVisible()` and `page.waitForResponse(...)`.
5. **Third-party services mocked** via `page.route`. Auth providers, payment gateways, telemetry — all intercepted.
6. **One assertion concept per test.** Multiple `expect` lines are fine if they cover the same behavior.
7. **Parallel-safe**: each test creates its own data (use `faker` + a `test_*` prefix) and cleans up via API teardown.
8. **No real credentials.** Test users come from `e2e/fixtures/users.json` and are seeded on env spin-up.

## Page Object template

```ts
// e2e/pages/UsersPage.ts
import { Page, Locator, expect } from "@playwright/test";

export class UsersPage {
  readonly page: Page;
  readonly createButton: Locator;
  readonly emailInput: Locator;
  readonly nameInput: Locator;
  readonly submitButton: Locator;

  constructor(page: Page) {
    this.page = page;
    this.createButton = page.getByRole("button", { name: "Add user" });
    this.emailInput = page.getByLabel("Email");
    this.nameInput = page.getByLabel("Display name");
    this.submitButton = page.getByRole("button", { name: "Create" });
  }

  async goto() {
    await this.page.goto("/users");
    await expect(this.createButton).toBeVisible();
  }

  async createUser(email: string, name: string) {
    await this.createButton.click();
    await this.emailInput.fill(email);
    await this.nameInput.fill(name);
    await this.submitButton.click();
    await expect(this.page.getByRole("row", { name: email })).toBeVisible();
  }
}
```

## Spec template

```ts
// e2e/specs/users.spec.ts
import { test, expect } from "@playwright/test";
import { faker } from "@faker-js/faker";
import { UsersPage } from "../pages/UsersPage";

test("admin can create a user", async ({ page }) => {
  const email = `test_${faker.string.uuid()}@example.com`;
  const users = new UsersPage(page);

  await users.goto();
  await users.createUser(email, "Test User");

  await expect(page.getByRole("row", { name: email })).toBeVisible();
});
```

## Commands

```bash
pnpm exec playwright install --with-deps
pnpm exec playwright test                       # all specs
pnpm exec playwright test users.spec.ts         # one spec
pnpm exec playwright test --ui                  # interactive
pnpm exec playwright show-report                # last report
```
