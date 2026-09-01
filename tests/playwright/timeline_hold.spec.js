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
const HOLD_WAKE_TIMEOUT_MS = 10000;

async function startBackgroundHold(page, { trackLucidUnload = false } = {}) {
  await completeInitialGateway(page);
  await expect(page.locator("#main-body")).toContainText(
    "Submit this page to start background feedback processing.",
    { timeout: STEP_TIMEOUT_MS }
  );
  if (trackLucidUnload) {
    await page.evaluate(() => {
      window.beforeUnloadOperations = [];
      const originalAddEventListener = window.addEventListener.bind(window);
      const originalRemoveEventListener =
        window.removeEventListener.bind(window);
      window.addEventListener = function (type, ...args) {
        if (type === "beforeunload") window.beforeUnloadOperations.push("add");
        return originalAddEventListener(type, ...args);
      };
      window.removeEventListener = function (type, ...args) {
        if (type === "beforeunload") {
          window.beforeUnloadOperations.push("remove");
        }
        return originalRemoveEventListener(type, ...args);
      };
      psynetTemplateData.flags.lucidRecruitment = true;
      Object.assign(psynetTemplateData.lucid, {
        inactivityTimeoutMs: 600000,
        inactivityTimeoutS: 600,
        noFocusTimeoutMs: 600000,
        noFocusTimeoutReason: "no-focus-",
        overallTimeoutS: 600,
        secondsLeft: 600,
        shouldWarnOnBeforeUnload: true
      });
      psynet.initLucidTermination();
    });
  }
  const visiblePageUuid = await page.evaluate(() => window.pageUuid);
  const mainBodyTop = await page
    .locator("#main-body")
    .evaluate((element) => element.getBoundingClientRect().top + window.scrollY);
  await page.locator("#next-button").click();
  await expect(page.locator("#psynet-timeline-hold-indicator")).toBeVisible({
    timeout: STEP_TIMEOUT_MS
  });
  return { visiblePageUuid, mainBodyTop };
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
    await experimentPage.addInitScript(() => {
      if (!["http:", "https:"].includes(location.protocol)) return;
      if (sessionStorage.getItem("timelineHoldWakeCount") === null) {
        sessionStorage.setItem("timelineHoldWakeCount", "0");
      }
      window.addEventListener("timelineHoldWakeReceived", () => {
        const count = Number(sessionStorage.getItem("timelineHoldWakeCount"));
        sessionStorage.setItem("timelineHoldWakeCount", String(count + 1));
      });
    });
    const { visiblePageUuid, mainBodyTop } = await startBackgroundHold(
      experimentPage,
      { trackLucidUnload: true }
    );

    await expect(experimentPage.locator("#main-body")).toContainText(
      "Submit this page to start background feedback processing."
    );
    await expect
      .poll(() =>
        experimentPage.evaluate(
          () => window.beforeUnloadOperations.at(-1)
        )
      )
      .toBe("add");
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

    // The indicator floats, so the preserved page must not shift when it appears.
    const holdLayout = await experimentPage.evaluate(() => {
      const mainBody = document.getElementById("main-body");
      const header = document.getElementById("timeline-header");
      const region = document.getElementById("timeline-hold-region");
      return {
        mainBodyTop: mainBody.getBoundingClientRect().top + window.scrollY,
        regionPosition: getComputedStyle(region).position,
        indicatorTop: document
          .getElementById("psynet-timeline-hold-indicator")
          .getBoundingClientRect().top,
        headerBottom: header.getBoundingClientRect().bottom
      };
    });
    expect(holdLayout.mainBodyTop).toBeCloseTo(mainBodyTop, 1);
    expect(holdLayout.regionPosition).toBe("fixed");
    expect(holdLayout.indicatorTop).toBeGreaterThanOrEqual(
      holdLayout.headerBottom
    );

    await experimentPage.waitForTimeout(500);
    const settledResponseCount = responses.getCount();
    await experimentPage.waitForTimeout(700);
    expect(responses.getCount()).toBeLessThanOrEqual(
      settledResponseCount + 1
    );

    const blockedBaseline = responses.getCount();
    expect(
      await experimentPage.evaluate(() => psynet.nextPage("unexpected"))
    ).toBe(false);
    await experimentPage.waitForTimeout(200);
    expect(responses.getCount()).toBe(blockedBaseline);

    const rejectedHoldEffects = await experimentPage.evaluate(async () => {
      const originalAlert = psynet.alert;
      const originalResponseEnable = psynet.response.enable;
      const originalSubmitEnable = psynet.submit.enable;
      const effects = { alerts: 0, responseEnables: 0, submitEnables: 0 };
      psynet.alert = () => {
        effects.alerts += 1;
      };
      psynet.response.enable = () => {
        effects.responseEnables += 1;
      };
      psynet.submit.enable = () => {
        effects.submitEnables += 1;
      };
      await psynet.handleRejectedResponse(
        { message: "Rejected hold check" },
        undefined,
        { timelineHoldResume: true }
      );
      psynet.alert = originalAlert;
      psynet.response.enable = originalResponseEnable;
      psynet.submit.enable = originalSubmitEnable;
      return effects;
    });
    expect(rejectedHoldEffects).toEqual({
      alerts: 0,
      responseEnables: 0,
      submitEnables: 0
    });

    const busyHoldEffects = await experimentPage.evaluate(async () => {
      const originalAlert = psynet.alert;
      const originalResponseEnable = psynet.response.enable;
      const originalSubmitEnable = psynet.submit.enable;
      const effects = { alerts: 0, responseEnables: 0, submitEnables: 0 };
      psynet.alert = () => {
        effects.alerts += 1;
      };
      psynet.response.enable = () => {
        effects.responseEnables += 1;
      };
      psynet.submit.enable = () => {
        effects.submitEnables += 1;
      };
      const request = {
        status: 503,
        response: JSON.stringify({
          status: "busy",
          submission: "busy",
          message: "The experiment is temporarily busy. Please try again."
        })
      };
      const isBusy = psynet.isBusyResponse(request);
      await psynet.handleBusyResponse(request, { timelineHoldResume: true });
      psynet.alert = originalAlert;
      psynet.response.enable = originalResponseEnable;
      psynet.submit.enable = originalSubmitEnable;
      return { isBusy, ...effects };
    });
    expect(busyHoldEffects).toEqual({
      isBusy: true,
      alerts: 0,
      responseEnables: 0,
      submitEnables: 0
    });

    const pendingBaseline = responses.getCount();
    await experimentPage.evaluate(() => {
      psynet.timelineHold.hold.safety_poll_ms = 100;
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
      2000
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
    expect(accounting.metric).toBeCloseTo(accounting.credit, 5);
    expect(
      await experimentPage.evaluate(
        () => Number(sessionStorage.getItem("timelineHoldWakeCount"))
      )
    ).toBeGreaterThanOrEqual(1);
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
    // Same-session updates keep the existing DOM; hold resume must re-enable
    // controls (Unity listens for pageUpdated; HTML Next is for non-Unity use).
    await expect(experimentPage.locator("#next-button")).toBeEnabled();
    const controlsDisabled = await experimentPage.evaluate(() => ({
      next: document.querySelector("#next-button")?.disabled ?? null,
      response: document.querySelector(".response")?.disabled ?? null,
    }));
    expect(controlsDisabled.next).toBe(false);
    await expect(
      experimentPage.locator("#intentionally-disabled-response")
    ).toBeDisabled();
    await expect(experimentPage.locator("#next-button-spinner")).toBeHidden();
    await expect(experimentPage.locator("#next-button-text")).toBeVisible();
    const nextButtonInlineSize = await experimentPage
      .locator("#next-button")
      .evaluate((button) => ({
        height: button.style.height,
        width: button.style.width
      }));
    expect(nextButtonInlineSize).toEqual({ height: "", width: "" });
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
