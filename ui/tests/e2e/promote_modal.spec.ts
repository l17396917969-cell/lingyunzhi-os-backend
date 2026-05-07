import { test, expect, mintToken } from "./_fixtures";

test("promote modal requires PROMOTE text", async ({ page, apiBaseUrl }) => {
  const token = await mintToken(apiBaseUrl, "admin", "promote-e2e");
  await page.goto("/login");
  await page.getByLabel("令牌").fill(token);
  await page.getByRole("button", { name: /登录/ }).click();
  await expect(page).toHaveURL(/\/graph\/staging/);

  // Toolbar button should be visible for admin scope
  await expect(page.getByRole("button", { name: /推送到生产/ })).toBeVisible();

  await page.getByRole("button", { name: /推送到生产/ }).click();

  // Confirm button starts disabled
  await expect(page.getByRole("button", { name: /确认推送/ })).toBeDisabled();

  // Type PROMOTE — confirm button enables
  await page.getByLabel("confirm-promote").fill("PROMOTE");
  await expect(page.getByRole("button", { name: /确认推送/ })).toBeEnabled();
});
