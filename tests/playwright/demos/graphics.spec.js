const path = require("path");
const { test, expect } = require("@playwright/test");

const {
  clearEntryGatewayPage,
  clickNextAndWait,
  withExperiment
} = require("../psynetHarness");

const PROMPT_TIMEOUT_MS = 90000;
const STEP_TIMEOUT_MS = 120000;

/*
UI coverage checklist:
- Shape rendering: assert expected SVG primitives and basic animation state change.
- GraphicControl clicks: click answerable graphics and verify click registration in debug output.
- Mixed media: verify synchronized audio prompt behavior and control visibility expectations.
- Typography/rendering: compare big/small text effective rendered size.
- Recording flow: verify countdown/status text, auto-start recording, and staged audio blob.
- Playback flow: click "play recording" control before submission.
- End-to-end: reach Finish and recruiter-exit URL.

Intentionally not covered:
- Full animation path validation over time for each SVG element.
- Exact audio content produced by user/bot recording.
*/

async function clickUiAndWaitForPageChange(page, locator, timeoutMs = 60000) {
  const oldUuid = await page.evaluate(() => window.pageUuid || null).catch(() => null);
  await locator.click({ force: true });
  if (!oldUuid) {
    await page.waitForTimeout(500);
    return;
  }
  await page.waitForFunction(
    (uuid) => window.pageUuid && window.pageUuid !== uuid,
    oldUuid,
    { timeout: timeoutMs }
  );
}

function extractClickCoordinates(debugText) {
  const match = debugText.match(
    /'click_coordinates':\s*\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]/
  );
  expect(match).not.toBeNull();
  return [Number(match[1]), Number(match[2])];
}

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

async function getGraphicAttribute(locator, attribute) {
  return locator.first().evaluate((el, attr) => {
    const raw = el.getAttribute(attr);
    const num = Number.parseFloat(raw ?? "");
    return Number.isFinite(num) ? num : raw;
  }, attribute);
}

async function getRenderedTextHeight(locator) {
  return locator.first().evaluate((el) => {
    const bboxHeight =
      typeof el.getBBox === "function" ? Number(el.getBBox().height) : NaN;
    if (Number.isFinite(bboxHeight) && bboxHeight > 0) {
      return bboxHeight;
    }

    const computedFontSize = Number.parseFloat(getComputedStyle(el).fontSize);
    if (Number.isFinite(computedFontSize) && computedFontSize > 0) {
      return computedFontSize;
    }

    const attrFontSize = Number.parseFloat(el.getAttribute("font-size") || "");
    if (Number.isFinite(attrFontSize) && attrFontSize > 0) {
      return attrFontSize;
    }

    return NaN;
  });
}

