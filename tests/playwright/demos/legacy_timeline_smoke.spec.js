const path = require("path");
const { test, expect } = require("@playwright/test");

const {
  assertLegacyTimelinePathActive,
  clickNextAndWait,
  completeInitialGateway,
  isInplaceTimelineModeEnabled,
  withExperiment
} = require("../psynetHarness");

const PROMPT_TIMEOUT_MS = 90000;
const STEP_TIMEOUT_MS = 120000;

test.skip(
  isInplaceTimelineModeEnabled(),
  "legacy timeline smoke runs only when inplace mode is disabled"
);

test("legacy timeline smoke", async ({ page, context }) => {
  const absDir = path.resolve("demos/features/modular_page");
  await withExperiment(page, context, absDir, async (experimentPage) => {
    await completeInitialGateway(experimentPage);
    await assertLegacyTimelinePathActive(experimentPage, 20000);

    await expect(experimentPage.locator("#main-body")).toContainText(
      "simple text page",
      { timeout: PROMPT_TIMEOUT_MS }
    );
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expect(experimentPage.locator("#main-body")).toContainText(
      "simple formatting",
      { timeout: PROMPT_TIMEOUT_MS }
    );
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expect(experimentPage.locator("#prompt-text")).toContainText(
      "RatingControl",
      { timeout: PROMPT_TIMEOUT_MS }
    );
  });
});
