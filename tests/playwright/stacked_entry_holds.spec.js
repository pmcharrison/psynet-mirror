const path = require("path");
const { test, expect } = require("./fixtures");

const {
  assertNoBackendError,
  beginExperiment,
  captureFirstTimelineAfterGateway,
  readTimelinePageFromHtml,
  startExperiment,
  stopExperiment,
  waitForTimelinePageReady,
  withFreshParticipantIds
} = require("./psynetHarness");

const STEP_TIMEOUT_MS = 120000;

test("last arriver's first timeline page skips stacked partner holds", { tag: "@both" }, async ({
  browser
}) => {
  // Enter one participant at a time. The last arriver's first GET /timeline
  // document must already be the action page; waiting for that prompt later
  // can hide a hold that the poller then clears.
  const experiment = startExperiment(
    path.resolve("demos/experiments/rock_paper_scissors")
  );
  const firstContext = await browser.newContext();
  const secondContext = await browser.newContext();
  let firstParticipant;
  let secondParticipant;

  try {
    const recruitmentUrl = await experiment.urlPromise;
    firstParticipant = await beginExperiment(
      await firstContext.newPage(),
      firstContext,
      withFreshParticipantIds(recruitmentUrl, "stacked_hold_first")
    );
    const firstPaint = readTimelinePageFromHtml(
      await captureFirstTimelineAfterGateway(firstParticipant, STEP_TIMEOUT_MS)
    );
    expect(firstPaint.type).toBe("_BarrierHoldPage");
    expect(firstPaint.showsHold).toBe(true);
    await waitForTimelinePageReady(firstParticipant, STEP_TIMEOUT_MS);
    await expect(
      firstParticipant.locator("#psynet-timeline-hold-indicator")
    ).toBeVisible({ timeout: STEP_TIMEOUT_MS });
    await expect(
      firstParticipant.locator(".psynet-timeline-hold-message")
    ).toContainText("Waiting for your partner");

    secondParticipant = await beginExperiment(
      await secondContext.newPage(),
      secondContext,
      withFreshParticipantIds(recruitmentUrl, "stacked_hold_second")
    );
    const secondPaint = readTimelinePageFromHtml(
      await captureFirstTimelineAfterGateway(secondParticipant, STEP_TIMEOUT_MS)
    );
    expect(secondPaint.type).toBe("ModularPage");
    expect(secondPaint.showsHold).toBe(false);
    await waitForTimelinePageReady(secondParticipant, STEP_TIMEOUT_MS);
    await expect(secondParticipant.locator("#main-body")).toContainText(
      "Choose your action",
      { timeout: STEP_TIMEOUT_MS }
    );
    await expect(
      secondParticipant.locator("#psynet-timeline-hold-indicator")
    ).toHaveCount(0);
    await expect(secondParticipant.locator("body")).not.toHaveClass(
      /timeline-held/
    );
    await expect(
      secondParticipant.getByRole("button", { name: "rock" })
    ).toBeVisible();

    await expect(firstParticipant.locator("#main-body")).toContainText(
      "Choose your action",
      { timeout: STEP_TIMEOUT_MS }
    );
    await expect(
      firstParticipant.locator("#psynet-timeline-hold-indicator")
    ).toHaveCount(0);

    await assertNoBackendError(firstParticipant);
    await assertNoBackendError(secondParticipant);
  } finally {
    await firstContext.close();
    await secondContext.close();
    await stopExperiment(experiment.proc);
  }
});
