const path = require("path");
const { test, expect } = require("./fixtures");

const {
  assertInplaceTimelinePathActive,
  assertNoBackendError,
  completeInitialGateway,
  waitForMainBodyContains,
  waitForPageChange,
  waitForTimelinePageReady,
  withExperiment
} = require("./psynetHarness");

const STEP_TIMEOUT_MS = 120000;

async function dispatchWindowClick(page) {
  await page.evaluate(() => {
    window.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
}

async function nextPageFromBrowser(page, answer = null) {
  const oldUuid = await page.evaluate(() => window.pageUuid || null);
  const result = await page.evaluate((rawAnswer) => window.psynet.nextPage(rawAnswer), answer);
  if (result) {
    await waitForPageChange(page, oldUuid, STEP_TIMEOUT_MS);
    await waitForTimelinePageReady(page, STEP_TIMEOUT_MS);
  }
  return result;
}

test("adversarial lifecycle handles rejection retry and page listener cleanup", async ({
  page,
  context
}) => {
  const absDir = path.resolve(
    "tests/playwright/experiments/adversarial_lifecycle"
  );

  await withExperiment(page, context, absDir, async (experimentPage) => {
    await completeInitialGateway(experimentPage);
    await assertInplaceTimelinePathActive(experimentPage, 20000);

    await waitForMainBodyContains(
      experimentPage,
      "Rejection retry page",
      STEP_TIMEOUT_MS
    );

    const rejected = await nextPageFromBrowser(experimentPage, "rejected");
    expect(rejected).toBe(false);
    await expect(experimentPage.locator("#alert-message")).toContainText(
      "Please submit the accepted answer.",
      { timeout: STEP_TIMEOUT_MS }
    );
    await expect
      .poll(
        () =>
          experimentPage.evaluate(() => ({
            nextPagePending: window.psynet.nextPagePending,
            stillOnRejectionPage: Boolean(
              document.getElementById("adversarial-rejection-page")
            )
          })),
        { timeout: STEP_TIMEOUT_MS }
      )
      .toEqual({
        nextPagePending: false,
        stillOnRejectionPage: true
      });
    await experimentPage.locator("#alert-button").click();

    const accepted = await nextPageFromBrowser(experimentPage, "accepted");
    expect(accepted).toBe(true);
    await waitForMainBodyContains(experimentPage, "Listener page first", STEP_TIMEOUT_MS);

    await dispatchWindowClick(experimentPage);
    await expect
      .poll(
        () => experimentPage.evaluate(() => window.__adversarialLifecycle),
        { timeout: STEP_TIMEOUT_MS }
      )
      .toMatchObject({
        listenerClicks: 1,
        cleanupCalls: 0,
        activations: ["first"]
      });

    expect(await nextPageFromBrowser(experimentPage)).toBe(true);
    await waitForMainBodyContains(
      experimentPage,
      "Listener cleanup checkpoint",
      STEP_TIMEOUT_MS
    );
    await dispatchWindowClick(experimentPage);
    await expect
      .poll(
        () => experimentPage.evaluate(() => window.__adversarialLifecycle),
        { timeout: STEP_TIMEOUT_MS }
      )
      .toMatchObject({
        listenerClicks: 1,
        cleanupCalls: 1,
        activations: ["first"]
      });

    expect(await nextPageFromBrowser(experimentPage)).toBe(true);
    await waitForMainBodyContains(experimentPage, "Listener page second", STEP_TIMEOUT_MS);
    await dispatchWindowClick(experimentPage);
    await expect
      .poll(
        () => experimentPage.evaluate(() => window.__adversarialLifecycle),
        { timeout: STEP_TIMEOUT_MS }
      )
      .toMatchObject({
        listenerClicks: 2,
        cleanupCalls: 1,
        activations: ["first", "second"]
      });
    await assertNoBackendError(experimentPage);
  });
});
