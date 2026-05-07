import { test, expect, mintToken } from "./_fixtures";
import { expectNoSeriousA11yViolations } from "./_axe";

test("cost_price detail panel shows CONFIDENTIAL badge", async ({ page, apiBaseUrl }) => {
  const token = await mintToken(apiBaseUrl, "editor", "mask-e2e");
  await page.goto("/login");
  await page.getByLabel("token").fill(token);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.goto("/browse/production");
  await expectNoSeriousA11yViolations(page);
  // Click into the material object; the JSON detail should include cost_price with sensitivity=CONFIDENTIAL.
  await page.getByText("material", { exact: false }).first().click();
  await expect(page.getByText(/CONFIDENTIAL/)).toBeVisible();
});
