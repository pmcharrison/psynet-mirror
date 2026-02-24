const path = require("path");
const { test, expect } = require("@playwright/test");

const {
  advanceUntilFinish,
  clearEntryGatewayPage,
  clickNextAndWait,
  withExperiment
} = require("../psynetHarness");

const PROMPT_TIMEOUT_MS = 90000;
const STEP_TIMEOUT_MS = 120000;

/*
UI coverage checklist:
- Prompt media readiness: verify video prompt source/duration is loaded before progressing.
- AV sync pages: assert soundtrack trigger events where video+audio pages are expected.
- Audio recording page: click record/play controls, verify event timing, and staged audio blob.
- Video recording page: validate countdown captions, recording state, and staged camera blob.
- Dual-source recording: verify both camera and screen blobs exist and can be replayed.
- Playback page: ensure final video prompt renders with load-ready media.
- End-to-end: finish remaining timeline steps.

Intentionally not covered:
- Exact audiovisual synchronization at sub-frame precision.
- Binary equality of captured camera/screen recordings.
*/

async function expectPromptContains(page, text, timeout = PROMPT_TIMEOUT_MS) {
  await expect(page.locator("#prompt-text")).toContainText(text, { timeout });
}

async function expectMainBodyContains(page, text, timeout = PROMPT_TIMEOUT_MS) {
  await expect(page.locator("#main-body")).toContainText(text, { timeout });
}

async function getTrialEvents(page) {
  return page.evaluate(() => {
    return (psynet?.trial?.eventLog || []).map((event) => ({
      eventType: event.eventType,
      localTimeMs: new Date(event.localTime).getTime()
    }));
  });
}

async function getActiveSoundIds(page) {
  return page.evaluate(() => {
    return (psynet?.media?.sounds || []).map((sound) => sound.stimulusId);
  });
}

async function getStagedAudioRecordingInfo(page) {
  return page.evaluate(() => {
    const blob = psynet?.response?.staged?.blobs?.audioRecording || null;
    if (!blob) {
      return { exists: false, size: 0, type: null };
    }
    return {
      exists: true,
      size: typeof blob.size === "number" ? blob.size : 0,
      type: typeof blob.type === "string" ? blob.type : null
    };
  });
}

