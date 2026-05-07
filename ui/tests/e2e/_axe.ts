import { type Page, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/**
 * Run axe-core on the current page and fail if any serious or critical
 * accessibility violations are found.
 *
 * Called inside every e2e spec immediately after page navigation so that
 * every screen has a11y coverage.
 */
export async function expectNoSeriousA11yViolations(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page }).analyze();
  const serious = results.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical",
  );
  if (serious.length) {
    console.log("axe violations:", JSON.stringify(serious, null, 2));
  }
  expect(serious, "expected no serious/critical axe violations").toHaveLength(0);
}
