const path = require("path");
const { test, expect } = require("./fixtures");

const {
  assertNoBackendError,
  beginExperiment,
  completeInitialGateway,
  startExperiment,
  startResponseSubmitTracker,
  stopExperiment,
  withFreshParticipantIds
} = require("./psynetHarness");

const STEP_TIMEOUT_MS = 120000;

test("default barriers hold the current page until websocket release", { tag: "@inplace-only" }, async ({
  browser
}) => {
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
      withFreshParticipantIds(recruitmentUrl, "barrier_hold_first")
    );
    secondParticipant = await beginExperiment(
      await secondContext.newPage(),
      secondContext,
      withFreshParticipantIds(recruitmentUrl, "barrier_hold_second")
    );

    await Promise.all([
      completeInitialGateway(firstParticipant),
      completeInitialGateway(secondParticipant)
    ]);
    await Promise.all([
      expect(firstParticipant.locator("#main-body")).toContainText(
        "Choose your action",
        { timeout: STEP_TIMEOUT_MS }
      ),
      expect(secondParticipant.locator("#main-body")).toContainText(
        "Choose your action",
        { timeout: STEP_TIMEOUT_MS }
      )
    ]);

    const pageErrors = [];
    firstParticipant.on("pageerror", (error) => pageErrors.push(error.message));
    secondParticipant.on("pageerror", (error) => pageErrors.push(error.message));
    const firstResponses = startResponseSubmitTracker(firstParticipant);
    await firstParticipant.getByRole("button", { name: "rock" }).click();
    await expect(
      firstParticipant.locator("#psynet-timeline-hold-indicator")
    ).toBeVisible({ timeout: STEP_TIMEOUT_MS });
    await expect(firstParticipant.locator("#main-body")).toContainText(
      "Choose your action"
    );
    await expect(firstParticipant.locator("body")).toHaveClass(/timeline-held/);

    // The initial WebSocket connection reconciles once. Afterwards a short
    // wait should not produce the old twice-per-second response polling.
    await firstParticipant.waitForTimeout(1000);
    const settledResponseCount = firstResponses.getCount();
    await firstParticipant.waitForTimeout(2500);
    expect(firstResponses.getCount()).toBeLessThanOrEqual(
      settledResponseCount + 1
    );

    await secondParticipant.getByRole("button", { name: "paper" }).click();
    await Promise.all([
      expect(firstParticipant.locator("#main-body")).toContainText(
        "Round results",
        { timeout: STEP_TIMEOUT_MS }
      ),
      expect(secondParticipant.locator("#main-body")).toContainText(
        "Round results",
        { timeout: STEP_TIMEOUT_MS }
      )
    ]);
    await expect(firstParticipant.locator("#main-body")).toContainText(
      "You lost."
    );
    await expect(secondParticipant.locator("#main-body")).toContainText(
      "You won!"
    );
    await expect(
      firstParticipant.locator("#psynet-timeline-hold-indicator")
    ).toHaveCount(0);

    const chatMessage = "Barrier hold chatroom regression";
    await firstParticipant.locator("#chatroom-chat-input").fill(chatMessage);
    await firstParticipant.locator("#chatroom-send-btn").click();
    await Promise.all([
      expect(firstParticipant.locator("#chatroom-messages")).toContainText(
        chatMessage
      ),
      expect(secondParticipant.locator("#chatroom-messages")).toContainText(
        chatMessage
      )
    ]);

    firstResponses.stop();
    await assertNoBackendError(firstParticipant);
    await assertNoBackendError(secondParticipant);
    expect(pageErrors).toEqual([]);
  } finally {
    await firstContext.close();
    await secondContext.close();
    await stopExperiment(experiment.proc);
  }
});