function getEventTimes(events, eventType) {
  return events
    .filter((event) => event.eventType === eventType)
    .map((event) => event.localTimeMs);
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

async function getStagedVideoRecordingInfo(page) {
  return page.evaluate(() => {
    const cameraBlob = psynet?.response?.staged?.blobs?.cameraRecording || null;
    const screenBlob = psynet?.response?.staged?.blobs?.screenRecording || null;
    return {
      cameraExists: !!cameraBlob,
      cameraSize: cameraBlob && typeof cameraBlob.size === "number" ? cameraBlob.size : 0,
      cameraType: cameraBlob && typeof cameraBlob.type === "string" ? cameraBlob.type : null,
      screenExists: !!screenBlob,
      screenSize: screenBlob && typeof screenBlob.size === "number" ? screenBlob.size : 0,
      screenType: screenBlob && typeof screenBlob.type === "string" ? screenBlob.type : null
    };
  });
}

async function expectVideoPromptReady(page, timeout = PROMPT_TIMEOUT_MS) {
  const videoPrompt = page.locator("video#prompt");
  await expect(videoPrompt).toBeVisible({ timeout });
  await expect
    .poll(
      () =>
        videoPrompt.evaluate((video) => ({
          hasSource: Boolean(video.currentSrc),
          hasDuration: Number(video.duration) > 0
        })),
      { timeout }
    )
    .toMatchObject({ hasSource: true, hasDuration: true });
}

test("video feature demo", async ({ page, context }) => {
  const absDir = path.resolve("demos/features/video");
  await withExperiment(page, context, absDir, async (experimentPage) => {
    // Section 0: clear shared entry gateway page before timeline-specific assertions.
    await clearEntryGatewayPage(experimentPage);

    // Section 1: validate first prompt page renders video.
    await expectVideoPromptReady(experimentPage);
    await expectPromptContains(experimentPage, "Example video prompt");
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 2: verify subsequent prompt pages still render expected video/audio UI.
    await expectPromptContains(experimentPage, "play window");
    await expectVideoPromptReady(experimentPage);
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expectPromptContains(experimentPage, "video, muted, alongside an audio file");
    await expectVideoPromptReady(experimentPage);
    await waitForTrialEventCount(experimentPage, "playSoundtrack", 1, 15000);
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expectPromptContains(experimentPage, "well-synchronized");
    await expectVideoPromptReady(experimentPage);
    await waitForTrialEventCount(experimentPage, "playSoundtrack", 1, 15000);
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 3: validate audio-recording-on-video page by exercising record controls and events.
    await expectPromptContains(
      experimentPage,
      "record an audio response",
      PROMPT_TIMEOUT_MS
    );
    const audioRecordButton = experimentPage.locator("#btn-record-record");
    const audioPlayRecordingButton = experimentPage.locator(
      "#btn-record-play-recording"
    );
    await expect(audioRecordButton).toBeVisible();
    await expect(audioRecordButton).toBeEnabled();
    await audioRecordButton.click();
    await waitForTrialEventCount(experimentPage, "trialStart", 1, 15000);
    await waitForTrialEventCount(experimentPage, "recordStart", 1, 30000);
    await waitForTrialEventCount(experimentPage, "recordEnd", 1, 45000);
    await waitForTrialEventCount(experimentPage, "submitEnable", 1, 45000);
    await waitForTrialEventCount(experimentPage, "playSoundtrack", 1, 15000);
    await waitForTrialEventCount(experimentPage, "stopSoundtrack", 1, 15000);
    const audioRecordEvents = await getTrialEvents(experimentPage);
    assertEventDelayWithin(audioRecordEvents, {
      fromEvent: "recordStart",
      toEvent: "recordEnd",
      minMs: 2500,
      maxMs: 9000
    });
    await expect(audioPlayRecordingButton).toBeEnabled({ timeout: 45000 });
    const audioRecordingBlob = await getStagedAudioRecordingInfo(experimentPage);
    expect(audioRecordingBlob.exists).toBe(true);
    expect(audioRecordingBlob.size).toBeGreaterThan(0);
    if (audioRecordingBlob.type) {
      expect(audioRecordingBlob.type).toContain("audio");
    }
    const activeSoundsBeforeAudioPlayback = await getActiveSoundIds(experimentPage);
    await audioPlayRecordingButton.click();
    await expect
      .poll(
        async () => {
          const activeSoundsAfterAudioPlayback = await getActiveSoundIds(experimentPage);
          return activeSoundsAfterAudioPlayback.length;
        },
        { timeout: 10000 }
      )
      .toBeGreaterThan(activeSoundsBeforeAudioPlayback.length);
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 4: validate delayed video recording page timing and staged camera blob.
    await expectPromptContains(
      experimentPage,
      "record a video response after a countdown",
      PROMPT_TIMEOUT_MS
    );
    const videoRecordButton = experimentPage.locator("#btn-record-record");
    await expect(videoRecordButton).toBeVisible();
    await expect(videoRecordButton).toBeEnabled();
    const firstVideoEvents = await getTrialEvents(experimentPage);
    const startsBefore = getEventTimes(firstVideoEvents, "recordStart").length;
    const endsBefore = getEventTimes(firstVideoEvents, "recordEnd").length;
    await videoRecordButton.click();
    await expectMainBodyContains(experimentPage, "Recording in 3 seconds...");
    await expectMainBodyContains(experimentPage, "Recording in 2 seconds...");
    await expectMainBodyContains(experimentPage, "Recording in 1 seconds...");
    await expectMainBodyContains(experimentPage, "Recording!");
    await waitForTrialEventCount(
      experimentPage,
      "recordStart",
      startsBefore + 1,
      30000
    );
    await waitForTrialEventCount(
      experimentPage,
      "recordEnd",
      endsBefore + 1,
      45000
    );
    const videoEventsAfterClick = await getTrialEvents(experimentPage);
    const trialStartsBefore = getEventTimes(firstVideoEvents, "trialStart").length;
    assertEventDelayWithin(videoEventsAfterClick, {
      fromEvent: "trialStart",
      toEvent: "recordStart",
      minMs: 2000,
      maxMs: 8000,
      fromOccurrence: trialStartsBefore,
      toOccurrence: startsBefore
    });
    const singleVideoRecording = await getStagedVideoRecordingInfo(experimentPage);
    expect(singleVideoRecording.cameraExists).toBe(true);
    expect(singleVideoRecording.cameraSize).toBeGreaterThan(0);
    if (singleVideoRecording.cameraType) {
      expect(singleVideoRecording.cameraType).toContain("video");
    }
    const videoPlayRecordingButton = experimentPage.locator(
      "#btn-record-play-recording"
    );
    await expect(videoPlayRecordingButton).toBeEnabled({ timeout: 45000 });
    await videoPlayRecordingButton.click();
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 5: validate dual-source recording stores both camera and screen blobs.
    await expectMainBodyContains(
      experimentPage,
      "simultaneous screen recording",
      PROMPT_TIMEOUT_MS
    );
    const dualRecordButton = experimentPage.locator("#btn-record-record");
    await expect(dualRecordButton).toBeVisible();
    await expect(dualRecordButton).toBeEnabled();
    const dualEventsBefore = await getTrialEvents(experimentPage);
    const dualStartsBefore = getEventTimes(dualEventsBefore, "recordStart").length;
    const dualEndsBefore = getEventTimes(dualEventsBefore, "recordEnd").length;
    await dualRecordButton.click();
    await waitForTrialEventCount(
      experimentPage,
      "recordStart",
      dualStartsBefore + 1,
      30000
    );
    await waitForTrialEventCount(
      experimentPage,
      "recordEnd",
      dualEndsBefore + 1,
      60000
    );
    const dualRecording = await getStagedVideoRecordingInfo(experimentPage);
    expect(dualRecording.cameraExists).toBe(true);
    expect(dualRecording.cameraSize).toBeGreaterThan(0);
    expect(dualRecording.screenExists).toBe(true);
    expect(dualRecording.screenSize).toBeGreaterThan(0);
    const dualPlayRecordingButton = experimentPage.locator(
      "#btn-record-play-recording"
    );
    await expect(dualPlayRecordingButton).toBeEnabled({ timeout: 45000 });
    await dualPlayRecordingButton.click();
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 6: ensure playback page appears and finish remaining timeline safely.
    await expectMainBodyContains(experimentPage, "camera recording", STEP_TIMEOUT_MS);
    await expectVideoPromptReady(experimentPage, STEP_TIMEOUT_MS);
    await advanceUntilFinish(experimentPage);
  });
});
