const path = require("path");
const { test, expect } = require("./fixtures");
const {
  ACTION_PROMPT,
  GROUP_HOLD_TEXT,
  RESULTS_PROMPT,
  STEP_TIMEOUT_MS,
  armChoiceHold,
  assertNoSessionErrors,
  assertWaiterReleasedWithLastArriver,
  awaitPossiblyHeldArrival,
  closeHoldSessions,
  enterSkippingHold,
  enterTimelineAfterGateway,
  enterWaitingHold,
  startHoldExperiment,
  stopExperiment,
  submitLastChoice
} = require("./stackedHoldHarness");

const TRIO_DIR = path.resolve("tests/playwright/experiments/stacked_group_holds");

test("last of three skips stacked holds and releases every waiter", { tag: "@both" }, async ({
  browser
}) => {
  // The second member must still first-paint a hold. Only the third member
  // skips, and both waiters must leave from the server wake.
  const { experiment, sessions } = await startHoldExperiment(browser, TRIO_DIR, [
    "trio_first",
    "trio_second",
    "trio_third"
  ]);
  const [first, second, last] = sessions;

  try {
    await enterWaitingHold(first, {
      holdText: GROUP_HOLD_TEXT,
      prompt: ACTION_PROMPT
    });
    await enterWaitingHold(second, {
      holdText: GROUP_HOLD_TEXT,
      prompt: ACTION_PROMPT
    });
    await expect(
      first.page.locator("#psynet-timeline-hold-indicator")
    ).toBeVisible({ timeout: STEP_TIMEOUT_MS });
    const lastEntry = await enterSkippingHold(last);
    await expect(last.page.getByRole("button", { name: "go" })).toBeVisible();
    await assertWaiterReleasedWithLastArriver(first, lastEntry);
    await assertWaiterReleasedWithLastArriver(second, lastEntry);
    await assertNoSessionErrors(sessions);
  } finally {
    await closeHoldSessions(sessions);
    await stopExperiment(experiment.proc);
  }
});

test("two late trio members arriving together release every waiter", { tag: "@both" }, async ({
  browser
}) => {
  // Concurrent last arrivals share one group fill. Whoever loses the first
  // paint still has to leave as soon as the group is complete.
  const { experiment, sessions } = await startHoldExperiment(browser, TRIO_DIR, [
    "trio_wait",
    "trio_late_a",
    "trio_late_b"
  ]);
  const [first, lateA, lateB] = sessions;

  try {
    await enterWaitingHold(first, {
      holdText: GROUP_HOLD_TEXT,
      prompt: ACTION_PROMPT
    });
    const [entryA, entryB] = await Promise.all([
      enterTimelineAfterGateway(lateA.page, STEP_TIMEOUT_MS),
      enterTimelineAfterGateway(lateB.page, STEP_TIMEOUT_MS)
    ]);
    const laterEntry =
      entryA.start.timelineAtMs >= entryB.start.timelineAtMs ? entryA : entryB;
    await assertWaiterReleasedWithLastArriver(first, laterEntry);
    await awaitPossiblyHeldArrival(lateA, entryA, laterEntry, {
      holdText: GROUP_HOLD_TEXT
    });
    await awaitPossiblyHeldArrival(lateB, entryB, laterEntry, {
      holdText: GROUP_HOLD_TEXT
    });
    await assertNoSessionErrors(sessions);
  } finally {
    await closeHoldSessions(sessions);
    await stopExperiment(experiment.proc);
  }
});

test("last of three choices releases both waiting members", { tag: "@both" }, async ({
  browser
}) => {
  // The post-choice barrier is a POST /response last arrival with two people
  // already held. Both have to leave without a safety poll.
  const { experiment, sessions } = await startHoldExperiment(browser, TRIO_DIR, [
    "trio_choice_a",
    "trio_choice_b",
    "trio_choice_c"
  ]);
  const [first, second, last] = sessions;

  try {
    await enterWaitingHold(first, {
      holdText: GROUP_HOLD_TEXT,
      prompt: ACTION_PROMPT
    });
    await enterWaitingHold(second, {
      holdText: GROUP_HOLD_TEXT,
      prompt: ACTION_PROMPT
    });
    const lastEntry = await enterSkippingHold(last);
    await assertWaiterReleasedWithLastArriver(first, lastEntry);
    await assertWaiterReleasedWithLastArriver(second, lastEntry);

    await armChoiceHold(first, {
      holdText: GROUP_HOLD_TEXT,
      prompt: RESULTS_PROMPT
    });
    await armChoiceHold(second, {
      holdText: GROUP_HOLD_TEXT,
      prompt: RESULTS_PROMPT
    });
    const lastChoice = await submitLastChoice(last, { prompt: RESULTS_PROMPT });
    await assertWaiterReleasedWithLastArriver(first, lastChoice, {
      prompt: RESULTS_PROMPT
    });
    await assertWaiterReleasedWithLastArriver(second, lastChoice, {
      prompt: RESULTS_PROMPT
    });
    await assertNoSessionErrors(sessions);
  } finally {
    await closeHoldSessions(sessions);
    await stopExperiment(experiment.proc);
  }
});
