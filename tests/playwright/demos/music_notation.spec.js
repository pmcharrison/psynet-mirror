const path = require("path");
const { test, expect } = require("../fixtures");

const {
  assertExpectedTimelinePathActive,
  assertNoBackendError,
  completeInitialGateway,
  withExperiment
} = require("../psynetHarness");

const STEP_TIMEOUT_MS = 120000;

test("music notation loads package-owned resources", async ({ page, context }) => {
  await withExperiment(
    page,
    context,
    path.resolve("demos/features/music_notation"),
    async (experimentPage) => {
      await completeInitialGateway(experimentPage);
      await assertExpectedTimelinePathActive(experimentPage, 20000);
      await expect(experimentPage.locator("#abcScore svg")).toBeVisible({
        timeout: STEP_TIMEOUT_MS
      });
      await assertNoBackendError(experimentPage);
    }
  );
});
