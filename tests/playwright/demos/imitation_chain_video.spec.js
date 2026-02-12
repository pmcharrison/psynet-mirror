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

test("imitation_chain_video demo", async ({ page, context }) => {
  const absDir = path.resolve("demos/experiments/imitation_chain_video");
  const { proc, urlPromise } = startExperiment(absDir);
  try {
    const url = await urlPromise;
    const experimentPage = await beginExperiment(page, context, url);
    await acceptConsents(experimentPage);

    await expect(experimentPage.locator("#main-body")).toContainText(
      "Please speak into your microphone",
      { timeout: 60000 }
    );
    await waitForNextEnabled(experimentPage, 60000);
    await experimentPage.click("#next-button");

    await clickRecord(experimentPage);
    await advanceUntilFinish(experimentPage);
  } finally {
    await stopExperiment(proc);
  }
});
