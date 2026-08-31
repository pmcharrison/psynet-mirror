const path = require("path");
const { test, expect } = require("./fixtures");

const {
  assertNoBackendError,
  completeInitialGateway,
  startResponseSubmitTracker,
  waitForResponseSubmitIncrement,
  withExperiment
} = require("./psynetHarness");

const STEP_TIMEOUT_MS = 120000;
const HOLD_WAKE_TIMEOUT_MS = 4500;

async function startBackgroundHold(page) {
  await completeInitialGateway(page);
  await expect(page.locator("#main-body")).toContainText(
    "Submit this page to start background feedback processing.",
    { timeout: STEP_TIMEOUT_MS }
  );
  const visiblePageUuid = await page.evaluate(() => window.pageUuid);
  await page.locator("#next-button").click();
  await expect(page.locator("#psynet-timeline-hold-indicator")).toBeVisible({
    timeout: STEP_TIMEOUT_MS
  });
  return visiblePageUuid;
}

test("wait_while preserves the submitted page and wakes after async work", { tag: "@both" }, async ({
  page,
  context
}) => {
  const experimentDir = path.resolve(
    "tests/playwright/experiments/timeline_hold"
  );

  await withExperiment(page, context, experimentDir, async (experimentPage) => {
    const responses = startResponseSubmitTracker(experimentPage);
    const visiblePageUuid = await startBackgroundHold(experimentPage);

    await expect(experimentPage.locator("#main-body")).toContainText(
      "Submit this page to start background feedback processing."
    );
    expect(
      await experimentPage.evaluate(
        (uuid) =>
          window.pageUuid === uuid &&
          psynet.submissionPageUuid !== window.pageUuid &&
          document.getElementById("main-body").inert,
        visiblePageUuid
      )
    ).toBe(true);
    await expect(experimentPage.locator("#comment-button")).toBeDisabled();

    const headerBox = await experimentPage.locator("#timeline-header").boundingBox();
    const indicatorBox = await experimentPage
      .locator("#psynet-timeline-hold-indicator")
      .boundingBox();
    expect(indicatorBox.y).toBeGreaterThanOrEqual(headerBox.y + headerBox.height);

    await experimentPage.waitForTimeout(500);
    const settledResponseCount = responses.getCount();
    await experimentPage.waitForTimeout(700);
    expect(responses.getCount()).toBe(settledResponseCount);

    const blockedBaseline = responses.getCount();
    expect(
      await experimentPage.evaluate(() => psynet.nextPage("unexpected"))
    ).toBe(false);
    await experimentPage.waitForTimeout(200);
    expect(responses.getCount()).toBe(blockedBaseline);

    const pendingBaseline = responses.getCount();
    await experimentPage.evaluate(() => {
      psynet.nextPagePending = true;
      psynet.resumeTimelineHold("test pending request");
      setTimeout(() => {
        psynet.nextPagePending = false;
      }, 200);
    });
    await waitForResponseSubmitIncrement(
      responses,
      pendingBaseline,
      1,
      1000
    );

    await expect(experimentPage.locator("#main-body")).toContainText(
      "Background feedback processing finished.",
      { timeout: HOLD_WAKE_TIMEOUT_MS }
    );
    const accounting = await experimentPage.evaluate(() => ({
      credit: Number(document.getElementById("hold-credit").textContent),
      metric: Number(document.getElementById("hold-metric").textContent)
    }));
    expect(accounting.credit).toBeGreaterThanOrEqual(2.5);
    expect(accounting.credit).toBeLessThanOrEqual(20);
    expect(accounting.metric).toBeGreaterThanOrEqual(accounting.credit);
    await expect(
      experimentPage.locator("#psynet-timeline-hold-indicator")
    ).toHaveCount(0);
    expect(
      await experimentPage.evaluate(
        () =>
          !document.body.classList.contains("timeline-held") &&
          !document.getElementById("main-body").inert
      )
    ).toBe(true);
    await expect(experimentPage.locator("#comment-button")).toBeEnabled();
    responses.stop();
    await assertNoBackendError(experimentPage);
  });
});

test("timeline hold restores its accessible fallback after refresh", { tag: "@both" }, async ({
  page,
  context
}) => {
  const experimentDir = path.resolve(
    "tests/playwright/experiments/timeline_hold"
  );

  await withExperiment(page, context, experimentDir, async (experimentPage) => {
    await startBackgroundHold(experimentPage);
    await experimentPage.reload();

    const indicator = experimentPage.locator("#psynet-timeline-hold-indicator");
    await expect(indicator).toBeVisible({ timeout: STEP_TIMEOUT_MS });
    await expect(indicator).toHaveAttribute("role", "status");
    await expect(indicator).toHaveAttribute("aria-live", "polite");
    expect(
      await experimentPage.evaluate(
        () => !document.getElementById("main-body").inert
      )
    ).toBe(true);

    await expect(experimentPage.locator("#main-body")).toContainText(
      "Background feedback processing finished.",
      { timeout: HOLD_WAKE_TIMEOUT_MS }
    );
    await assertNoBackendError(experimentPage);
  });
});

