const path = require("path");
const { test, expect } = require("./fixtures");

const {
  assertNoBackendError,
  beginExperiment,
  enterTimelineAfterGateway,
  startExperiment,
  stopExperiment,
  summarizeParticipantRequests,
  unexpectedBlockingRequests,
  waitForTimelinePageReady,
  withFreshParticipantIds
} = require("./psynetHarness");

const STEP_TIMEOUT_MS = 120000;
// Below the 5s timeline lock timeout so a lock-wait busy path fails this test.
const ENTRY_REQUEST_MAX_MS = 2500;
const START_PAGE_MAX_MS = 6000;
const BLOCKING_REQUEST_MS = 4000;

function entryPathRequests(records) {
  return records.filter((record) =>
    ["create_participant", "load_participant", "timeline_document"].includes(
      record.kind
    )
  );
}

function assertEntryWasResponsive(entry, label) {
  const summary = summarizeParticipantRequests(entry.tracker.records);
  const entryRequests = entryPathRequests(entry.tracker.records);
  expect(entry.timeline.status, `${label} first GET /timeline (${summary})`).toBe(
    200
  );
  expect(entry.timeline.busy, `${label} first GET /timeline was busy (${summary})`).toBe(
    false
  );
  expect(
    entry.timeline.busyPage,
    `${label} first GET /timeline rendered a busy page (${summary})`
  ).toBe(false);
  expect(
    unexpectedBlockingRequests(entryRequests, ENTRY_REQUEST_MAX_MS),
    `${label} unexpected entry blocking: ${summary}`
  ).toEqual([]);
  expect(
    entry.timeline.durationMs,
    `${label} GET /timeline took ${Math.round(entry.timeline.durationMs)}ms (${summary})`
  ).toBeLessThan(ENTRY_REQUEST_MAX_MS);
  expect(
    entry.start.consentToTimelineMs,
    `${label} stayed on Starting experiment... for ${entry.start.consentToTimelineMs}ms (${summary})`
  ).toBeLessThan(START_PAGE_MAX_MS);
}

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
  let firstEntry;
  let secondEntry;

  try {
    const recruitmentUrl = await experiment.urlPromise;
    firstParticipant = await beginExperiment(
      await firstContext.newPage(),
      firstContext,
      withFreshParticipantIds(recruitmentUrl, "stacked_hold_first")
    );
    firstEntry = await enterTimelineAfterGateway(
      firstParticipant,
      STEP_TIMEOUT_MS
    );
    assertEntryWasResponsive(firstEntry, "first arriver");
    expect(firstEntry.paint.type).toBe("_BarrierHoldPage");
    expect(firstEntry.paint.showsHold).toBe(true);
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
    secondEntry = await enterTimelineAfterGateway(
      secondParticipant,
      STEP_TIMEOUT_MS
    );
    assertEntryWasResponsive(secondEntry, "last arriver");
    expect(secondEntry.paint.type).toBe("ModularPage");
    expect(secondEntry.paint.showsHold).toBe(false);
    expect(
      secondEntry.timeline.durationMs,
      `last arriver GET /timeline ${Math.round(secondEntry.timeline.durationMs)}ms vs first ${Math.round(firstEntry.timeline.durationMs)}ms`
    ).toBeLessThan(firstEntry.timeline.durationMs + ENTRY_REQUEST_MAX_MS);
    expect(
      secondEntry.start.consentToTimelineMs,
      `last arriver Starting experiment... ${secondEntry.start.consentToTimelineMs}ms vs first ${firstEntry.start.consentToTimelineMs}ms`
    ).toBeLessThan(firstEntry.start.consentToTimelineMs + ENTRY_REQUEST_MAX_MS);
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

    await firstEntry.tracker.flush();
    await secondEntry.tracker.flush();
    expect(
      unexpectedBlockingRequests(firstEntry.tracker.records, BLOCKING_REQUEST_MS),
      `first arriver unexpected blocking: ${summarizeParticipantRequests(firstEntry.tracker.records)}`
    ).toEqual([]);
    expect(
      unexpectedBlockingRequests(secondEntry.tracker.records, BLOCKING_REQUEST_MS),
      `last arriver unexpected blocking: ${summarizeParticipantRequests(secondEntry.tracker.records)}`
    ).toEqual([]);

    await assertNoBackendError(firstParticipant);
    await assertNoBackendError(secondParticipant);
  } finally {
    firstEntry?.tracker.stop();
    secondEntry?.tracker.stop();
    await firstContext.close();
    await secondContext.close();
    await stopExperiment(experiment.proc);
  }
});
