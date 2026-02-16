const path = require("path");
const { test, expect } = require("@playwright/test");

const {
  clickNextAndWait,
  waitForNextEnabled,
  withExperiment
} = require("../psynetHarness");

const PROMPT_TIMEOUT_MS = 90000;
const STEP_TIMEOUT_MS = 120000;

async function expectPromptContains(page, text, timeout = PROMPT_TIMEOUT_MS) {
  await expect(page.locator("#prompt-text")).toContainText(text, {
    timeout
  });
}

async function expectMainBodyContains(page, text, timeout = PROMPT_TIMEOUT_MS) {
  await expect(page.locator("#main-body")).toContainText(text, {
    timeout
  });
}

async function useStandardAudioControls(page, options = {}) {
  const stopAfterPlay = options.stopAfterPlay ?? true;
  const playButton = page.locator("#audio-prompt-play");
  const stopButton = page.locator("#audio-prompt-stop");
  const loopToggle = page.locator("#audio-prompt-loop-input");
  await expect(playButton).toBeVisible();
  await expect(stopButton).toBeVisible();
  await expect(loopToggle).toBeVisible();
  await expect(playButton).toBeEnabled();

  await playButton.click();
  if (stopAfterPlay) {
    await stopButton.click();
  }

  const wasChecked = await loopToggle.isChecked();
  await loopToggle.click();
  if (wasChecked) {
    await expect(loopToggle).not.toBeChecked();
  } else {
    await expect(loopToggle).toBeChecked();
  }
}

test("audio demo", async ({ page, context }) => {
  const absDir = path.resolve("demos/experiments/audio");
  await withExperiment(page, context, absDir, async (experimentPage) => {
    await expectPromptContains(
      experimentPage,
      "harmonic complex tone as the timbre"
    );
    await useStandardAudioControls(experimentPage);
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expectPromptContains(experimentPage, "select various instrument sounds");
    await expect(experimentPage.locator("#audio-prompt-play")).toHaveCount(0);
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expectPromptContains(
      experimentPage,
      "manipulate individual notes with a slider"
    );
    const slider = experimentPage.locator("#sliderpage_slider");
    await expect(slider).toBeVisible();
    await expect(slider).toBeEnabled();
    const sliderValueBefore = Number(await slider.inputValue());
    await slider.focus();
    await experimentPage.keyboard.press("ArrowRight");
    await expect
      .poll(async () => Number(await slider.inputValue()), { timeout: 5000 })
      .not.toBe(sliderValueBefore);
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expectPromptContains(experimentPage, "Shepard tones");
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expectPromptContains(experimentPage, "custom sampler");
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expectPromptContains(
      experimentPage,
      "simple audio page with one stimulus"
    );
    await expect(experimentPage.locator("#audio-prompt-controls")).toHaveCount(0);
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expectPromptContains(experimentPage, "loops the same stimulus");
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expectPromptContains(experimentPage, "adds audio playback controls");
    await expect(experimentPage.locator("#next-button")).toBeDisabled();
    await useStandardAudioControls(experimentPage, { stopAfterPlay: false });
    await waitForNextEnabled(experimentPage, 45000);
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expectPromptContains(experimentPage, "customizes the audio controls");
    await expect(experimentPage.locator("#audio-prompt-play")).toContainText(
      "Play again"
    );
    await expect(experimentPage.locator("#audio-prompt-stop")).toHaveCount(0);
    await expect(experimentPage.locator("#audio-prompt-loop-input")).toHaveCount(
      0
    );
    await experimentPage.locator("#audio-prompt-play").click();
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expectPromptContains(
      experimentPage,
      "access audio stimuli outside of Audio Prompts"
    );
    await expect(experimentPage.locator("#audio-prompt-controls")).toHaveCount(0);
    await waitForNextEnabled(experimentPage, 60000);
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expectPromptContains(experimentPage, "play window");
    await useStandardAudioControls(experimentPage);
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expectPromptContains(experimentPage, "shows an audio meter");
    await expect(experimentPage.locator("#audio-meter")).toBeVisible();
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expectPromptContains(experimentPage, "lets you record audio");
    const firstRecordButton = experimentPage.locator("#btn-record-record");
    await expect(firstRecordButton).toBeVisible();
    await expect(firstRecordButton).toBeEnabled();
    await firstRecordButton.click();
    await expect(experimentPage.locator("#btn-record-play-recording")).toBeEnabled({
      timeout: 45000
    });
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expectPromptContains(
      experimentPage,
      "Here's the recording you just made.",
      STEP_TIMEOUT_MS
    );
    await expect(experimentPage.locator("video#prompt")).toHaveCount(0);
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expectPromptContains(
      experimentPage,
      "activate the recorder 3 seconds afterwards"
    );
    await expect(experimentPage.locator("#btn-record-record")).toBeEnabled();
    await expect(experimentPage.locator("#btn-record-play-recording")).toBeEnabled({
      timeout: 45000
    });
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expectPromptContains(
      experimentPage,
      "plays audio and records video after a couple of seconds"
    );
    const videoRecordButton = experimentPage.locator("#btn-record-record");
    await expect(videoRecordButton).toBeVisible();
    await expect(videoRecordButton).toBeEnabled();
    await videoRecordButton.click();
    await expectPromptContains(
      experimentPage,
      "Here's the recording you just made.",
      STEP_TIMEOUT_MS
    );
    await expect(experimentPage.locator("video#prompt")).toBeVisible();
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expectPromptContains(
      experimentPage,
      "default meter parameters are designed to work well for music playback"
    );
    await expect(experimentPage.locator("#audio-meter")).toBeVisible();
    await expect(experimentPage.locator("#audio-meter-sliders .slider-range")).toHaveCount(
      9
    );
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expectPromptContains(experimentPage, "TappingAudioMeterControl class");
    await expect(experimentPage.locator("#audio-meter")).toBeVisible();
    await expect(experimentPage.locator("#audio-meter-sliders .slider-range")).toHaveCount(
      9
    );
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expectMainBodyContains(experimentPage, "demonstrates audio preloading");
    const playBierButton = experimentPage.getByRole("button", {
      name: "Play 'bier'."
    });
    const stopBierButton = experimentPage.getByRole("button", {
      name: "Stop 'bier'."
    });
    await expect(playBierButton).toBeEnabled();
    await expect(stopBierButton).toBeEnabled();
    await playBierButton.click();
    await stopBierButton.click();

    await expect(experimentPage.locator("#Finish")).toBeVisible();
    await experimentPage.click("#Finish");
    await experimentPage.waitForURL(
      (url) => url.toString().includes("recruiter-exit"),
      { timeout: STEP_TIMEOUT_MS }
    );
  });
});
