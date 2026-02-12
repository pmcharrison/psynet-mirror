const path = require("path");
const { test, expect } = require("@playwright/test");

const {
  acceptConsents,
  advanceUntilFinish,
  beginExperiment,
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

async function nextPageWithAnswer(page, answer) {
  const oldUuid = await getPageUuid(page);
  await page.waitForFunction(
    () => typeof psynet !== "undefined" && typeof psynet.nextPage === "function",
    null,
    { timeout: 15000 }
  );
  await page.evaluate((payload) => psynet.nextPage(payload), answer);
  await waitForPageChange(page, oldUuid, 60000);
}

test("graphics demo", async ({ page, context }) => {
  const absDir = path.resolve("demos/experiments/graphics");
  const { proc, urlPromise } = startExperiment(absDir);
  try {
    const url = await urlPromise;
    const experimentPage = await beginExperiment(page, context, url);
    await acceptConsents(experimentPage);

    await expect(experimentPage.locator("#main-body")).toContainText(
      "Graphic components",
      { timeout: 60000 }
    );
    await clickNextAndWait(experimentPage);

    await expect(experimentPage.locator("#prompt-text")).toContainText(
      "different kinds of geometric objects",
      { timeout: 60000 }
    );
    await clickNextAndWait(experimentPage);

    await expect(experimentPage.locator("#prompt-text")).toContainText(
      "Click on one of the objects",
      { timeout: 60000 }
    );
    await nextPageWithAnswer(experimentPage, {
      clicked_object: "title",
      click_coordinates: [0, 0]
    });

    await clickNextAndWait(experimentPage);

    await expect(experimentPage.locator("#prompt-text")).toContainText(
      "synchronized audio",
      { timeout: 60000 }
    );
    await clickNextAndWait(experimentPage);

    await expect(experimentPage.locator("#prompt-text")).toContainText(
      "different font sizes",
      { timeout: 60000 }
    );
    await clickNextAndWait(experimentPage);

    await expect(experimentPage.locator("#prompt-text")).toContainText(
      "both a GraphicPrompt and a GraphicControl",
      { timeout: 60000 }
    );
    await nextPageWithAnswer(experimentPage, {
      clicked_object: "not_much",
      click_coordinates: [0, 0]
    });

    await advanceUntilFinish(experimentPage);
  } finally {
    await stopExperiment(proc);
  }
});
