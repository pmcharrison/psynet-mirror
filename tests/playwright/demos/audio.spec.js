const path = require("path");
const { test, expect } = require("@playwright/test");

const {
  acceptConsents,
  advanceUntilFinish,
  beginExperiment,
  clickAudioPlay,
  getPageUuid,
  startExperiment,
  stopExperiment,
  waitForNextEnabled,
  waitForPageChange
} = require("../psynetHarness");

async function getPromptText(page) {
  const prompt = page.locator("#prompt-text");
  if ((await prompt.count()) === 0) {
    return "";
  }
  return (await prompt.first().innerText()).trim();
}

async function advanceOneStep(page) {
  await acceptConsents(page);

  const nextButton = page.locator("#next-button");
  if ((await nextButton.count()) === 0) {
    return false;
  }

  if (!(await nextButton.isEnabled())) {
    await clickAudioPlay(page);
    if ((await page.locator("#btn-record-record").count()) > 0) {
      await page.click("#btn-record-record", { force: true }).catch(() => {});
    }
    if ((await page.locator("#buttonStart").count()) > 0) {
      await page.click("#buttonStart", { force: true }).catch(() => {});
    }
    await waitForNextEnabled(page, 15000).catch(() => {});
  }

  if (!(await nextButton.isEnabled())) {
    return false;
  }

  const oldUuid = await getPageUuid(page);
  await nextButton.click();
  await waitForPageChange(page, oldUuid, 60000).catch(async () => {
    await page.waitForLoadState("networkidle", { timeout: 5000 }).catch(() => {});
  });
  return true;
}

async function advanceUntilPromptContains(page, text, maxSteps = 20) {
  let stalledAttempts = 0;
  for (let step = 0; step < maxSteps; step += 1) {
    const promptText = await getPromptText(page);
    if (promptText.includes(text)) {
      return;
    }

    const progressed = await advanceOneStep(page);
    if (!progressed) {
      stalledAttempts += 1;
      if (stalledAttempts >= 6) {
        throw new Error(
          `Could not progress to prompt containing "${text}". Current prompt: "${promptText}".`
        );
      }
      await page.waitForTimeout(1000);
      continue;
    }
    stalledAttempts = 0;
  }

  throw new Error(`Did not reach prompt containing "${text}" within ${maxSteps} steps.`);
}

test("audio demo", async ({ page, context }) => {
  const absDir = path.resolve("demos/experiments/audio");
  const { proc, urlPromise } = startExperiment(absDir);
  try {
    const url = await urlPromise;
    const experimentPage = await beginExperiment(page, context, url);
    await acceptConsents(experimentPage);

    await advanceUntilPromptContains(experimentPage, "JS synthesizer", 20);
    await clickAudioPlay(experimentPage);
    await advanceOneStep(experimentPage);

    await advanceUntilPromptContains(experimentPage, "audio playback controls", 20);
    await expect(experimentPage.locator("#prompt-text")).toContainText(
      "audio playback controls"
    );
    await clickAudioPlay(experimentPage);
    await advanceOneStep(experimentPage);

    await advanceUntilFinish(experimentPage);
  } finally {
    await stopExperiment(proc);
  }
});
