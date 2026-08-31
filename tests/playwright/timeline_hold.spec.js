const path = require("path");
const { test, expect } = require("./fixtures");

const {
  assertNoBackendError,
  completeInitialGateway,
  startResponseSubmitTracker,
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

    const headerBox = await experimentPage.locator("#timeline-header").boundingBox();
    const indicatorBox = await experimentPage
      .locator("#psynet-timeline-hold-indicator")
      .boundingBox();
    expect(indicatorBox.y).toBeGreaterThanOrEqual(headerBox.y + headerBox.height);

    await experimentPage.waitForTimeout(500);
    const settledResponseCount = responses.getCount();
    await experimentPage.waitForTimeout(700);
    expect(responses.getCount()).toBe(settledResponseCount);

    await expect(experimentPage.locator("#main-body")).toContainText(
      "Background feedback processing finished.",
      { timeout: HOLD_WAKE_TIMEOUT_MS }
    );
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
    expect(Date.now() - startedAt).toBeGreaterThanOrEqual(800);
    await assertNoBackendError(experimentPage);
  });
});
