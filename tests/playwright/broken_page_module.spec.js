const path = require("path");
const { test, expect } = require("./fixtures");

const {
  assertNoBackendError,
  completeInitialGateway,
  withExperiment
} = require("./psynetHarness");

const STEP_TIMEOUT_MS = 120000;

test("full-page managed JavaScript failures show a refresh prompt", { tag: "@both" }, async ({
  page,
  context
}) => {
  const absDir = path.resolve(
    "tests/playwright/experiments/broken_page_module"
  );

  await withExperiment(page, context, absDir, async (experimentPage) => {
    await completeInitialGateway(experimentPage);

    await expect(experimentPage.locator("#alert-message")).toContainText(
      "This page could not be loaded. Please refresh the page and try again.",
      { timeout: STEP_TIMEOUT_MS }
    );
    await expect
      .poll(
        () =>
          experimentPage.evaluate(() => ({
            pageReady: window.psynet?.pageReady === true,
            nextDisabled: document
              .getElementById("next-button")
              ?.hasAttribute("disabled")
          })),
        { timeout: 10000 }
      )
      .toEqual({
        pageReady: false,
        nextDisabled: true
      });

    await experimentPage.locator("#alert-button").click();
    await assertNoBackendError(experimentPage);
  });
});
