import { test, expect, mintToken } from "./_fixtures";
import { expectNoSeriousA11yViolations } from "./_axe";

test("chat session: send message → see agent reply or error → save", async ({ page, apiBaseUrl }) => {
  test.setTimeout(240_000);
  const token = await mintToken(apiBaseUrl, "editor", "chat-e2e");
  await page.goto("/login");
  await page.getByLabel("令牌").fill(token);
  await page.getByRole("button", { name: /登录/ }).click();
  await expect(page).toHaveURL(/\/graph\/staging/);

  await page.goto("/chat");
  await expect(page.getByRole("textbox", { name: "message" })).toBeVisible({ timeout: 15_000 });
  await expectNoSeriousA11yViolations(page);

  // Send a benign message that does not require file uploads
  await page.getByRole("textbox", { name: "message" }).fill("列出当前暂存区的对象类型即可");
  await page.getByRole("button", { name: /发送/ }).click();

  // Wait for either: an assistant reply text OR a turn-error toast.
  // The chat-backend persists an assistant message even when the LLM fails (with the zh-CN error string),
  // so any turn-completion path is acceptable here.
  await expect(
    page
      .getByText(/已完成本轮变更|本轮失败|本轮已取消/)
      .or(page.getByRole("alert"))
      .first()
  ).toBeVisible({ timeout: 180_000 });

  // Save closes session and redirects
  await page.getByRole("button", { name: /^保存$/ }).click();
  await expect(page).toHaveURL(/\/graph\/staging/, { timeout: 15_000 });
});

test("chat session: cancel rolls back and redirects", async ({ page, apiBaseUrl }) => {
  const token = await mintToken(apiBaseUrl, "editor", "chat-cancel-e2e");
  await page.goto("/login");
  await page.getByLabel("令牌").fill(token);
  await page.getByRole("button", { name: /登录/ }).click();
  await expect(page).toHaveURL(/\/graph\/staging/);

  await page.goto("/chat");
  await expect(page.getByRole("button", { name: /^取消$/ })).toBeVisible({ timeout: 15_000 });

  await page.getByRole("button", { name: /^取消$/ }).click();
  await expect(page).toHaveURL(/\/graph\/staging/, { timeout: 15_000 });
});
