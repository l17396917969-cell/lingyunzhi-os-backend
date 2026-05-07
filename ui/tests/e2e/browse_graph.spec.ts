import { test, expect, mintToken } from "./_fixtures";
import { expectNoSeriousA11yViolations } from "./_axe";

test.beforeEach(async ({ page, apiBaseUrl }) => {
  const token = await mintToken(apiBaseUrl, "editor", "browse-e2e");
  await page.goto("/login");
  await page.getByLabel("token").fill(token);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL("/");
});

test("ontology browser sidebar lists object types from production", async ({ page }) => {
  await page.goto("/browse/production");
  await expectNoSeriousA11yViolations(page);
  await expect(page.getByText("material", { exact: false })).toBeVisible();
  await page.getByText("material", { exact: false }).first().click();
  await expect(page.getByText(/"rid": "ri\.obj/)).toBeVisible();
});

test("graph view renders without overlapping nodes for fixture", async ({ page }) => {
  await page.goto("/graph/production");
  await expectNoSeriousA11yViolations(page);
  await page.waitForSelector(".react-flow__node");
  const nodes = await page.locator(".react-flow__node").all();
  const boxes = await Promise.all(nodes.map((n) => n.boundingBox()));
  // Sanity: every node has a position
  for (const b of boxes) expect(b).not.toBeNull();
  // None overlap by their full extent
  for (let i = 0; i < boxes.length; i++) {
    for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i]!;
      const b = boxes[j]!;
      const overlap = !(
        a.x + a.width <= b.x ||
        b.x + b.width <= a.x ||
        a.y + a.height <= b.y ||
        b.y + b.height <= a.y
      );
      expect(overlap).toBe(false);
    }
  }
});
