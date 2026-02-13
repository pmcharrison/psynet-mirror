const path = require("path");
const { test, expect } = require("@playwright/test");

const {
  advanceUntilFinish,
  clickNextAndWait,
  clickRecord,
  withExperiment
} = require("../psynetHarness");

test("imitation_chain_video demo", async ({ page, context }) => {
  const absDir = path.resolve("demos/experiments/imitation_chain_video");
  await withExperiment(page, context, absDir, async (experimentPage) => {
    await expect(experimentPage.locator("#main-body")).toContainText(
      "Please speak into your microphone",
      { timeout: 60000 }
    );
    await clickNextAndWait(experimentPage, 60000);

    await clickRecord(experimentPage);
    await advanceUntilFinish(experimentPage);
  });
});
