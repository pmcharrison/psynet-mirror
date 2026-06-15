const path = require("path");
const { test, expect } = require("./fixtures");

const {
  assertInplaceTimelinePathActive,
  completeInitialGateway,
  waitForMainBodyContains,
  waitForTimelinePageReady,
  withExperiment
} = require("./psynetHarness");

const STEP_TIMEOUT_MS = 120000;

test("same-session timeline update preserves page fragment and emits pageUpdated", async ({
  page,
  context
}) => {
  const absDir = path.resolve(
    "tests/playwright/experiments/same_session_page_update"
  );

  await withExperiment(page, context, absDir, async (experimentPage) => {
    await completeInitialGateway(experimentPage);
    await assertInplaceTimelinePathActive(experimentPage, 20000);

    await waitForMainBodyContains(
      experimentPage,
      "First same-session page",
      STEP_TIMEOUT_MS
    );
    const initialState = await experimentPage.evaluate(() => ({
      pageUuid: window.pageUuid
    }));

    await experimentPage.locator("#next-button").click();

    await expect
      .poll(
        () =>
          experimentPage.evaluate(() => ({
            pageUuid: window.pageUuid,
            pageStep: window.psynet.page.contents?.step || null,
            messageCount: window.__sameSessionUnityMessages?.length || 0,
            markerText:
              document.getElementById("same-session-marker")?.textContent || "",
            nextPagePending: window.psynet.nextPagePending
          })),
        { timeout: STEP_TIMEOUT_MS }
      )
      .toMatchObject({
        pageUuid: initialState.pageUuid,
        pageStep: 2,
        messageCount: 1,
        markerText: "First same-session page",
        nextPagePending: false
      });

    const updatePayload = await experimentPage.evaluate(
      () => window.__sameSessionUnityMessages[0].payload
    );
    expect(updatePayload.contents).toMatchObject({ step: 2, label: "second" });
    expect(updatePayload.attributes.session_id).toBe("shared-session");

    // The DOM still shows the first page because same-session updates are for
    // long-lived Unity sessions that consume updated psynet.page metadata.
    await expect(experimentPage.locator("#same-session-marker")).toContainText(
      "First same-session page"
    );
    await waitForTimelinePageReady(experimentPage, STEP_TIMEOUT_MS);
  });
});
