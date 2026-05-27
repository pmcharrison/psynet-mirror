const path = require("path");
const { test, expect } = require("@playwright/test");

const {
  assertInplaceTimelinePathActive,
  clickNextAndWait,
  completeInitialGateway,
  withExperiment
} = require("./psynetHarness");

const STEP_TIMEOUT_MS = 120000;

test("deferred page scripts register trialConstruct handlers before partial page init", async ({
  page,
  context
}) => {
  const absDir = path.resolve(
    "tests/playwright/experiments/deferred_page_scripts"
  );

  await withExperiment(page, context, absDir, async (experimentPage) => {
    await completeInitialGateway(experimentPage);
    await assertInplaceTimelinePathActive(experimentPage, 20000);

    await expect(experimentPage.locator("#main-body")).toContainText("First page", {
      timeout: STEP_TIMEOUT_MS
    });

    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    const marker = experimentPage.locator("#deferred-trial-construct-marker");
    await expect(marker).toHaveAttribute(
      "data-trial-construct-handler-ran",
      "true",
      { timeout: STEP_TIMEOUT_MS }
    );
    await expect(marker).toContainText("trialConstruct handler ran");

    await expect(experimentPage.locator("#deferred-css-marker")).toHaveCSS(
      "color",
      "rgb(12, 34, 56)"
    );

    await expect
      .poll(
        () =>
          experimentPage.evaluate(
            () =>
              window.__psynetDeferredPageScript?.scriptExecuted === true &&
              window.__psynetDeferredPageScript?.trialConstructHandlerRan === true
          ),
        { timeout: STEP_TIMEOUT_MS }
      )
      .toBe(true);
  });
});
