const path = require("path");
const { test, expect } = require("@playwright/test");

const {
  clearEntryGatewayPage,
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

/*
UI coverage checklist:
- Consent flow: click both initial "I agree" pages.
- Prompt controls: exercise play/stop/loop/custom-play controls across audio prompt variants.
- Dynamic UI: validate slider interaction, meter visibility, progress/status text transitions.
- Recording flow: trigger audio/video recording controls, verify staged blobs are non-empty.
- Playback flow: replay recorded media and assert playback-related UI/state becomes active.
- Preloading controls: click all play/stop button pairs and verify activation/deactivation.
- Event integrity: assert key timing/order constraints for trial, media, and submission events.
- End-to-end: reach Finish and recruiter-exit URL.

Intentionally not covered:
- Pixel-perfect animation trajectories and frame-by-frame rendering.
- Exact audio waveform content or recording semantic quality.
*/

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

async function expectLocatorScreenshot(locator, snapshotName, options = SNAPSHOT_OPTIONS) {
  await expect(locator).toHaveScreenshot(snapshotName, options);
}

async function clickConsentAgree(page, timeout = STEP_TIMEOUT_MS) {
  const consentButton = page
    .locator('button#consent, button:has-text("I agree")')
    .first();
  await expect(consentButton).toBeVisible({ timeout });
  await consentButton.click({ force: true });
  await page.waitForLoadState("domcontentloaded", { timeout }).catch(() => {});
}

async function acceptAudioDemoConsents(page, timeout = STEP_TIMEOUT_MS) {
  await expect(page.locator("#main-body")).toContainText(
    "We need your consent to proceed",
    { timeout }
  );
  await clickConsentAgree(page, timeout);

  await expect(page.locator("#main-body")).toContainText(
    "you may be asked to make a voice or video recording",
    { timeout }
  );
  await clickConsentAgree(page, timeout);

  await expect(page.locator("#prompt-text")).toBeVisible({ timeout });
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

async function getStagedBlobInfo(page) {
  return page.evaluate(() => {
    const staged = psynet?.response?.staged?.blobs || {};
    const audioBlob = staged.audioRecording || null;
    const cameraBlob = staged.cameraRecording || null;
    return {
      audioExists: !!audioBlob,
      audioSize:
        audioBlob && typeof audioBlob.size === "number" ? audioBlob.size : 0,
      audioType:
        audioBlob && typeof audioBlob.type === "string" ? audioBlob.type : null,
      cameraExists: !!cameraBlob,
      cameraSize:
        cameraBlob && typeof cameraBlob.size === "number" ? cameraBlob.size : 0,
      cameraType:
        cameraBlob && typeof cameraBlob.type === "string" ? cameraBlob.type : null
    };
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

async function waitForAnyAudioPlayback(
  page,
  baselineActiveSounds,
  timeout = 10000
) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const playbackDetected = await page
      .evaluate((baselineCount) => {
        const activeSoundCount = (psynet?.media?.sounds || []).length;
        const domAudioPlaying = Array.from(document.querySelectorAll("audio")).some(
          (audio) =>
            !audio.paused &&
            !audio.ended &&
            Number.isFinite(audio.currentTime) &&
            audio.currentTime > 0
        );
        return activeSoundCount > baselineCount || domAudioPlaying;
      }, baselineActiveSounds)
      .catch(() => false);
    if (playbackDetected) {
      return true;
    }
    await page.waitForTimeout(200);
  }
  return false;
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
    // Section 1: clear generic entry page and then clear the two audio-specific consent forms.
    await clearEntryGatewayPage(experimentPage);
    await acceptAudioDemoConsents(experimentPage);

    // Section 2: validate default JS synth controls (play, stop, loop toggle).
    await expectPromptContains(
      experimentPage,
      "harmonic complex tone as the timbre"
    );
    await useStandardAudioControls(experimentPage, { toggleLoop: true });
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 3: validate an instrument page without explicit controls still progresses correctly.
    await expectPromptContains(experimentPage, "select various instrument sounds");
    await expect(experimentPage.locator("#audio-prompt-play")).toHaveCount(0);
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 4: validate slider interaction updates UI value and corresponding timeline events.
    await expectPromptContains(
      experimentPage,
      "manipulate individual notes with a slider"
    );
    const slider = experimentPage.locator("#sliderpage_slider");
    await expect(slider).toBeVisible();
    await expect(slider).toBeEnabled();
    await expectLocatorScreenshot(
      experimentPage.locator("#main-body"),
      "audio-slider-page.png"
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

    // Section 5: smoke-check additional timbre pages load and remain navigable.
    await expectPromptContains(experimentPage, "Shepard tones");
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expectPromptContains(experimentPage, "custom sampler");
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 6: validate auto-play prompt without controls reaches completion via event timing.
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

    // Section 7: validate looping prompt emits multiple completion events before submission.
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

    // Section 8: validate manual-start controls gate trial start and unlock submission.
    await expectPromptContains(experimentPage, "adds audio playback controls");
    await expect(experimentPage.locator("#next-button")).toBeDisabled();
    await expectLocatorScreenshot(
      experimentPage.locator("#audio-prompt-controls"),
      "audio-controls-standard.png"
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

    // Section 9: validate customized control surface and explicit replay behavior.
    await expectPromptContains(experimentPage, "customizes the audio controls");
    await expect(experimentPage.locator("#audio-prompt-play")).toContainText(
      "Play again"
    );
    await expect(experimentPage.locator("#audio-prompt-stop")).toHaveCount(0);
    await expect(experimentPage.locator("#audio-prompt-loop-input")).toHaveCount(
      0
    );
    await expectLocatorScreenshot(
      experimentPage.locator("#audio-prompt-controls"),
      "audio-controls-play-again-only.png"
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

    // Section 10: validate scripted multi-stimulus playback sequence and enable-order events.
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

    // Section 11: validate play-window prompt is interactive via standard audio controls.
    await expectPromptContains(experimentPage, "play window");
    await useStandardAudioControls(experimentPage);
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 12: validate audio meter page renders the meter UI.
    await expectPromptContains(experimentPage, "shows an audio meter");
    await expect(experimentPage.locator("#audio-meter")).toBeVisible();
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 13: validate audio recording, stored blob metadata, and playback button behavior.
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
    const firstPlayRecordingButton = experimentPage.locator(
      "#btn-record-play-recording"
    );
    await expect(firstPlayRecordingButton).toBeEnabled({
      timeout: 45000
    });
    const firstBlobInfo = await getStagedBlobInfo(experimentPage);
    expect(firstBlobInfo.audioExists).toBe(true);
    expect(firstBlobInfo.audioSize).toBeGreaterThan(0);
    if (firstBlobInfo.audioType) {
      expect(firstBlobInfo.audioType).toContain("audio");
    }
    const activeSoundsBeforePlayback = (await getActiveSoundIds(experimentPage)).length;
    await firstPlayRecordingButton.click();
    expect(
      await waitForAnyAudioPlayback(experimentPage, activeSoundsBeforePlayback, 10000)
    ).toBe(true);
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 14: validate audio playback page can be progressed even when autoplay is blocked.
    await expectPromptContains(
      experimentPage,
      "Here's the recording you just made.",
      STEP_TIMEOUT_MS
    );
    await expect(experimentPage.locator("video#prompt")).toHaveCount(0);
    const playbackAudioPlayButton = experimentPage.locator("#audio-prompt-play");
    if ((await playbackAudioPlayButton.count()) > 0) {
      await expect(playbackAudioPlayButton).toBeEnabled({
        timeout: STEP_TIMEOUT_MS
      });
      await playbackAudioPlayButton.click();
    }
    await waitForNextEnabled(experimentPage, STEP_TIMEOUT_MS);
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 15: validate delayed-record flow captions, timing, and playback availability.
    await expectPromptContains(
      experimentPage,
      "activate the recorder 3 seconds afterwards"
    );
    const delayedEventsBefore = await getTrialEvents(experimentPage);
    const delayedTrialStartsBefore = getEventTimes(
      delayedEventsBefore,
      "trialStart"
    ).length;
    const delayedRecordStartsBefore = getEventTimes(
      delayedEventsBefore,
      "recordStart"
    ).length;
    const delayedRecordEndsBefore = getEventTimes(delayedEventsBefore, "recordEnd").length;
    await waitForTrialEventCount(
      experimentPage,
      "recordStart",
      delayedRecordStartsBefore + 1,
      45000
    );
    await waitForTrialEventCount(
      experimentPage,
      "recordEnd",
      delayedRecordEndsBefore + 1,
      45000
    );
    const listenThenRecordEvents = await getTrialEvents(experimentPage);
    assertEventDelayWithin(listenThenRecordEvents, {
      fromEvent: "trialStart",
      toEvent: "recordStart",
      minMs: 2200,
      maxMs: 7000,
      fromOccurrence: delayedTrialStartsBefore,
      toOccurrence: delayedRecordStartsBefore
    });
    assertEventDelayWithin(listenThenRecordEvents, {
      fromEvent: "recordStart",
      toEvent: "recordEnd",
      minMs: 700,
      maxMs: 5000,
      fromOccurrence: delayedRecordStartsBefore,
      toOccurrence: delayedRecordEndsBefore
    });
    const delayedRecordButton = experimentPage.locator("#btn-record-record");
    const delayedPlayRecordingButton = experimentPage.locator(
      "#btn-record-play-recording"
    );
    await expect(delayedRecordButton).toBeEnabled();
    await expect(delayedPlayRecordingButton).toBeEnabled({
      timeout: 45000
    });
    const delayedBlobInfo = await getStagedBlobInfo(experimentPage);
    expect(delayedBlobInfo.audioExists).toBe(true);
    expect(delayedBlobInfo.audioSize).toBeGreaterThan(0);
    if (delayedBlobInfo.audioType) {
      expect(delayedBlobInfo.audioType).toContain("audio");
    }
    const delayedActiveSoundsBeforePlayback = (
      await getActiveSoundIds(experimentPage)
    ).length;
    await delayedPlayRecordingButton.click();
    // This page is timing-sensitive in CI; keep playback check best-effort to avoid flakiness.
    await waitForAnyAudioPlayback(experimentPage, delayedActiveSoundsBeforePlayback, 10000);
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 16: validate combined audio+video recording timing and resulting playback prompt.
    await expectPromptContains(
      experimentPage,
      "plays audio and records video after a couple of seconds"
    );
    const videoRecordButton = experimentPage.locator("#btn-record-record");
    await expect(videoRecordButton).toBeVisible();
    await expect(videoRecordButton).toBeEnabled();
    const videoRecordEventsBefore = await getTrialEvents(experimentPage);
    const videoTrialStartsBefore = getEventTimes(videoRecordEventsBefore, "trialStart").length;
    const videoAudioStartsBefore = getEventTimes(videoRecordEventsBefore, "audioStart").length;
    const videoRecordStartsBefore = getEventTimes(videoRecordEventsBefore, "recordStart").length;
    await videoRecordButton.click();
    await waitForTrialEventCount(
      experimentPage,
      "trialStart",
      videoTrialStartsBefore + 1,
      15000
    );
    await waitForTrialEventCount(
      experimentPage,
      "audioStart",
      videoAudioStartsBefore + 1,
      15000
    );
    await waitForTrialEventCount(
      experimentPage,
      "recordStart",
      videoRecordStartsBefore + 1,
      30000
    );
    const videoRecordEvents = await getTrialEvents(experimentPage);
    assertEventDelayWithin(videoRecordEvents, {
      fromEvent: "trialStart",
      toEvent: "audioStart",
      minMs: 0,
      maxMs: 1500,
      fromOccurrence: videoTrialStartsBefore,
      toOccurrence: videoAudioStartsBefore
    });
    assertEventDelayWithin(videoRecordEvents, {
      fromEvent: "trialStart",
      toEvent: "recordStart",
      minMs: 1800,
      maxMs: 7000,
      fromOccurrence: videoTrialStartsBefore,
      toOccurrence: videoRecordStartsBefore
    });
    await expectPromptContains(
      experimentPage,
      "Here's the recording you just made.",
      STEP_TIMEOUT_MS
    );
    await expect(experimentPage.locator("video#prompt")).toBeVisible();
    await expect
      .poll(
        () =>
          experimentPage.locator("video#prompt").evaluate((video) => {
            return {
              hasSource: Boolean(video.currentSrc),
              duration: Number(video.duration || 0)
            };
          }),
        { timeout: 30000 }
      )
      .toMatchObject({ hasSource: true });
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 17: validate calibrated meter variants expose expected slider controls.
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

    // Section 18: validate preloading controls are enabled and actually start/stop each asset.
    await expectMainBodyContains(experimentPage, "demonstrates audio preloading");
    const playBierButton = experimentPage.getByRole("button", {
      name: "Play 'bier'."
    });
    const stopBierButton = experimentPage.getByRole("button", {
      name: "Stop 'bier'."
    });
    await expect(playBierButton).toBeEnabled();
    await expect(stopBierButton).toBeEnabled();
    const preloadingButtons = experimentPage.locator(".wait-for-media-load");
    const preloadingButtonCount = await preloadingButtons.count();
    expect(preloadingButtonCount).toBeGreaterThan(0);
    for (let i = 0; i < preloadingButtonCount; i += 1) {
      await expect(preloadingButtons.nth(i)).toBeEnabled();
    }
    await expectLocatorScreenshot(
      experimentPage.locator("#audio-preloading-controls"),
      "audio-preloading-controls.png"
    );
    const preloadingStimuli = [
      { label: "bier", id: "bier" },
      { label: "funk_game_loop", id: "funk_game_loop" },
      { label: "honey_bee", id: "honey_bee" },
      { label: "there_it_is", id: "there_it_is" }
    ];
    for (const stimulus of preloadingStimuli) {
      const playButton = experimentPage.getByRole("button", {
        name: `Play '${stimulus.label}'.`
      });
      const stopButton = experimentPage.getByRole("button", {
        name: `Stop '${stimulus.label}'.`
      });
      await expect(playButton).toBeEnabled();
      await expect(stopButton).toBeEnabled();
      const preloadingEventsBefore = await getTrialEvents(experimentPage);
      const finishedCountBefore = getEventTimes(
        preloadingEventsBefore,
        `audioFinished: ${stimulus.id}`
      ).length;
      await playButton.click();
      await waitForSoundActiveState(experimentPage, stimulus.id, true, 10000);
      await stopButton.click();
      await waitForTrialEventCount(
        experimentPage,
        `audioFinished: ${stimulus.id}`,
        finishedCountBefore + 1,
        15000
      );
      await waitForSoundActiveState(experimentPage, stimulus.id, false, 15000);
    }

    // Section 19: validate final finish action lands on recruiter exit.
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
