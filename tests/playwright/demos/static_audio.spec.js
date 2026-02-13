const path = require("path");
const { test, expect } = require("@playwright/test");

const {
  advanceUntilFinish,
  clickNextAndWait,
  clickRecord,
  clickStartButton,
  withExperiment
} = require("../psynetHarness");

test("static_audio demo", async ({ page, context }) => {
  const absDir = path.resolve("demos/experiments/static_audio");
  await withExperiment(page, context, absDir, async (experimentPage) => {
    await expect(experimentPage.locator("#main-body")).toContainText(
      "Please listen to the following sound",
      { timeout: 60000 }
    );
    await clickNextAndWait(experimentPage);

    await expect(experimentPage.locator("#main-body")).toContainText(
      "Please speak into your microphone",
      { timeout: 60000 }
    );
    await clickNextAndWait(experimentPage);

    await clickStartButton(experimentPage);
    await clickRecord(experimentPage);
    await advanceUntilFinish(experimentPage);
  });
});
