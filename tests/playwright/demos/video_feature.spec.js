const path = require("path");
const { test, expect } = require("@playwright/test");

const {
  acceptConsents,
  advanceUntilFinish,
  beginExperiment,
  clickRecord,
  waitForNextEnabled,
  startExperiment,
  stopExperiment
} = require("../psynetHarness");

test("video feature demo", async ({ page, context }) => {
  const absDir = path.resolve("demos/features/video");
  const { proc, urlPromise } = startExperiment(absDir);
  try {
    const url = await urlPromise;
    const experimentPage = await beginExperiment(page, context, url);
    await acceptConsents(experimentPage);

    await expect(experimentPage.locator("video#prompt")).toBeVisible({
      timeout: 60000
    });
    await waitForNextEnabled(experimentPage, 60000);
    await experimentPage.click("#next-button");

    await clickRecord(experimentPage);
    await advanceUntilFinish(experimentPage);
  } finally {
    await stopExperiment(proc);
  }
});
