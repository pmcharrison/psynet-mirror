const path = require("path");
const { test, expect } = require("../fixtures");

const {
  assertInplaceTimelinePathActive,
  assertNoBackendError,
  clickNextAndWait,
  completeInitialGateway,
  withExperiment
} = require("../psynetHarness");

const STEP_TIMEOUT_MS = 120000;

test("jsPsych activates after an in-place transition", async ({ page, context }) => {
  await withExperiment(
    page,
    context,
    path.resolve("demos/experiments/jspsych"),
    async (experimentPage) => {
      await completeInitialGateway(experimentPage);
      await assertInplaceTimelinePathActive(experimentPage, 20000);
      await expect(experimentPage.locator("#main-body")).toContainText(
        "jsPsych task begins",
        { timeout: STEP_TIMEOUT_MS }
      );

      await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);
      await expect(experimentPage.locator("#js-psych")).toContainText(
        "Welcome to the experiment",
        { timeout: STEP_TIMEOUT_MS }
      );
      await assertNoBackendError(experimentPage);
    }
  );
});
