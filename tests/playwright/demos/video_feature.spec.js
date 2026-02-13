const path = require("path");
const { test, expect } = require("@playwright/test");

const {
  advanceUntilFinish,
  clickNextAndWait,
  clickRecord,
  withExperiment
} = require("../psynetHarness");

test("video feature demo", async ({ page, context }) => {
  const absDir = path.resolve("demos/features/video");
  await withExperiment(page, context, absDir, async (experimentPage) => {
    await expect(experimentPage.locator("video#prompt")).toBeVisible({
      timeout: 60000
    });
    await clickNextAndWait(experimentPage, 60000);

    await clickRecord(experimentPage);
    await advanceUntilFinish(experimentPage);
  });
});
