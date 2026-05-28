const path = require("path");
const { test, expect } = require("@playwright/test");

const {
  assertInplaceTimelinePathActive,
  clickNextAndWait,
  completeInitialGateway,
  withExperiment,
  waitForMainBodyContains
} = require("./psynetHarness");

const STEP_TIMEOUT_MS = 120000;

test("custom template stylesheet block survives in-place fragment swaps", async ({
  page,
  context
}) => {
  const absDir = path.resolve(
    "tests/playwright/experiments/custom_template_stylesheet"
  );

  await withExperiment(page, context, absDir, async (experimentPage) => {
    await completeInitialGateway(experimentPage);
    await assertInplaceTimelinePathActive(experimentPage, STEP_TIMEOUT_MS);

    await waitForMainBodyContains(experimentPage, "First page", STEP_TIMEOUT_MS);
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    const marker = experimentPage.locator("#custom-stylesheet-marker");
    await expect(marker).toContainText("Styled custom template page", {
      timeout: STEP_TIMEOUT_MS
    });
    await expect(marker).toHaveCSS("color", "rgb(12, 34, 56)");
    await expect(marker).toHaveCSS("border-left-width", "7px");
    await expect(marker).toHaveCSS("padding-left", "13px");

    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expect(marker).toContainText("Unstyled cleanup marker", {
      timeout: STEP_TIMEOUT_MS
    });
    await expect(marker).not.toHaveCSS("color", "rgb(12, 34, 56)");
    await expect(marker).not.toHaveCSS("border-left-width", "7px");
  });
});

