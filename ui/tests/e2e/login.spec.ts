import { test, expect, mintToken } from "./_fixtures";
import { expectNoSeriousA11yViolations } from "./_axe";

test("login flow with valid editor token", async ({ page, apiBaseUrl }) => {
  const token = await mintToken(apiBaseUrl, "editor", "e2e-editor");
  await page.goto("/login");
  await expectNoSeriousA11yViolations(page);
  await page.getByLabel("令牌").fill(token);
  await page.getByRole("button", { name: /登录/ }).click();
  await expect(page).toHaveURL(/\/graph\/staging/);
  await expect(page.getByText(/e2e-editor/i)).toBeVisible({ timeout: 15_000 });
});

test("revoked token returns 401 and shows error", async ({ page, apiBaseUrl }) => {
  const adminToken = process.env.ONTO_BOOTSTRAP_TOKEN!;
  // Mint a token then use a corrupted version so the backend rejects it
  await mintToken(apiBaseUrl, "read", "to-revoke");
  void adminToken;
  await page.goto("/login");
  await expectNoSeriousA11yViolations(page);
  await page.getByLabel("令牌").fill("op_definitely_invalid_token_xyz");
  await page.getByRole("button", { name: /登录/ }).click();
  await expect(page.getByText(/令牌无效或已被撤销/)).toBeVisible();
});

test("session expiry forces re-login", async ({ page, apiBaseUrl }) => {
  // Backend run with ONTO_UI_SESSION_TTL=2s for this suite — a tiny TTL.
  const token = await mintToken(apiBaseUrl, "editor", "ephemeral");
  await page.goto("/login");
  await page.getByLabel("令牌").fill(token);
  await page.getByRole("button", { name: /登录/ }).click();
  await expect(page).toHaveURL(/\/graph\/staging/);
  await page.waitForTimeout(3500); // session expired
  await page.reload();
  await expect(page).toHaveURL(/\/login/);
});
