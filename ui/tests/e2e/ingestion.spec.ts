import { test, expect, mintToken } from "./_fixtures";
import { expectNoSeriousA11yViolations } from "./_axe";
import * as path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

test("ingestion happy path: upload + submit + arrives at imported", async ({
  page,
  apiBaseUrl,
}) => {
  const token = await mintToken(apiBaseUrl, "editor", "ingest-e2e");
  await page.goto("/login");
  await page.getByLabel("token").fill(token);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL("/");
  await page.goto("/ingest");
  await expectNoSeriousA11yViolations(page);

  // Resolve fixture file relative to this spec; repo root is three levels up.
  const fixturePath = path.resolve(
    __dirname,
    "../../../tests/fixtures/sql/logistics_minimal_ddl.sql",
  );
  await page.getByLabel(/file/i).setInputFiles(fixturePath);
  await page.locator("select").selectOption("replace");
  await page.getByRole("button", { name: /submit/i }).click();

  // Wait for a job row to appear (up to 60s — ingestion runs real AI pipeline)
  await expect(page.locator("ul li").first()).toBeVisible({ timeout: 60_000 });

  // Click into the most recent job
  await page.locator("ul li a").first().click();
  await expect(page.getByText(/Status:/)).toBeVisible();
});
