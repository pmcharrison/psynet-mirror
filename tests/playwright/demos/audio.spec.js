const path = require("path");
const { test, expect } = require("@playwright/test");

const {
  clickNextAndWait,
  waitForNextEnabled,
  withExperiment
} = require("../psynetHarness");

const PROMPT_TIMEOUT_MS = 90000;
const STEP_TIMEOUT_MS = 120000;
const SNAPSHOT_OPTIONS = {
  animations: "disabled",
  caret: "hide",
  maxDiffPixelRatio: 0.02
};

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

async function getTrialEvents(page) {
  return page.evaluate(() => {
    return (psynet?.trial?.eventLog || []).map((event) => ({
      eventType: event.eventType,
      localTimeMs: new Date(event.localTime).getTime(),
      info: event.info ?? null
    }));
  });
}

function getEventTimes(events, eventType) {
  return events
    .filter((event) => event.eventType === eventType)
    .map((event) => event.localTimeMs);
}

function assertEventDelayWithin(
  events,
  {
    fromEvent,
    toEvent,
    minMs,
    maxMs,
    fromOccurrence = 0,
    toOccurrence = 0
  }
) {
  const fromTimes = getEventTimes(events, fromEvent);
  const toTimes = getEventTimes(events, toEvent);
  expect(fromTimes.length).toBeGreaterThan(fromOccurrence);
  expect(toTimes.length).toBeGreaterThan(toOccurrence);

  const delayMs = toTimes[toOccurrence] - fromTimes[fromOccurrence];
  expect(delayMs).toBeGreaterThanOrEqual(minMs);
  expect(delayMs).toBeLessThanOrEqual(maxMs);
}

async function waitForTrialEventCount(
  page,
  eventType,
  expectedCount,
  timeout = PROMPT_TIMEOUT_MS
) {
  await expect
    .poll(
      async () => {
        const events = await getTrialEvents(page);
        return getEventTimes(events, eventType).length;
      },
      { timeout }
    )
    .toBeGreaterThanOrEqual(expectedCount);
}

async function getActiveSoundIds(page) {
  return page.evaluate(() => {
    return (psynet?.media?.sounds || []).map((sound) => sound.stimulusId);
  });
}

async function waitForSoundActiveState(
  page,
  stimulusId,
  expectedActive,
  timeout = PROMPT_TIMEOUT_MS
) {
  await expect
    .poll(
      async () => {
        const activeSoundIds = await getActiveSoundIds(page);
        return activeSoundIds.includes(stimulusId);
      },
      { timeout }
    )
    .toBe(expectedActive);
}

async function useStandardAudioControls(page, options = {}) {
  const stopAfterPlay = options.stopAfterPlay ?? true;
  const toggleLoop = options.toggleLoop ?? false;
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

  if (toggleLoop) {
    const wasChecked = await loopToggle.isChecked();
    await loopToggle.click();
    if (wasChecked) {
      await expect(loopToggle).not.toBeChecked();
    } else {
      await expect(loopToggle).toBeChecked();
    }
  }
}

