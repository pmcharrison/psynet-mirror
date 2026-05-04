const path = require("path");
const { test, expect } = require("@playwright/test");

const {
  advanceUntilFinish,
  assertExpectedTimelinePathActive,
  clickNextAndWait,
  completeInitialGateway,
  startResponseSubmitTracker,
  waitForNextEnabled,
  waitForResponseSubmitIncrement,
  withExperiment
} = require("../psynetHarness");

const PROMPT_TIMEOUT_MS = 90000;
const STEP_TIMEOUT_MS = 120000;

async function expectPromptContains(page, text, timeout = PROMPT_TIMEOUT_MS) {
  await expect(page.locator("#prompt-text")).toContainText(text, { timeout });
}

async function expectMainBodyContains(page, text, timeout = PROMPT_TIMEOUT_MS) {
  await expect(page.locator("#main-body")).toContainText(text, { timeout });
}

async function answerSingleRating(page, value) {
  const item = page.locator(".sd-rating__item").nth(value - 1);
  await expect(item).toBeVisible({ timeout: PROMPT_TIMEOUT_MS });
  await item.click();
}

async function answerMultiRating(page, answers) {
  const questions = page.locator(".sd-question");
  await expect(questions).toHaveCount(2, { timeout: PROMPT_TIMEOUT_MS });
  for (const [index, value] of answers.entries()) {
    const item = questions
      .nth(index)
      .locator(".sd-rating__item")
      .nth(value - 1);
    await item.click();
  }
}

async function nudgeSlider(page, selector) {
  await page.locator(selector).evaluate((element) => {
    const slider = element;
    const current = Number.parseFloat(slider.value);
    const step = Number.parseFloat(slider.step || "1") || 1;
    slider.value = String(current + step);
    slider.dispatchEvent(new Event("input", { bubbles: true }));
    slider.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

test("modular_page feature demo", async ({ page, context }) => {
  const absDir = path.resolve("demos/features/modular_page");
  await withExperiment(page, context, absDir, async (experimentPage) => {
    const submitTracker = startResponseSubmitTracker(experimentPage);
    try {
      await completeInitialGateway(experimentPage);
      await assertExpectedTimelinePathActive(experimentPage, 20000);

      await expectMainBodyContains(
        experimentPage,
        "simple text page",
        PROMPT_TIMEOUT_MS
      );
      await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

      await expectMainBodyContains(
        experimentPage,
        "simple formatting",
        PROMPT_TIMEOUT_MS
      );
      await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

      await expectPromptContains(
        experimentPage,
        "RatingControl",
        PROMPT_TIMEOUT_MS
      );
      await answerSingleRating(experimentPage, 3);
      await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

      await expectMainBodyContains(experimentPage, "Page type", PROMPT_TIMEOUT_MS);
      await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

      await expectPromptContains(
        experimentPage,
        "MultiRatingControl",
        PROMPT_TIMEOUT_MS
      );
      await answerMultiRating(experimentPage, [4, 5]);
      await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

      await expectMainBodyContains(experimentPage, "Metadata", PROMPT_TIMEOUT_MS);
      await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

      await expectPromptContains(
        experimentPage,
        "audio prompt combined with a push button control",
        PROMPT_TIMEOUT_MS
      );
      await expect(experimentPage.locator(".push-button").first()).toBeVisible({
        timeout: PROMPT_TIMEOUT_MS
      });
      await experimentPage.locator(".push-button").first().click();
      await expectMainBodyContains(experimentPage, "Page type", STEP_TIMEOUT_MS);

      await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

      await expectPromptContains(
        experimentPage,
        "timed push button control",
        PROMPT_TIMEOUT_MS
      );
      await experimentPage.locator(".push-button").nth(1).click();
      await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

      await expectMainBodyContains(experimentPage, "Answer", PROMPT_TIMEOUT_MS);
      await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

      await expectPromptContains(
        experimentPage,
        "frame slider",
        PROMPT_TIMEOUT_MS
      );
      await waitForNextEnabled(experimentPage, STEP_TIMEOUT_MS);
      await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

      await expectMainBodyContains(experimentPage, "Metadata", PROMPT_TIMEOUT_MS);
      await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

      await expectPromptContains(
        experimentPage,
        "video slider page",
        PROMPT_TIMEOUT_MS
      );
      await nudgeSlider(experimentPage, "#sliderpage_slider");
      await waitForNextEnabled(experimentPage, STEP_TIMEOUT_MS);
      await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

      await expectMainBodyContains(experimentPage, "Answer", PROMPT_TIMEOUT_MS);
      await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

      await expectPromptContains(experimentPage, "adds 'Hello'", PROMPT_TIMEOUT_MS);
      await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

      await expectPromptContains(
        experimentPage,
        "custom control interface",
        PROMPT_TIMEOUT_MS
      );
      const customText = "P4 override survives page N and stops at page N+1.";
      await experimentPage.locator("#text-input").fill(customText);
      const overrideSubmitBaseline = submitTracker.getCount();
      await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);
      await waitForResponseSubmitIncrement(
        submitTracker,
        overrideSubmitBaseline,
        1,
        STEP_TIMEOUT_MS
      );

      await expectMainBodyContains(experimentPage, "Page type", PROMPT_TIMEOUT_MS);
      await expectMainBodyContains(experimentPage, customText, PROMPT_TIMEOUT_MS);
      await expectMainBodyContains(
        experimentPage,
        "aquamarine",
        PROMPT_TIMEOUT_MS
      );
      await expect
        .poll(
          () =>
            experimentPage.evaluate(() =>
              window.psynet?.stageResponse === null
                ? "null"
                : typeof window.psynet?.stageResponse
            ),
          { timeout: 10000 }
        )
        .toMatch(/^(null|undefined)$/);

      await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);
      await advanceUntilFinish(experimentPage, { timeoutMs: STEP_TIMEOUT_MS });
    } finally {
      submitTracker.stop();
    }
  });
});
