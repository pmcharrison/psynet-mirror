const path = require("path");
const { test } = require("./fixtures");

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

// A representative desktop viewport. The occlusion invariant is viewport-
// relative: a control that falls entirely below the fold is treated as ordinary
// scrolling, so a very short viewport would silently weaken the check.
test.use({ viewport: { width: 1280, height: 900 } });

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

      // A page that declares expect_scrolling=True is exempt from the
      // reachability check but must still keep its controls reachable at the
      // end of the scroll.
      await waitForMainBodyContains(
        experimentPage,
        "deliberately long page",
        STEP_TIMEOUT_MS
      );
      await assertPageInvariants(experimentPage, "long page (expect_scrolling)");
    } finally {
      await stopExperiment(proc);
    }
  }
);