test("audio demo", async ({ page, context }) => {
  const absDir = path.resolve("demos/experiments/audio");
  await withExperiment(page, context, absDir, async (experimentPage) => {
    await expectPromptContains(
      experimentPage,
      "harmonic complex tone as the timbre"
    );
    await useStandardAudioControls(experimentPage, { toggleLoop: true });
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
    await expect(experimentPage.locator("#main-body")).toHaveScreenshot(
      "audio-slider-page.png",
      SNAPSHOT_OPTIONS
    );
    const sliderEventsBeforeInteraction = await getTrialEvents(experimentPage);
    const sliderChangeCountBefore = getEventTimes(
      sliderEventsBeforeInteraction,
      "sliderChange"
    ).length;
    const sliderSubmitEnableCountBefore = getEventTimes(
      sliderEventsBeforeInteraction,
      "submitEnable"
    ).length;
    const sliderValueBefore = Number(await slider.inputValue());
    await slider.focus();
    await experimentPage.keyboard.press("ArrowRight");
    await expect
      .poll(async () => Number(await slider.inputValue()), { timeout: 5000 })
      .not.toBe(sliderValueBefore);
    await waitForTrialEventCount(
      experimentPage,
      "sliderChange",
      sliderChangeCountBefore + 1,
      15000
    );
    await waitForTrialEventCount(
      experimentPage,
      "submitEnable",
      sliderSubmitEnableCountBefore + 1,
      30000
    );
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
    await waitForTrialEventCount(experimentPage, "audioFinished: prompt", 1, 30000);
    const simpleAudioEvents = await getTrialEvents(experimentPage);
    assertEventDelayWithin(simpleAudioEvents, {
      fromEvent: "trialStart",
      toEvent: "audioFinished: prompt",
      minMs: 100,
      maxMs: 20000
    });
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expectPromptContains(experimentPage, "loops the same stimulus");
    await waitForTrialEventCount(experimentPage, "audioFinished: prompt", 2, 45000);
    const loopingAudioEvents = await getTrialEvents(experimentPage);
    const loopingFinishTimes = getEventTimes(
      loopingAudioEvents,
      "audioFinished: prompt"
    );
    expect(loopingFinishTimes[1] - loopingFinishTimes[0]).toBeGreaterThanOrEqual(
      100
    );
    expect(loopingFinishTimes[1] - loopingFinishTimes[0]).toBeLessThanOrEqual(
      25000
    );
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expectPromptContains(experimentPage, "adds audio playback controls");
    await expect(experimentPage.locator("#next-button")).toBeDisabled();
    await expect(experimentPage.locator("#audio-prompt-controls")).toHaveScreenshot(
      "audio-controls-standard.png",
      SNAPSHOT_OPTIONS
    );
    const controlsEventsBeforePlay = await getTrialEvents(experimentPage);
    expect(getEventTimes(controlsEventsBeforePlay, "trialStart").length).toBe(0);
    await useStandardAudioControls(experimentPage, { stopAfterPlay: false });
    await waitForTrialEventCount(experimentPage, "trialStart", 1, 15000);
    await waitForTrialEventCount(experimentPage, "audioFinished: prompt", 1, 30000);
    const controlsAudioEvents = await getTrialEvents(experimentPage);
    assertEventDelayWithin(controlsAudioEvents, {
      fromEvent: "trialStart",
      toEvent: "audioFinished: prompt",
      minMs: 100,
      maxMs: 25000
    });
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
    await expect(experimentPage.locator("#audio-prompt-controls")).toHaveScreenshot(
      "audio-controls-play-again-only.png",
      SNAPSHOT_OPTIONS
    );
    await waitForTrialEventCount(experimentPage, "audioFinished: prompt", 1, 30000);
    const customControlEventsBeforeReplay = await getTrialEvents(experimentPage);
    const customFinishedCountBeforeReplay = getEventTimes(
      customControlEventsBeforeReplay,
      "audioFinished: prompt"
    ).length;
    await experimentPage.locator("#audio-prompt-play").click();
    await waitForTrialEventCount(
      experimentPage,
      "audioFinished: prompt",
      customFinishedCountBeforeReplay + 1,
      30000
    );
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expectPromptContains(
      experimentPage,
      "access audio stimuli outside of Audio Prompts"
    );
    await expect(experimentPage.locator("#audio-prompt-controls")).toHaveCount(0);
    await waitForTrialEventCount(experimentPage, "playStimulus1", 1, 15000);
    await waitForTrialEventCount(experimentPage, "audioFinished: stimulus_1", 1, 30000);
    await waitForTrialEventCount(experimentPage, "playStimulus2", 1, 15000);
    await waitForTrialEventCount(experimentPage, "responseEnable", 1, 15000);
    await waitForTrialEventCount(experimentPage, "submitEnable", 1, 15000);
    const sequenceEvents = await getTrialEvents(experimentPage);
    assertEventDelayWithin(sequenceEvents, {
      fromEvent: "trialStart",
      toEvent: "playStimulus1",
      minMs: 0,
      maxMs: 1500
    });
    assertEventDelayWithin(sequenceEvents, {
      fromEvent: "audioFinished: stimulus_1",
      toEvent: "playStimulus2",
      minMs: 100,
      maxMs: 2500
    });
    assertEventDelayWithin(sequenceEvents, {
      fromEvent: "playStimulus2",
      toEvent: "responseEnable",
      minMs: 700,
      maxMs: 3000
    });
    assertEventDelayWithin(sequenceEvents, {
      fromEvent: "responseEnable",
      toEvent: "submitEnable",
      minMs: 0,
      maxMs: 1000
    });
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
    const firstRecordEventsBefore = await getTrialEvents(experimentPage);
    const firstRecordEndCountBefore = getEventTimes(
      firstRecordEventsBefore,
      "recordEnd"
    ).length;
    await firstRecordButton.click();
    await waitForTrialEventCount(
      experimentPage,
      "recordEnd",
      firstRecordEndCountBefore + 1,
      45000
    );
    const firstRecordEvents = await getTrialEvents(experimentPage);
    const firstRecordTrialStarts = getEventTimes(firstRecordEvents, "trialStart");
    const firstRecordEnds = getEventTimes(firstRecordEvents, "recordEnd");
    expect(firstRecordTrialStarts.length).toBeGreaterThan(0);
    expect(firstRecordEnds.length).toBeGreaterThan(0);
    const firstRecordDurationMs =
      firstRecordEnds[firstRecordEnds.length - 1] -
      firstRecordTrialStarts[firstRecordTrialStarts.length - 1];
    expect(firstRecordDurationMs).toBeGreaterThanOrEqual(2000);
    expect(firstRecordDurationMs).toBeLessThanOrEqual(12000);
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
    await waitForTrialEventCount(experimentPage, "recordStart", 1, 45000);
    await waitForTrialEventCount(experimentPage, "recordEnd", 1, 45000);
    const listenThenRecordEvents = await getTrialEvents(experimentPage);
    assertEventDelayWithin(listenThenRecordEvents, {
      fromEvent: "trialStart",
      toEvent: "recordStart",
      minMs: 2200,
      maxMs: 7000
    });
    assertEventDelayWithin(listenThenRecordEvents, {
      fromEvent: "recordStart",
      toEvent: "recordEnd",
      minMs: 700,
      maxMs: 5000
    });
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
    const videoRecordEventsBefore = await getTrialEvents(experimentPage);
    expect(getEventTimes(videoRecordEventsBefore, "trialStart").length).toBe(0);
    await videoRecordButton.click();
    await waitForTrialEventCount(experimentPage, "trialStart", 1, 15000);
    await waitForTrialEventCount(experimentPage, "audioStart", 1, 15000);
    await waitForTrialEventCount(experimentPage, "recordStart", 1, 30000);
    const videoRecordEvents = await getTrialEvents(experimentPage);
    assertEventDelayWithin(videoRecordEvents, {
      fromEvent: "trialStart",
      toEvent: "audioStart",
      minMs: 0,
      maxMs: 1500
    });
    assertEventDelayWithin(videoRecordEvents, {
      fromEvent: "trialStart",
      toEvent: "recordStart",
      minMs: 1800,
      maxMs: 7000
    });
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
    const audioMeterCalibrationSliderCount = await experimentPage
      .locator("#audio-meter-sliders .slider-range")
      .count();
    expect(audioMeterCalibrationSliderCount).toBeGreaterThanOrEqual(9);
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expectPromptContains(experimentPage, "TappingAudioMeterControl class");
    await expect(experimentPage.locator("#audio-meter")).toBeVisible();
    const tappingCalibrationSliderCount = await experimentPage
      .locator("#audio-meter-sliders .slider-range")
      .count();
    expect(tappingCalibrationSliderCount).toBeGreaterThanOrEqual(9);
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
    await expect(experimentPage.locator("#main-body")).toHaveScreenshot(
      "audio-preloading-page.png",
      SNAPSHOT_OPTIONS
    );
    const preloadingEventsBefore = await getTrialEvents(experimentPage);
    const bierFinishedCountBefore = getEventTimes(
      preloadingEventsBefore,
      "audioFinished: bier"
    ).length;
    await playBierButton.click();
    await waitForSoundActiveState(experimentPage, "bier", true, 10000);
    await stopBierButton.click();
    await waitForTrialEventCount(
      experimentPage,
      "audioFinished: bier",
      bierFinishedCountBefore + 1,
      15000
    );
    await waitForSoundActiveState(experimentPage, "bier", false, 15000);

    const finishButton = experimentPage.locator("#Finish");
    const finishIsVisible =
      (await finishButton.count()) > 0 && (await finishButton.first().isVisible());
    if (!finishIsVisible) {
      await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);
    }
    await expect(finishButton).toBeVisible({ timeout: STEP_TIMEOUT_MS });
    await finishButton.first().click();
    await experimentPage.waitForURL(
      (url) => url.toString().includes("recruiter-exit"),
      { timeout: STEP_TIMEOUT_MS }
    );
  });
});
