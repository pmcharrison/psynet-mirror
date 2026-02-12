const path = require("path");
const { test, expect } = require("@playwright/test");

const {
  acceptConsents,
  advanceUntilFinish,
  beginExperiment,
  clickRecord,
  clickStartButton,
  getPageUuid,
  waitForNextEnabled,
  waitForPageChange,
  startExperiment,
  stopExperiment
} = require("../psynetHarness");

async function clickNextAndWait(page) {
  await waitForNextEnabled(page, 60000);
  const oldUuid = await getPageUuid(page);
  await page.click("#next-button");
  await waitForPageChange(page, oldUuid, 60000);
}

test("static_audio demo", async ({ page, context }) => {
  const absDir = path.resolve("demos/experiments/static_audio");
  const { proc, urlPromise } = startExperiment(absDir);
  try {
    const url = await urlPromise;
    const experimentPage = await beginExperiment(page, context, url);
    await acceptConsents(experimentPage);

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
  } finally {
    await stopExperiment(proc);
  }
});