test("timeline hold uses the authoritative server timeout", { tag: "@both" }, async ({
  page,
  context
}) => {
  const experimentDir = path.resolve(
    "tests/playwright/experiments/timeline_hold_timeout"
  );

  await withExperiment(page, context, experimentDir, async (experimentPage) => {
    await completeInitialGateway(experimentPage);
    await expect(experimentPage.locator("#main-body")).toContainText(
      "Start a timeline hold that will time out.",
      { timeout: STEP_TIMEOUT_MS }
    );
    const startedAt = Date.now();
    await experimentPage.locator("#next-button").click();
    await expect(
      experimentPage.locator("#psynet-timeline-hold-indicator")
    ).toBeVisible({ timeout: STEP_TIMEOUT_MS });
    await expect(experimentPage.locator("#main-body")).toContainText(
      "The timeline hold timed out.",
      { timeout: 3000 }
    );
    const fixedCredit = await experimentPage
      .locator("#fixed-hold-credit")
      .evaluate((element) => Number(element.textContent));
    expect(fixedCredit).toBeCloseTo(0.5);
    expect(Date.now() - startedAt).toBeGreaterThanOrEqual(800);
    await assertNoBackendError(experimentPage);
  });
});

test("timeline hold preserves a reload-required page until release", { tag: "@both" }, async ({
  page,
  context
}) => {
  const experimentDir = path.resolve(
    "tests/playwright/experiments/timeline_hold_reload"
  );

  await withExperiment(page, context, experimentDir, async (experimentPage) => {
    await completeInitialGateway(experimentPage);
    await expect(experimentPage.locator("#main-body")).toContainText(
      "This page requires a full reload after its hold.",
      { timeout: STEP_TIMEOUT_MS }
    );
    await expect
      .poll(
        () =>
          experimentPage.evaluate(
            () => typeof window.holdReloadMarker
          ),
        { timeout: STEP_TIMEOUT_MS }
      )
      .toBe("object");
    const markerPageUuid = await experimentPage.evaluate(
      () => window.holdReloadMarker.pageUuid
    );
    await experimentPage.locator("#next-button").click();
    await expect(
      experimentPage.locator("#psynet-timeline-hold-indicator")
    ).toBeVisible({ timeout: STEP_TIMEOUT_MS });
    expect(
      await experimentPage.evaluate(
        (uuid) =>
          window.holdReloadMarker.pageUuid === uuid &&
          window.pageUuid === uuid,
        markerPageUuid
      )
    ).toBe(true);

    await expect(experimentPage.locator("#main-body")).toContainText(
      "The reload-required hold finished.",
      { timeout: HOLD_WAKE_TIMEOUT_MS }
    );
    expect(
      await experimentPage.evaluate(
        () => typeof window.holdReloadMarker === "undefined"
      )
    ).toBe(true);
    await assertNoBackendError(experimentPage);
  });
});

test("timeline hold preserves same-session page identity", { tag: "@both" }, async ({
  page,
  context
}) => {
  const experimentDir = path.resolve(
    "tests/playwright/experiments/timeline_hold_same_session"
  );

  await withExperiment(page, context, experimentDir, async (experimentPage) => {
    await completeInitialGateway(experimentPage);
    await expect(experimentPage.locator("#hold-session-marker")).toHaveText(
      "First session page",
      { timeout: STEP_TIMEOUT_MS }
    );
    await experimentPage.locator("#next-button").click();
    await expect(
      experimentPage.locator("#psynet-timeline-hold-indicator")
    ).toBeVisible({ timeout: STEP_TIMEOUT_MS });

    await expect
      .poll(
        () =>
          experimentPage.evaluate(() => ({
            messageCount: window.holdSessionMessages.length,
            step: psynet.page.contents.step
          })),
        { timeout: HOLD_WAKE_TIMEOUT_MS }
      )
      .toEqual({ messageCount: 1, step: 2 });
    await expect(experimentPage.locator("#hold-session-marker")).toHaveText(
      "First session page"
    );
    await expect(
      experimentPage.locator("#psynet-timeline-hold-indicator")
    ).toHaveCount(0);
    await assertNoBackendError(experimentPage);
  });
});

test("trial feedback processing uses an in-place timeline hold", { tag: "@both" }, async ({
  page,
  context
}) => {
  const experimentDir = path.resolve(
    "tests/playwright/experiments/timeline_hold_feedback"
  );

  await withExperiment(page, context, experimentDir, async (experimentPage) => {
    await completeInitialGateway(experimentPage);
    await expect(experimentPage.locator("#main-body")).toContainText(
      "Choose a response before feedback processing.",
      { timeout: STEP_TIMEOUT_MS }
    );
    await experimentPage
      .getByRole("button", { name: "response", exact: true })
      .click();

    await expect(
      experimentPage.locator("#psynet-timeline-hold-indicator")
    ).toBeVisible({ timeout: STEP_TIMEOUT_MS });
    await expect(experimentPage.locator("#main-body")).toContainText(
      "Choose a response before feedback processing."
    );
    await expect(experimentPage.locator("#main-body")).toContainText(
      "Asynchronous feedback is ready.",
      { timeout: 5000 }
    );
    await assertNoBackendError(experimentPage);
  });
});
