const { expect } = require("./fixtures");
const {
  assertNoBackendError,
  beginExperiment,
  enterTimelineAfterGateway,
  installTimelineHoldReleaseProbe,
  installTimelineHoldReleaseProbeOnContext,
  readTimelineHoldReleaseProbe,
  silenceTimelineHoldSafetyPoll,
  wrapTimelineHoldResumeProbe,
  startExperiment,
  startParticipantRequestTracker,
  startTimelineHoldSocketTracker,
  stopExperiment,
  summarizeParticipantRequests,
  unexpectedBlockingRequests,
  waitForHeldParticipantToResume,
  waitForTimelinePageReady,
  withFreshParticipantIds,
  isInplaceTimelineModeEnabled
} = require("./psynetHarness");

const STEP_TIMEOUT_MS = 120000;
const ENTRY_REQUEST_MAX_MS = 2500;
const START_PAGE_MAX_MS = 6000;
const BLOCKING_REQUEST_MS = 4000;
const PARTNER_HOLD_RELEASE_MAX_MS = 2500;
const WAITER_RELEASE_SPREAD_MAX_MS = 1500;
const SETTLE_HOLD_MS = 3500;
const ACTION_PROMPT = "Choose your action";
const RESULTS_PROMPT = "Everyone is ready";
const PAIR_HOLD_TEXT = "Waiting for your partner";
const GROUP_HOLD_TEXT = "Waiting for your group";
const RELEASE_RESUME_REASONS = new Set(["server notification", "queued hold wake"]);

function entryPathRequests(records) {
  return records.filter((record) =>
    ["create_participant", "load_participant", "timeline_document"].includes(
      record.kind
    )
  );
}

function publishedWakeTokens(holdFrames) {
  const tokens = [];
  for (const frame of holdFrames) {
    const jsonStart = frame.indexOf("{");
    if (jsonStart < 0) {
      continue;
    }
    try {
      const payload = JSON.parse(frame.slice(jsonStart));
      for (const target of payload.targets || []) {
        if (target.wake_token) {
          tokens.push(target.wake_token);
        }
      }
    } catch {
      // Keep going; the summary still includes the raw frame.
    }
  }
  return tokens;
}

function requestsSince(records, startedAtMs, kind = null) {
  return records.filter(
    (record) =>
      (record.startedAtMs ?? 0) >= startedAtMs &&
      (kind == null || record.kind === kind)
  );
}

function responsesSince(records, startedAtMs) {
  return requestsSince(records, startedAtMs, "response");
}

function lastArriverClock(lastEntry) {
  const kind = lastEntry.start?.kind === "choice" ? "choice" : "entry";
  const clickedAtMs =
    lastEntry.start?.clickedAtMs ?? lastEntry.start?.consentClickedAtMs;
  const paintedAtMs =
    lastEntry.start?.paintedAtMs ?? lastEntry.start?.timelineAtMs;
  const clickToPaintMs =
    lastEntry.start?.clickToPaintMs ??
    lastEntry.start?.consentToTimelineMs ??
    paintedAtMs - clickedAtMs;
  return { kind, clickedAtMs, paintedAtMs, clickToPaintMs };
}

