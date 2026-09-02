const path = require("path");
const { test, expect } = require("./fixtures");

const {
  beginExperiment,
  clickNextAndWait,
  completeInitialGateway,
  startExperiment,
  stopExperiment,
  waitForMainBodyContains,
  waitForTimelinePageReady
} = require("./psynetHarness");

const { assertPageInvariants } = require("./participantPageInvariants");

const STEP_TIMEOUT_MS = 120000;

// A representative desktop viewport. The reachability invariant is viewport-
// relative: a control that falls entirely below the fold is treated as ordinary
// scrolling, so a very short viewport would silently weaken the check.
const DESKTOP_VIEWPORT = { width: 1280, height: 900 };

// A narrow viewport exercises the mobile branch of the theme, where horizontal
// overflow is the failure that matters.
const MOBILE_VIEWPORT = { width: 375, height: 780 };

/**
 * Walks the participant flow of a purpose-built experiment and asserts the
 * structural invariants on every page, including the pre-timeline pages.
 *
 * The experiment is deliberately small: the invariants are properties of the
 * shared chrome and layout primitives, so a handful of representative pages
 * exercises them without paying for a sweep over every demo.
 */
test(
  "participant pages satisfy structural layout invariants",
  { tag: "@both" },
  async ({ page, context }) => {
    const experimentDir = path.resolve(
      "tests/playwright/experiments/participant_page_invariants"
    );

    // startExperiment rather than withExperiment, so that the ad page can be
    // checked before beginExperiment clicks through it.
    const { proc, urlPromise } = startExperiment(experimentDir);

    try {
      const url = await urlPromise;

      await page.setViewportSize(DESKTOP_VIEWPORT);
      await page.goto(url);
      await page.waitForSelector("#begin-button, button.btn-primary", {
        timeout: 30000
      });
      await assertPageInvariants(page, "ad page");

      const experimentPage = await beginExperiment(page, context, url);
      await assertPageInvariants(experimentPage, "consent gateway");

      await completeInitialGateway(experimentPage);

      // The timeline is fixed, so each step is named rather than discovered.
      await waitForMainBodyContains(
        experimentPage,
        "plain information page",
        STEP_TIMEOUT_MS
      );
      await assertPageInvariants(experimentPage, "information page");
      await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

      await waitForMainBodyContains(experimentPage, "radio options", STEP_TIMEOUT_MS);
      await assertPageInvariants(experimentPage, "radio page (nothing selected)");
      await experimentPage.locator("#alpha").check();
      await assertPageInvariants(experimentPage, "radio page (option selected)");
      await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

      await waitForMainBodyContains(experimentPage, "push buttons", STEP_TIMEOUT_MS);
      await assertPageInvariants(experimentPage, "push button page");
      await experimentPage.locator("#left").click();

      await waitForMainBodyContains(experimentPage, "tall graphic", STEP_TIMEOUT_MS);
      await waitForTimelinePageReady(experimentPage, STEP_TIMEOUT_MS);
      await assertPageInvariants(experimentPage, "graphic page");
      await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

      // A 16:9 graphic at 90% of the window would be wider than the 900px
      // surface. The box must shrink to the surface and keep that aspect
      // ratio, rather than clamping width independently of height.
      await waitForMainBodyContains(
        experimentPage,
        "landscape graphic",
        STEP_TIMEOUT_MS
      );
      await waitForTimelinePageReady(experimentPage, STEP_TIMEOUT_MS);
      await assertPageInvariants(experimentPage, "landscape graphic page");
      const landscapeBox = await experimentPage.locator("#graphic-prompt").boundingBox();
      expect(landscapeBox).not.toBeNull();
      expect(landscapeBox.width / landscapeBox.height).toBeCloseTo(16 / 9, 2);
      await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);

      // A page that declares expect_scrolling=True is exempt from the
      // reachability check but must still keep its controls reachable at the
      // end of the scroll.
      await waitForMainBodyContains(
        experimentPage,
        "deliberately long page",
        STEP_TIMEOUT_MS
      );
      await assertPageInvariants(experimentPage, "long page (expect_scrolling)");

      // Re-check the same page narrow. The mobile branch of the theme changes
      // the surface's margins and padding, where horizontal overflow is the
      // failure that matters.
      await experimentPage.setViewportSize(MOBILE_VIEWPORT);
      await experimentPage.waitForTimeout(300);
      await assertPageInvariants(experimentPage, "long page (mobile viewport)");
    } finally {
      await stopExperiment(proc);
    }
  }
);