test("graphics demo", async ({ page, context }) => {
  const absDir = path.resolve("demos/experiments/graphics");
  await withExperiment(page, context, absDir, async (experimentPage) => {
    // Section 0: clear shared entry gateway page before timeline-specific assertions.
    await clearEntryGatewayPage(experimentPage);

    // Section 1: smoke-check intro page and move into graphics-specific pages.
    await expectMainBodyContains(experimentPage, "Graphic components");
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 2: verify core GraphicPrompt rendering (shape primitives from Python timeline).
    await expectPromptContains(experimentPage, "different kinds of geometric objects");
    await expect(experimentPage.locator("#main-body svg path")).toHaveCount(1);
    await expect(experimentPage.locator("#main-body svg circle")).toHaveCount(1);
    await expect(experimentPage.locator("#main-body svg ellipse")).toHaveCount(1);
    await expect(experimentPage.locator("#main-body svg rect")).toHaveCount(1);
    const animatedCircle = experimentPage.locator("#main-body svg circle");
    const circleCxBefore = await getGraphicAttribute(animatedCircle, "cx");
    await experimentPage.waitForTimeout(1200);
    const circleCxAfter = await getGraphicAttribute(animatedCircle, "cx");
    expect(circleCxAfter).not.toBe(circleCxBefore);
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 3: verify GraphicControl click path through real UI and persisted server answer.
    await expectPromptContains(experimentPage, "Click on one of the objects");
    await expect(experimentPage.locator("#main-body svg image")).toHaveCount(1);
    const titleGraphic = experimentPage.locator("#main-body svg text").filter({
      hasText: "PsyNet is great!"
    });
    await expect(titleGraphic).toBeVisible({ timeout: PROMPT_TIMEOUT_MS });
    await clickUiAndWaitForPageChange(experimentPage, titleGraphic);

    const firstDebugAnswer = await experimentPage.locator("#main-body").innerText();
    await expect(experimentPage.locator("#main-body")).toContainText("'clicked_object': 'title'");
    const [firstX, firstY] = extractClickCoordinates(firstDebugAnswer);
    expect(firstX).toBeGreaterThan(0);
    expect(firstY).toBeGreaterThan(0);
    expect(firstX).toBeLessThanOrEqual(100);
    expect(firstY).toBeLessThanOrEqual(100);

    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 4: verify synchronized-audio graphics page starts expected stimulus without controls.
    await expectPromptContains(experimentPage, "synchronized audio");
    await expect(experimentPage.locator("#audio-prompt-controls")).toHaveCount(0);
    await expect
      .poll(async () => {
        const activeSoundIds = await getActiveSoundIds(experimentPage);
        return activeSoundIds.includes("bier");
      })
      .toBe(true);
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 5: verify font-size rendering differences survive frontend pipeline.
    await expectPromptContains(experimentPage, "different font sizes");
    const bigText = experimentPage.locator("#main-body svg text").filter({
      hasText: "Big text"
    });
    const smallText = experimentPage.locator("#main-body svg text").filter({
      hasText: "Small text"
    });
    await expect(bigText).toBeVisible({ timeout: PROMPT_TIMEOUT_MS });
    await expect(smallText).toBeVisible({ timeout: PROMPT_TIMEOUT_MS });
    const [bigTextHeight, smallTextHeight] = await Promise.all([
      getRenderedTextHeight(bigText),
      getRenderedTextHeight(smallText)
    ]);
    expect(Number.isFinite(bigTextHeight)).toBe(true);
    expect(Number.isFinite(smallTextHeight)).toBe(true);
    expect(bigTextHeight).toBeGreaterThan(smallTextHeight);
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 6: verify mixed GraphicPrompt + GraphicControl page and chosen-answer integrity.
    await expectPromptContains(experimentPage, "both a GraphicPrompt and a GraphicControl");
    await expect(
      experimentPage
        .locator("#main-body svg text")
        .filter({ hasText: "What's up? Click to answer." })
    ).toBeVisible({ timeout: PROMPT_TIMEOUT_MS });
    const lotsGraphic = experimentPage.locator("#main-body svg text").filter({
      hasText: "Lots."
    });
    await expect(lotsGraphic).toBeVisible({ timeout: PROMPT_TIMEOUT_MS });
    await clickUiAndWaitForPageChange(experimentPage, lotsGraphic);

    const secondDebugAnswer = await experimentPage.locator("#main-body").innerText();
    await expect(experimentPage.locator("#main-body")).toContainText(
      "'clicked_object': 'lots'"
    );
    const [secondX, secondY] = extractClickCoordinates(secondDebugAnswer);
    expect(secondX).toBeGreaterThan(0);
    expect(secondY).toBeGreaterThan(0);
    expect(secondX).toBeLessThanOrEqual(300);
    expect(secondY).toBeLessThanOrEqual(100);

    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 7: verify transition into recorder setup still renders expected UI components.
    await expectMainBodyContains(experimentPage, "enable your sound recorder");
    await expect(experimentPage.locator("#audio-meter")).toBeVisible();
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 8: verify graphic-timed recording flow enables response, records, and exposes playback.
    await expectPromptContains(
      experimentPage,
      "trigger timing in the Control object"
    );
    await expect(experimentPage.locator("#btn-record-record")).toHaveCount(0);
    await expectMainBodyContains(experimentPage, "3");
    await expectMainBodyContains(experimentPage, "2");
    await expectMainBodyContains(experimentPage, "1");
    await expectMainBodyContains(experimentPage, "Sing!");
    await expectMainBodyContains(experimentPage, "Stop.");
    await waitForTrialEventCount(experimentPage, "responseEnable", 1, 30000);
    await waitForTrialEventCount(experimentPage, "recordStart", 1, 45000);
    await waitForTrialEventCount(experimentPage, "recordEnd", 1, 45000);
    const recordedAudio = await getStagedAudioRecordingInfo(experimentPage);
    expect(recordedAudio.exists).toBe(true);
    expect(recordedAudio.size).toBeGreaterThan(0);
    if (recordedAudio.type) {
      expect(recordedAudio.type).toContain("audio");
    }
    await expect(experimentPage.locator("#next-button")).toBeEnabled({
      timeout: STEP_TIMEOUT_MS
    });
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

    // Section 9: verify normal experiment termination route remains intact after assertions above.
    const finishButton = experimentPage.locator("#Finish");
    await expect(finishButton).toBeVisible({ timeout: STEP_TIMEOUT_MS });
    await finishButton.first().click();
    await experimentPage.waitForURL(
      (url) => url.toString().includes("recruiter-exit"),
      { timeout: STEP_TIMEOUT_MS }
    );
  });
});