function holdReleaseSummary({
  clickToPaintMs,
  afterClickMs,
  afterPaintMs,
  clockKind = "entry",
  holdResumePostMs,
  extraTimelineGets,
  probe,
  resumeRequests,
  resumeLog = [],
  holdFrames = [],
  waitingWakeToken = null,
  label = "waiter"
}) {
  const reasons = (probe.resumeReasons || [])
    .map((entry) => entry.reason)
    .join(",") || "none";
  const wake = probe.wakeReason
    ? `wake ${probe.wakeReason}`
    : "no hold wake event";
  const holdResumePost =
    holdResumePostMs == null ? "missing" : `${Math.round(holdResumePostMs)}ms`;
  const responseNotes =
    resumeLog
      .filter((entry) => entry.kind)
      .map((entry) => {
        if (entry.kind === "approved") {
          return `approved ${entry.pageType} fragment=${entry.hasFragment} hold=${entry.hasHold} requiresReload=${entry.requiresReload} inplace=${entry.inplace}`;
        }
        if (entry.kind === "rejected") {
          return `rejected ${entry.message || ""}`;
        }
        return entry.kind;
      })
      .join("; ") || "no response handler notes";
  const clickLabel =
    clockKind === "choice" ? "choice→paint" : "consent→timeline";
  const afterPaintLabel =
    clockKind === "choice" ? "last paint" : "last timeline";
  const afterClickLabel =
    clockKind === "choice" ? "after last choice" : "after last consent";
  return (
    `${label}: last arriver ${clickLabel} ${Math.round(clickToPaintMs)}ms; ` +
    `waiter ${Math.round(afterPaintMs)}ms after ${afterPaintLabel} ` +
    `(${Math.round(afterClickMs)}ms ${afterClickLabel}; ` +
    `hold-resume POST ${holdResumePost}; extra GET /timeline ${extraTimelineGets}; ` +
    `inplace=${isInplaceTimelineModeEnabled()}; ` +
    `${wake}; resumes ${reasons}; ${responseNotes}; ` +
    `hold resumes ${probe.nextPageHoldResumes?.length || 0}; ` +
    `waiting token ${waitingWakeToken || "missing"}; ` +
    `published ${publishedWakeTokens(holdFrames).join(",") || "none"}; ` +
    `requests ${summarizeParticipantRequests(resumeRequests)})`
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

async function createHoldSession(browser, recruitmentUrl, label) {
  const context = await browser.newContext();
  const resumeLog = [];
  await context.exposeBinding("__psynetRecordHoldResume", (_source, entry) => {
    resumeLog.push({
      ...(entry || {}),
      atMs: Date.now()
    });
  });
  await installTimelineHoldReleaseProbeOnContext(context);
  const page = await beginExperiment(
    await context.newPage(),
    context,
    withFreshParticipantIds(recruitmentUrl, label)
  );
  return {
    label,
    context,
    page,
    sockets: startTimelineHoldSocketTracker(page),
    resumeLog,
    entry: null,
    waitingWakeToken: null,
    resumePromise: null
  };
}

async function closeHoldSessions(sessions) {
  for (const session of sessions) {
    session.entry?.tracker.stop();
    session.sockets?.stop();
    await session.context.close();
  }
}

async function startHoldExperiment(browser, experimentDir, labels, options = {}) {
  const experiment = startExperiment(experimentDir, options);
  const recruitmentUrl = await experiment.urlPromise;
  const sessions = [];
  try {
    for (const label of labels) {
      sessions.push(await createHoldSession(browser, recruitmentUrl, label));
    }
  } catch (error) {
    await closeHoldSessions(sessions);
    await stopExperiment(experiment.proc);
    throw error;
  }
  return { experiment, sessions, recruitmentUrl };
}

async function armVisibleHold(
  session,
  { holdText, prompt, timeout = STEP_TIMEOUT_MS }
) {
  await expect(
    session.page.locator("#psynet-timeline-hold-indicator")
  ).toBeVisible({ timeout });
  await expect(
    session.page.locator(".psynet-timeline-hold-message")
  ).toContainText(holdText);
  await installTimelineHoldReleaseProbe(session.page);
  expect(
    await wrapTimelineHoldResumeProbe(session.page),
    `${session.label} hold-resume probe was not attached`
  ).toBe(true);
  session.waitingWakeToken = await session.page.evaluate(
    () => psynet.timelineHold?.hold?.wake_token || null
  );
  expect(
    await silenceTimelineHoldSafetyPoll(session.page),
    `${session.label} hold safety poll was not running`
  ).toBe(true);
  session.resumePromise = waitForHeldParticipantToResume(session.page, {
    prompt,
    timeout
  });
}

async function assertStillHeld(session, holdText) {
  await expect(
    session.page.locator("#psynet-timeline-hold-indicator")
  ).toBeVisible();
  await expect(
    session.page.locator(".psynet-timeline-hold-message")
  ).toContainText(holdText);
}

async function enterWaitingHold(session, { holdText, prompt, timeout = STEP_TIMEOUT_MS }) {
  session.entry = await enterTimelineAfterGateway(session.page, timeout);
  assertEntryWasResponsive(session.entry, session.label);
  expect(session.entry.paint.type).toBe("_BarrierHoldPage");
  expect(session.entry.paint.showsHold).toBe(true);
  await waitForTimelinePageReady(session.page, timeout);
  await armVisibleHold(session, { holdText, prompt, timeout });
  return session.entry;
}

async function enterSkippingHold(session, { timeout = STEP_TIMEOUT_MS } = {}) {
  session.entry = await enterTimelineAfterGateway(session.page, timeout);
  assertEntryWasResponsive(session.entry, session.label);
  expect(session.entry.paint.type).toBe("ModularPage");
  expect(session.entry.paint.showsHold).toBe(false);
  await waitForTimelinePageReady(session.page, timeout);
  await expect(session.page.locator("#main-body")).toContainText(ACTION_PROMPT, {
    timeout
  });
  await expect(session.page.locator("#psynet-timeline-hold-indicator")).toHaveCount(
    0
  );
  await expect(session.page.locator("body")).not.toHaveClass(/timeline-held/);
  return session.entry;
}

async function armChoiceHold(
  session,
  {
    holdText,
    prompt,
    buttonName = "go",
    timeout = STEP_TIMEOUT_MS
  }
) {
  session.choiceTracker = startParticipantRequestTracker(session.page);
  await session.page.getByRole("button", { name: buttonName }).click();
  await armVisibleHold(session, { holdText, prompt, timeout });
}

async function submitChoiceMaybeHeld(
  session,
  {
    holdText,
    prompt,
    buttonName = "go",
    timeout = STEP_TIMEOUT_MS
  }
) {
  session.choiceTracker = startParticipantRequestTracker(session.page);
  const clickedAtMs = Date.now();
  await session.page.getByRole("button", { name: buttonName }).click();
  await session.page.waitForFunction(
    ({ expectedPrompt, expectedHold }) => {
      const body = document.getElementById("main-body")?.innerText || "";
      const hold =
        document.querySelector(".psynet-timeline-hold-message")?.innerText || "";
      return body.includes(expectedPrompt) || hold.includes(expectedHold);
    },
    { expectedPrompt: prompt, expectedHold: holdText },
    { timeout }
  );
  const held =
    (await session.page.locator("#psynet-timeline-hold-indicator").count()) > 0;
  const doneAtMs = Date.now();
  if (!held) {
    await assertActionOrPrompt(session.page, prompt, timeout);
    expect(
      doneAtMs - clickedAtMs,
      `${session.label} stayed on a hold after a last-choice skip`
    ).toBeLessThan(PARTNER_HOLD_RELEASE_MAX_MS);
    return {
      held: false,
      start: {
        kind: "choice",
        clickedAtMs,
        paintedAtMs: doneAtMs,
        clickToPaintMs: doneAtMs - clickedAtMs,
        consentClickedAtMs: clickedAtMs,
        timelineAtMs: doneAtMs
      }
    };
  }
  await armVisibleHold(session, { holdText, prompt, timeout });
  return {
    held: true,
    start: {
      kind: "choice",
      clickedAtMs,
      paintedAtMs: doneAtMs,
      clickToPaintMs: doneAtMs - clickedAtMs,
      consentClickedAtMs: clickedAtMs,
      timelineAtMs: doneAtMs
    }
  };
}

async function submitLastChoice(
  session,
  { buttonName = "go", prompt, timeout = STEP_TIMEOUT_MS }
) {
  const clickedAtMs = Date.now();
  await session.page.getByRole("button", { name: buttonName }).click();
  await expect(session.page.locator("#main-body")).toContainText(prompt, {
    timeout
  });
  await expect(session.page.locator("#psynet-timeline-hold-indicator")).toHaveCount(
    0
  );
  const doneAtMs = Date.now();
  expect(
    doneAtMs - clickedAtMs,
    `${session.label} stayed on a hold after submitting the last choice`
  ).toBeLessThan(PARTNER_HOLD_RELEASE_MAX_MS);
  return {
    clickedAtMs,
    doneAtMs,
    start: {
      kind: "choice",
      clickedAtMs,
      paintedAtMs: doneAtMs,
      clickToPaintMs: doneAtMs - clickedAtMs,
      consentClickedAtMs: clickedAtMs,
      timelineAtMs: doneAtMs
    }
  };
}

async function assertWaiterReleasedWithLastArriver(
  session,
  lastEntry,
  { prompt = ACTION_PROMPT, timeout = STEP_TIMEOUT_MS } = {}
) {
  const resume = await session.resumePromise;
  await expect(session.page.locator("#main-body")).toContainText(prompt, {
    timeout
  });
  const probe = await readTimelineHoldReleaseProbe(session.page);
  if (session.choiceTracker) {
    await session.choiceTracker.flush();
  } else {
    await session.entry.tracker.flush();
  }
  const records = session.choiceTracker
    ? session.choiceTracker.records
    : session.entry.tracker.records;
  const clock = lastArriverClock(lastEntry);
  const sinceMs = clock.clickedAtMs;
  const resumeRequests = responsesSince(records, sinceMs);
  const afterClickMs = resume.resumedAtMs - clock.clickedAtMs;
  const afterPaintMs = resume.resumedAtMs - clock.paintedAtMs;
  const laterTimeline = requestsSince(
    records,
    clock.paintedAtMs,
    "timeline_document"
  );
  const holdResumePosts = resumeRequests.filter(
    (record) =>
      record.kind === "response" &&
      record.status === 200 &&
      record.holdResume === true
  );
  const holdResumePostMs = holdResumePosts[0]?.durationMs ?? null;
  const reasonsAfterLast = (session.resumeLog || [])
    .filter((entry) => entry.atMs >= sinceMs && entry.reason)
    .map((entry) => entry.reason);
  const summary = holdReleaseSummary({
    clickToPaintMs: clock.clickToPaintMs,
    afterClickMs,
    afterPaintMs,
    clockKind: clock.kind,
    holdResumePostMs,
    extraTimelineGets: laterTimeline.length,
    probe: {
      ...probe,
      resumeReasons: reasonsAfterLast.map((reason) => ({ reason, atMs: sinceMs }))
    },
    resumeRequests,
    resumeLog: session.resumeLog || [],
    holdFrames: session.sockets?.frames || [],
    waitingWakeToken: session.waitingWakeToken,
    label: session.label
  });
  expect(
    session.waitingWakeToken,
    `${session.label} hold is missing a wake token (${summary})`
  ).toBeTruthy();
  expect(
    publishedWakeTokens(session.sockets?.frames || []),
    `${session.label} last arriver did not wake the waiting hold (${summary})`
  ).toContain(session.waitingWakeToken);
  expect(
    afterPaintMs,
    `${session.label} hold-resume clock ran backwards (${summary})`
  ).toBeGreaterThan(-ENTRY_REQUEST_MAX_MS);
  expect(
    afterPaintMs,
    `${session.label} still held after the last arriver painted (${summary})`
  ).toBeLessThan(PARTNER_HOLD_RELEASE_MAX_MS);
  expect(
    afterClickMs,
    `${session.label} still held after the last arriver started (${summary})`
  ).toBeLessThan(START_PAGE_MAX_MS + PARTNER_HOLD_RELEASE_MAX_MS);
  expect(
    unexpectedBlockingRequests(resumeRequests, ENTRY_REQUEST_MAX_MS),
    `${session.label} hold-resume blocking: ${summary}`
  ).toEqual([]);
  expect(
    resumeRequests.filter((record) => record.busy),
    `${session.label} hold-resume retries: ${summary}`
  ).toEqual([]);
  if (isInplaceTimelineModeEnabled()) {
    expect(
      laterTimeline.length,
      `${session.label} extra /timeline reloads after the last arriver painted (${summary})`
    ).toBe(0);
  } else {
    expect(
      laterTimeline.length,
      `${session.label} extra /timeline reloads after the last arriver painted (${summary})`
    ).toBeLessThanOrEqual(1);
  }
  expect(
    holdResumePosts.length,
    `${session.label} missing hold-resume POST /response (${summary})`
  ).toBeGreaterThan(0);
  expect(
    reasonsAfterLast,
    `${session.label} used a safety poll after the last arriver started (${summary})`
  ).not.toContain("safety poll");
  expect(
    reasonsAfterLast,
    `${session.label} used a hold-timeout resume after the last arriver started (${summary})`
  ).not.toContain("hold timeout");
  expect(
    reasonsAfterLast.some((reason) => RELEASE_RESUME_REASONS.has(reason)),
    `${session.label} did not resume from a server wake (${summary})`
  ).toBe(true);
  expect(
    holdResumePosts.length,
    `${session.label} extra hold-resume requests: ${summary}`
  ).toBeLessThanOrEqual(2);
  console.log(summary);
  return { resume, probe, summary };
}

async function assertAllWaitersReleasedTogether(
  sessions,
  lastEntry,
  { prompt = ACTION_PROMPT, timeout = STEP_TIMEOUT_MS } = {}
) {
  const results = await Promise.all(
    sessions.map((session) =>
      assertWaiterReleasedWithLastArriver(session, lastEntry, { prompt, timeout })
    )
  );
  const times = results.map((result) => result.resume.resumedAtMs);
  const spread = Math.max(...times) - Math.min(...times);
  expect(
    spread,
    `waiting members left ${spread}ms apart after the hold was satisfied`
  ).toBeLessThan(WAITER_RELEASE_SPREAD_MAX_MS);
  return results;
}

async function awaitPossiblyHeldArrival(
  session,
  entry,
  lastEntry,
  { holdText, prompt = ACTION_PROMPT, timeout = STEP_TIMEOUT_MS } = {}
) {
  session.entry = entry;
  if (entry.timeline.busy || entry.timeline.busyPage || !entry.paint.showsHold) {
    await assertActionPage(session.page, timeout);
    return;
  }
  await waitForTimelinePageReady(session.page, timeout);
  if ((await session.page.locator("#psynet-timeline-hold-indicator").count()) === 0) {
    await assertActionPage(session.page, timeout);
    await entry.tracker.flush();
    const clock = lastArriverClock(lastEntry);
    const laterTimeline = requestsSince(
      entry.tracker.records,
      clock.paintedAtMs,
      "timeline_document"
    );
    if (isInplaceTimelineModeEnabled()) {
      expect(
        laterTimeline.length,
        `${session.label} extra /timeline reloads after a first-paint hold already cleared`
      ).toBe(0);
    } else {
      expect(
        laterTimeline.length,
        `${session.label} extra /timeline reloads after a first-paint hold already cleared`
      ).toBeLessThanOrEqual(1);
    }
    return;
  }
  await armVisibleHold(session, { holdText, prompt, timeout });
  await assertWaiterReleasedWithLastArriver(session, lastEntry, { prompt, timeout });
}

async function assertActionOrPrompt(page, prompt, timeout = STEP_TIMEOUT_MS) {
  await waitForTimelinePageReady(page, timeout);
  await expect(page.locator("#main-body")).toContainText(prompt, { timeout });
  await expect(page.locator("#psynet-timeline-hold-indicator")).toHaveCount(0);
}

async function assertActionPage(page, timeout = STEP_TIMEOUT_MS) {
  await assertActionOrPrompt(page, ACTION_PROMPT, timeout);
}

async function assertNoSessionErrors(sessions) {
  for (const session of sessions) {
    if (session.entry?.tracker) {
      await session.entry.tracker.flush();
      expect(
        unexpectedBlockingRequests(session.entry.tracker.records, BLOCKING_REQUEST_MS),
        `${session.label} unexpected blocking: ${summarizeParticipantRequests(
          session.entry.tracker.records
        )}`
      ).toEqual([]);
    }
    if (session.choiceTracker) {
      session.choiceTracker.stop();
    }
    await assertNoBackendError(session.page);
  }
}

module.exports = {
  ACTION_PROMPT,
  BLOCKING_REQUEST_MS,
  ENTRY_REQUEST_MAX_MS,
  GROUP_HOLD_TEXT,
  PAIR_HOLD_TEXT,
  PARTNER_HOLD_RELEASE_MAX_MS,
  RESULTS_PROMPT,
  SETTLE_HOLD_MS,
  START_PAGE_MAX_MS,
  STEP_TIMEOUT_MS,
  WAITER_RELEASE_SPREAD_MAX_MS,
  armChoiceHold,
  assertActionPage,
  assertAllWaitersReleasedTogether,
  assertEntryWasResponsive,
  assertNoSessionErrors,
  assertStillHeld,
  assertWaiterReleasedWithLastArriver,
  awaitPossiblyHeldArrival,
  closeHoldSessions,
  createHoldSession,
  enterSkippingHold,
  enterTimelineAfterGateway,
  enterWaitingHold,
  responsesSince,
  startHoldExperiment,
  stopExperiment,
  submitChoiceMaybeHeld,
  submitLastChoice
};
