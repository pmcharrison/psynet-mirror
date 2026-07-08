const path = require("path");
const { test, expect } = require("../fixtures");

const { completeInitialGateway, withExperiment } = require("../psynetHarness");

const STEP_TIMEOUT_MS = 120000;

/*
Regression coverage for the migrated color-slider page (js_links) under the
default in-place timeline transitions.

The gibbs color-slider control ships its page JavaScript via js_links
(static/color-slider.js). In in-place mode, page js_links execute before the
slider control's main-body macro script (see activateTimelineFragmentLifecycle),
so a top-level `psynet.page.control.slider.onSliderEvent = ...` in that file runs
before `psynet.page.control.slider` exists. Reaching this page in a browser
therefore raises an uncaught page error, which the failOnPageErrors fixture turns
into a test failure. Bot tests never caught this because bots do not execute JS.
*/

test("gibbs color-slider page activates without uncaught page errors", async ({
  page,
  context
}) => {
  const absDir = path.resolve("demos/experiments/gibbs");

  await withExperiment(page, context, absDir, async (experimentPage) => {
    await completeInitialGateway(experimentPage);

    // First timeline page: choose a participant group.
    await expect(experimentPage.locator(".push-button").first()).toBeVisible({
      timeout: STEP_TIMEOUT_MS
    });
    await experimentPage.locator(".push-button").first().click();

    // Reaching the color-slider trial page runs static/color-slider.js. If it
    // throws (js_links running before the slider control state exists), the
    // failOnPageErrors fixture fails this test at teardown.
    await expect(experimentPage.locator("#color-box")).toBeVisible({
      timeout: STEP_TIMEOUT_MS
    });

    // And the live-update hook (color-slider.js) must have taken effect: moving
    // the slider recolours the box. If the onSliderEvent assignment was lost,
    // the box colour never changes.
    const colorBox = experimentPage.locator("#color-box");
    const slider = experimentPage.locator("input.slider-range").first();
    await expect(slider).toBeVisible({ timeout: STEP_TIMEOUT_MS });

    const before = await colorBox.evaluate(
      (el) => getComputedStyle(el).backgroundColor
    );
    await slider.evaluate((el) => {
      el.value = String((Number(el.value) + 60) % 256);
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await expect
      .poll(
        () => colorBox.evaluate((el) => getComputedStyle(el).backgroundColor),
        { timeout: STEP_TIMEOUT_MS }
      )
      .not.toBe(before);
  });
});
