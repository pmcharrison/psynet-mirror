const path = require("path");
const { test, expect } = require("@playwright/test");

const {
  advanceUntilPromptContains,
  advanceUntilFinish,
  clearEntryGatewayPage,
  clickNextAndWait,
  withExperiment
} = require("../psynetHarness");

const PROMPT_TIMEOUT_MS = 90000;
const STEP_TIMEOUT_MS = 120000;

/*
UI coverage checklist:
- Calibration: verify audio meter screen appears and enables response progression.
- Seed trial: validate recording UI, event timing, restart button behavior, and staged video blob.
- Non-seed trial: validate prompt video readiness, transition to record page, and progress captions.
- Recording controls: click record buttons directly and verify new recordStart/recordEnd events.
- End-to-end: complete remaining chain steps and finish cleanly.

Intentionally not covered:
- Node/chain statistical properties across many participants.
- Detailed gesture/video-content correctness beyond recording existence and timing.
*/

async function expectMainBodyContains(page, text, timeout = PROMPT_TIMEOUT_MS) {
  await expect(page.locator("#main-body")).toContainText(text, { timeout });
}

async function expectPromptContains(page, text, timeout = PROMPT_TIMEOUT_MS) {
  await expect(page.locator("#prompt-text")).toContainText(text, { timeout });
}

async function getTrialEvents(page) {
  return page.evaluate(() => {
    return (psynet?.trial?.eventLog || []).map((event) => ({
      eventType: event.eventType,
      localTimeMs: new Date(event.localTime).getTime()
    }));
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

async function getStagedCameraRecordingInfo(page) {
  return page.evaluate(() => {
    const blob = psynet?.response?.staged?.blobs?.cameraRecording || null;
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

test("imitation_chain_video demo", async ({ page, context }) => {
  const absDir = path.resolve("demos/experiments/imitation_chain_video");
  await withExperiment(page, context, absDir, async (experimentPage) => {
    // Section 0: clear shared entry gateway page before timeline-specific assertions.
    await clearEntryGatewayPage(experimentPage);

    // Section 1: verify microphone calibration UI is present and gates progression.
    await expectMainBodyContains(experimentPage, "Please speak into your microphone");
    await expect(experimentPage.locator("#audio-meter")).toBeVisible({
      timeout: PROMPT_TIMEOUT_MS
    });
    await waitForTrialEventCount(experimentPage, "responseEnable", 1, 45000);
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 2: verify actual webcam recording flow via UI and event-log timing.
    await expectPromptContains(experimentPage, "Please trace out a");
    await expect(experimentPage.locator("#video-control")).toBeVisible({
      timeout: PROMPT_TIMEOUT_MS
    });
    const recordButton = experimentPage.locator("#btn-record-record");
    const playRecordingButton = experimentPage.locator("#btn-record-play-recording");
    await expect(recordButton).toBeVisible();
    await expect(recordButton).toBeEnabled();

    // The recording trial can auto-start once the page is constructed.
    await waitForTrialEventCount(experimentPage, "trialStart", 1, 15000);
    await waitForTrialEventCount(experimentPage, "recordStart", 1, 30000);
    await waitForTrialEventCount(experimentPage, "recordEnd", 1, 45000);
    await waitForTrialEventCount(experimentPage, "submitEnable", 1, 45000);
    const recordingEvents = await getTrialEvents(experimentPage);
    assertEventDelayWithin(recordingEvents, {
      fromEvent: "trialStart",
      toEvent: "recordStart",
      minMs: 900,
      maxMs: 7000
    });
    assertEventDelayWithin(recordingEvents, {
      fromEvent: "recordStart",
      toEvent: "recordEnd",
      minMs: 4000,
      maxMs: 10000
    });
    await expect(playRecordingButton).toBeEnabled({ timeout: 45000 });
    const stagedRecording = await getStagedCameraRecordingInfo(experimentPage);
    expect(stagedRecording.exists).toBe(true);
    expect(stagedRecording.size).toBeGreaterThan(0);
    if (stagedRecording.type) {
      expect(stagedRecording.type).toContain("video");
    }

    // Verify click registration by restarting the recording through the UI.
    const recordStartsBeforeRestart = getEventTimes(recordingEvents, "recordStart").length;
    const recordEndsBeforeRestart = getEventTimes(recordingEvents, "recordEnd").length;
    await recordButton.click();
    await waitForTrialEventCount(
      experimentPage,
      "recordStart",
      recordStartsBeforeRestart + 1,
      30000
    );
    await waitForTrialEventCount(
      experimentPage,
      "recordEnd",
      recordEndsBeforeRestart + 1,
      45000
    );
    const recordingEventsAfterRestart = await getTrialEvents(experimentPage);
    const restartStartTimes = getEventTimes(recordingEventsAfterRestart, "recordStart");
    const restartEndTimes = getEventTimes(recordingEventsAfterRestart, "recordEnd");
    expect(restartStartTimes.length).toBeGreaterThan(recordStartsBeforeRestart);
    expect(restartEndTimes.length).toBeGreaterThan(recordEndsBeforeRestart);
    const restartedDurationMs =
      restartEndTimes[recordEndsBeforeRestart] - restartStartTimes[recordStartsBeforeRestart];
    expect(restartedDurationMs).toBeGreaterThanOrEqual(4000);
    expect(restartedDurationMs).toBeLessThanOrEqual(10000);

    await expect(experimentPage.locator("#next-button")).toBeEnabled({
      timeout: STEP_TIMEOUT_MS
    });
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 3: verify a non-seed trial prompt/record sequence also exercises real UI.
    await advanceUntilPromptContains(
      experimentPage,
      "When you are ready, press next to imitate the figure that you see."
    );
    await expectVideoPromptReady(experimentPage);
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    await expect(experimentPage.locator("#video-control")).toBeVisible({
      timeout: PROMPT_TIMEOUT_MS
    });
    await expectMainBodyContains(experimentPage, "Get ready...");
    await expectMainBodyContains(experimentPage, "Make your gesture!");
    await expectMainBodyContains(
      experimentPage,
      "Click 'Next' if you're happy with your recording."
    );
    const nonSeedRecordButton = experimentPage.locator("#btn-record-record");
    await expect(nonSeedRecordButton).toBeVisible();
    await expect(nonSeedRecordButton).toBeEnabled();
    const nonSeedEventsBefore = await getTrialEvents(experimentPage);
    const nonSeedStartsBefore = getEventTimes(nonSeedEventsBefore, "recordStart").length;
    const nonSeedEndsBefore = getEventTimes(nonSeedEventsBefore, "recordEnd").length;
    await nonSeedRecordButton.click();
    await waitForTrialEventCount(
      experimentPage,
      "recordStart",
      nonSeedStartsBefore + 1,
      30000
    );
    await waitForTrialEventCount(
      experimentPage,
      "recordEnd",
      nonSeedEndsBefore + 1,
      45000
    );
    const nonSeedStagedRecording = await getStagedCameraRecordingInfo(experimentPage);
    expect(nonSeedStagedRecording.exists).toBe(true);
    expect(nonSeedStagedRecording.size).toBeGreaterThan(0);
    if (nonSeedStagedRecording.type) {
      expect(nonSeedStagedRecording.type).toContain("video");
    }
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 4: complete remaining trials after verifying core interaction and logging behavior.
    await advanceUntilFinish(experimentPage);
  });
});
