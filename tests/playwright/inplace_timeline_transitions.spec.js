const path = require("path");
const { test, expect } = require("@playwright/test");

const {
  assertInplaceTimelinePathActive,
  clickNextAndWait,
  completeInitialGateway,
  waitForMainBodyContains,
  withExperiment
} = require("./psynetHarness");

const STEP_TIMEOUT_MS = 120000;

test("in-place timeline transitions replay page scripts and hydrate page styles", async ({
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

    const deferredMarker = experimentPage.locator(
      "#deferred-trial-construct-marker"
    );
    await expect(deferredMarker).toHaveAttribute(
      "data-trial-construct-handler-ran",
      "true",
      { timeout: STEP_TIMEOUT_MS }
    );
    await expect(deferredMarker).toContainText("trialConstruct handler ran");

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

    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    const stylesheetMarker = experimentPage.locator("#custom-stylesheet-marker");
    await expect(stylesheetMarker).toContainText("Styled custom template page", {
      timeout: STEP_TIMEOUT_MS
    });
    await expect(stylesheetMarker).toHaveCSS("color", "rgb(12, 34, 56)");
    await expect(stylesheetMarker).toHaveCSS("border-left-width", "7px");
    await expect(stylesheetMarker).toHaveCSS("padding-left", "13px");

    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await waitForMainBodyContains(experimentPage, "Cleanup page", STEP_TIMEOUT_MS);
    await expect(stylesheetMarker).toContainText("Unstyled cleanup marker", {
      timeout: STEP_TIMEOUT_MS
    });
    await expect(stylesheetMarker).not.toHaveCSS("color", "rgb(12, 34, 56)");
    await expect(stylesheetMarker).not.toHaveCSS("border-left-width", "7px");
  });
});

