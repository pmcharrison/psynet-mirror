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
- Calibration/setup: validate volume/microphone setup pages and meter visibility.
- Trial interaction: click explicit start button and verify trial enters recording flow.
- Progress states: assert recording/upload status captions appear in the UI.
- Recording artifact: verify staged audio blob exists and has non-zero size.
- Feedback page: exercise playback control and confirm continuation is enabled.
- End-to-end: finish remaining static trials.

Intentionally not covered:
- Every single static-trial node variant (this spec validates the representative flow).
- Acoustic quality/content analysis of recorded audio.
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

test("static_audio demo", async ({ page, context }) => {
  const absDir = path.resolve("demos/experiments/static_audio");
  await withExperiment(page, context, absDir, async (experimentPage) => {
    // Section 0: clear shared entry gateway page before timeline-specific assertions.
    await clearEntryGatewayPage(experimentPage);

    // Section 1: verify calibration pages and required meter UI.
    await expectMainBodyContains(experimentPage, "Please listen to the following sound");
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);
    await expectMainBodyContains(experimentPage, "Please speak into your microphone");
    await expect(experimentPage.locator("#audio-meter")).toBeVisible({
      timeout: PROMPT_TIMEOUT_MS
    });
    await waitForTrialEventCount(experimentPage, "responseEnable", 1, 45000);
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 2: verify info page content before entering the static-trial loop.
    await expectMainBodyContains(experimentPage, "repeat");
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 3: verify first static trial uses start button, records automatically, and submits.
    await expectPromptContains(experimentPage, "Please imitate the spoken word");
    const startButton = experimentPage.locator("#buttonStart");
    await expect(startButton).toBeVisible();
    await expect(startButton).toBeEnabled();
    await expect(experimentPage.locator("#next-button")).toHaveCount(0);
    const trialEventsBeforeStart = await getTrialEvents(experimentPage);
    expect(getEventTimes(trialEventsBeforeStart, "trialStart").length).toBe(0);
    await startButton.click();
    await waitForTrialEventCount(experimentPage, "trialStart", 1, 15000);
    await waitForTrialEventCount(experimentPage, "promptEnd", 1, 30000);
    await waitForTrialEventCount(experimentPage, "recordStart", 1, 30000);
    await expectMainBodyContains(experimentPage, "Recording...");
    await expectMainBodyContains(experimentPage, "Uploading, please wait...");
    const trialEvents = await getTrialEvents(experimentPage);
    assertEventDelayWithin(trialEvents, {
      fromEvent: "trialStart",
      toEvent: "promptEnd",
      minMs: 200,
      maxMs: 6000
    });
    assertEventDelayWithin(trialEvents, {
      fromEvent: "promptEnd",
      toEvent: "recordStart",
      minMs: 0,
      maxMs: 1500
    });
    const stagedAudio = await getStagedAudioRecordingInfo(experimentPage);
    expect(stagedAudio.exists).toBe(true);
    expect(stagedAudio.size).toBeGreaterThan(0);
    if (stagedAudio.type) {
      expect(stagedAudio.type).toContain("audio");
    }

    // Section 4: confirm auto-advance lands on feedback page and unlocks continuation.
    await expectPromptContains(experimentPage, "Listen back to your recording", STEP_TIMEOUT_MS);
    await expect(experimentPage.locator("#btn-record-record")).toHaveCount(0);
    const feedbackPageUuid = await experimentPage
      .evaluate(() => window.pageUuid || null)
      .catch(() => null);
    const feedbackPlayButton = experimentPage.locator("#audio-prompt-play");
    if ((await feedbackPlayButton.count()) > 0) {
      await expect(feedbackPlayButton).toBeVisible();
      await expect(feedbackPlayButton).toBeEnabled();
      await feedbackPlayButton.click();
    }
    await expect
      .poll(
        async () => {
          const nextEnabled = await experimentPage
            .locator("#next-button")
            .isEnabled()
            .catch(() => false);
          const pageChanged = feedbackPageUuid
            ? await experimentPage
                .evaluate((uuid) => window.pageUuid && window.pageUuid !== uuid, feedbackPageUuid)
                .catch(() => false)
            : false;
          return nextEnabled || pageChanged;
        },
        { timeout: STEP_TIMEOUT_MS }
      )
      .toBe(true);
    if (
      (await experimentPage.locator("#next-button").count()) > 0 &&
      (await experimentPage.locator("#next-button").isEnabled().catch(() => false))
    ) {
      await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);
    }

    // Section 5: finish remaining trials once core trial behavior is validated.
    await advanceUntilFinish(experimentPage);
  });
});
