const path = require("path");
const { test, expect } = require("../fixtures");

const {
  assertExpectedTimelinePathActive,
  assertNoBackendError,
  clickNextAndWait,
  completeInitialGateway,
  withExperiment
} = require("../psynetHarness");

const STEP_TIMEOUT_MS = 120000;

test("jsPsych waits for page readiness and removes persistent listeners", async ({
  page,
  context
}) => {
  await context.addInitScript(() => {
    const trackedTypes = new Set([
      "blur",
      "focus",
      "fullscreenchange",
      "mozfullscreenchange",
      "webkitfullscreenchange",
      "jspsych-activate"
    ]);
    const counts = {};
    window.__jsPsychPersistentListenerCounts = counts;
    const originalAdd = EventTarget.prototype.addEventListener;
    const originalRemove = EventTarget.prototype.removeEventListener;

    EventTarget.prototype.addEventListener = function (type, listener, options) {
      if ((this === window || this === document) && trackedTypes.has(type)) {
        counts[type] = (counts[type] || 0) + 1;
      }
      return originalAdd.call(this, type, listener, options);
    };
    EventTarget.prototype.removeEventListener = function (
      type,
      listener,
      options
    ) {
      if ((this === window || this === document) && trackedTypes.has(type)) {
        counts[type] = Math.max(0, (counts[type] || 0) - 1);
      }
      return originalRemove.call(this, type, listener, options);
    };
  });

  await withExperiment(
    page,
    context,
    path.resolve("demos/experiments/jspsych"),
    async (experimentPage) => {
      await completeInitialGateway(experimentPage);
      await assertExpectedTimelinePathActive(experimentPage, 20000);
      await expect(experimentPage.locator("#main-body")).toContainText(
        "quick jsPsych task begins",
        { timeout: STEP_TIMEOUT_MS }
      );
      const baselineListeners = await experimentPage.evaluate(() =>
        Object.values(window.__jsPsychPersistentListenerCounts).reduce(
          (total, count) => total + count,
          0
        )
      );

      await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);
      await expect(experimentPage.locator("#main-body")).toContainText(
        "quick jsPsych task completed",
        { timeout: STEP_TIMEOUT_MS }
      );
      await expect
        .poll(
          () =>
            experimentPage.evaluate(() =>
              Object.values(window.__jsPsychPersistentListenerCounts).reduce(
                (total, count) => total + count,
                0
              )
            ),
          { timeout: STEP_TIMEOUT_MS }
        )
        .toBe(baselineListeners);

      await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);
      await expect(experimentPage.locator("#js-psych")).toContainText(
        "Welcome to the experiment",
        { timeout: STEP_TIMEOUT_MS }
      );
      await expect
        .poll(
          () =>
            experimentPage.evaluate(() =>
              Object.values(window.__jsPsychPersistentListenerCounts).reduce(
                (total, count) => total + count,
                0
              )
            ),
          { timeout: STEP_TIMEOUT_MS }
        )
        .toBe(baselineListeners + 6);
      await assertNoBackendError(experimentPage);
    }
  );
});
