import { test, expect, mintToken } from "./_fixtures";
import { expectNoSeriousA11yViolations } from "./_axe";

test("editor token sees disabled Promote with tooltip", async ({ page, apiBaseUrl }) => {
  const token = await mintToken(apiBaseUrl, "editor", "diff-e2e-editor");
  await page.goto("/login");
  await page.getByLabel("token").fill(token);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.goto("/diff");
  await expectNoSeriousA11yViolations(page);
  const promoteBtn = page.getByRole("button", { name: /^promote$/i });
  await expect(promoteBtn).toBeDisabled();
});

test("admin token: promote requires confirmation typing", async ({ page, apiBaseUrl }) => {
  const token = await mintToken(apiBaseUrl, "admin", "diff-e2e-admin");
  await page.goto("/login");
  await page.getByLabel("token").fill(token);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.goto("/diff");
  await expectNoSeriousA11yViolations(page);
  await page.getByRole("button", { name: /^promote$/i }).click();
  await page.getByLabel(/type "PROMOTE"/i).fill("PROMOTE");
  await page.getByRole("button", { name: /confirm promote/i }).click();
  await expect(page.getByText(/Production updated/)).toBeVisible({ timeout: 10_000 });
});
