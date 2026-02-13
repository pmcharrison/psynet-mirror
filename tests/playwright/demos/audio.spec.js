const path = require("path");
const { test, expect } = require("@playwright/test");

const {
  advanceOneStep,
  advanceUntilPromptContains,
  advanceUntilFinish,
  clickAudioPlay,
  withExperiment
} = require("../psynetHarness");

test("audio demo", async ({ page, context }) => {
  const absDir = path.resolve("demos/experiments/audio");
  await withExperiment(page, context, absDir, async (experimentPage) => {
    await advanceUntilPromptContains(experimentPage, "JS synthesizer", {
      maxSteps: 20
    });
    await clickAudioPlay(experimentPage);
    await advanceOneStep(experimentPage);

    await advanceUntilPromptContains(experimentPage, "audio playback controls", {
      maxSteps: 20
    });
    await expect(experimentPage.locator("#prompt-text")).toContainText(
      "audio playback controls"
    );
    await clickAudioPlay(experimentPage);
    await advanceOneStep(experimentPage);

    await advanceUntilFinish(experimentPage);
  });
});
