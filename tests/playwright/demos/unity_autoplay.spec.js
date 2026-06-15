const path = require("path");
const { test, expect } = require("../fixtures");

const {
  clickConsentButton,
  completeInitialGateway,
  waitForTimelinePageReady,
  withExperiment
} = require("../psynetHarness");

const STEP_TIMEOUT_MS = 120000;

test("unity_autoplay demo handles same-session page updates in real WebGL build", async ({
  page,
  context
}) => {
  const absDir = path.resolve("demos/experiments/unity_autoplay");

  await withExperiment(page, context, absDir, async (experimentPage) => {
    await completeInitialGateway(experimentPage, STEP_TIMEOUT_MS);
    await expect(experimentPage.locator("#main-body")).toContainText(
      "We need your consent to proceed",
      { timeout: STEP_TIMEOUT_MS }
    );
    await clickConsentButton(experimentPage, STEP_TIMEOUT_MS);

    await expect(experimentPage.locator("#unity-canvas")).toBeVisible({
      timeout: STEP_TIMEOUT_MS
    });
    await experimentPage.evaluate(() => {
      window.__realUnityMessages = [];
      window.__realUnityNextPageCalls = [];

      const originalNextPage = window.psynet.nextPage.bind(window.psynet);
      window.psynet.nextPage = function (rawAnswer, metadata, blobs, onRejection) {
        const rewrittenAnswer =
          window.__realUnityNextPageCalls.length === 0 &&
          rawAnswer &&
          rawAnswer.expire === true
            ? { ...rawAnswer, expire: false }
            : rawAnswer;
        window.__realUnityNextPageCalls.push({
          rawAnswer,
          rewrittenAnswer
        });
        return originalNextPage(rewrittenAnswer, metadata, blobs, onRejection);
      };

      const wrapUnitySendMessage = window.setInterval(() => {
        if (
          typeof unityInstance === "undefined" ||
          !unityInstance ||
          typeof unityInstance.SendMessage !== "function" ||
          unityInstance.__psynetPlaywrightWrapped
        ) {
          return;
        }

        const originalSendMessage = unityInstance.SendMessage.bind(unityInstance);
        unityInstance.SendMessage = function (objectName, methodName, payload) {
          window.__realUnityMessages.push({
            objectName,
            methodName,
            payload: JSON.parse(payload)
          });
          return originalSendMessage(objectName, methodName, payload);
        };
        unityInstance.__psynetPlaywrightWrapped = true;
        window.clearInterval(wrapUnitySendMessage);
      }, 20);
    });

    const initialState = await experimentPage.evaluate(() => ({
      pageUuid: window.pageUuid,
      sessionId: window.psynet.page.attributes?.session_id || null
    }));

    await expect(experimentPage.locator("#unity-loading-bar")).toBeHidden({
      timeout: STEP_TIMEOUT_MS
    });
    await waitForTimelinePageReady(experimentPage, STEP_TIMEOUT_MS);

    await expect
      .poll(
        () =>
          experimentPage.evaluate(() => ({
            pageUuid: window.pageUuid,
            sessionId: window.psynet.page.attributes?.session_id || null,
            messageCount: window.__realUnityMessages?.length || 0,
            nextPageCalls: window.__realUnityNextPageCalls?.length || 0,
            latestPayload:
              window.__realUnityMessages?.[window.__realUnityMessages.length - 1]
                ?.payload || null,
            nextPagePending: window.psynet.nextPagePending
          })),
        { timeout: STEP_TIMEOUT_MS }
      )
      .toMatchObject({
        pageUuid: initialState.pageUuid,
        sessionId: initialState.sessionId || "0",
        messageCount: 1,
        nextPageCalls: 1,
        nextPagePending: false
      });

    const update = await experimentPage.evaluate(
      () => window.__realUnityMessages[0]
    );
    expect(update.objectName).toBe("PsynetObj");
    expect(update.methodName).toBe("GetData");
    expect(update.payload.attributes.session_id).toBe(initialState.sessionId || "0");
    expect(update.payload.contents).toHaveProperty("goal");
    expect(update.payload.contents).toHaveProperty("gain");
    await expect(experimentPage.locator("#unity-canvas")).toBeVisible();
  });
});
