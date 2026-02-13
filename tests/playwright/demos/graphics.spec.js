const path = require("path");
const { test, expect } = require("@playwright/test");

const {
  advanceUntilFinish,
  clickNextAndWait,
  submitAnswerAndWait,
  withExperiment
} = require("../psynetHarness");

test("graphics demo", async ({ page, context }) => {
  const absDir = path.resolve("demos/experiments/graphics");
  await withExperiment(page, context, absDir, async (experimentPage) => {
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
    await submitAnswerAndWait(experimentPage, {
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
    await submitAnswerAndWait(experimentPage, {
      clicked_object: "not_much",
      click_coordinates: [0, 0]
    });

    await advanceUntilFinish(experimentPage);
  });
});
