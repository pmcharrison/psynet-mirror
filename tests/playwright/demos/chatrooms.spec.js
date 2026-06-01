const path = require("path");
const { test, expect } = require("@playwright/test");

const {
  assertNoBackendError,
  beginExperiment,
  completeInitialGateway,
  startExperiment,
  stopExperiment,
  withFreshParticipantIds
} = require("../psynetHarness");

const STEP_TIMEOUT_MS = 120000;
const MESSAGE_TIMEOUT_MS = 30000;

/*
Step summary:
1. Start one chatrooms demo backend and create two isolated browser contexts.
2. Each participant clears the gateway/consent flow and joins Room 1.
3. Participant A sends a message; both participants see it in the live chat feed.
4. Participant B replies; both participants see the reply.
5. The test reads chat history through the participant-facing endpoint to verify
   submitted messages were persisted, not just relayed live over WebSocket.

Intentionally not covered:
- Exact occupancy timing for every transient join/leave update.
- Multi-room isolation beyond both participants sharing the same room.
*/

async function waitForRoomSelectionOrConsent(page) {
  const roomButtons = page.locator("#room-buttons button");
  const consentButton = page.locator("#consent");
  const deadline = Date.now() + STEP_TIMEOUT_MS;

  while (Date.now() < deadline) {
    await assertNoBackendError(page);
    if (await roomButtons.first().isVisible().catch(() => false)) {
      return "room-selection";
    }
    if (await consentButton.isVisible().catch(() => false)) {
      return "consent";
    }
    await page.waitForTimeout(250);
  }

  throw new Error("Timed out waiting for room selection or consent page.");
}

async function acceptConsentIfPresent(page) {
  const startupState = await waitForRoomSelectionOrConsent(page);
  if (startupState === "room-selection") {
    return;
  }

  await expect(page.locator("#main-body")).toContainText(
    "We need your consent to proceed",
    { timeout: STEP_TIMEOUT_MS }
  );
  const consentButton = page.locator("#consent");
  await expect(consentButton).toBeVisible({ timeout: STEP_TIMEOUT_MS });
  await expect(consentButton).toBeEnabled({ timeout: STEP_TIMEOUT_MS });
  await consentButton.click();
}

async function joinFirstRoom(page) {
  await completeInitialGateway(page, STEP_TIMEOUT_MS);
  await acceptConsentIfPresent(page);

  const roomButtons = page.locator("#room-buttons button");
  await expect(roomButtons.first()).toBeVisible({ timeout: STEP_TIMEOUT_MS });
  await expect(roomButtons.first()).toBeEnabled({ timeout: STEP_TIMEOUT_MS });
  await roomButtons.first().click();

  await expect(page.locator("#chat-input")).toBeVisible({ timeout: STEP_TIMEOUT_MS });
  await expect(page.locator("#send-btn")).toBeEnabled({ timeout: STEP_TIMEOUT_MS });
  await expect(page.locator("#chatroom-room-label")).toContainText("Room 1", {
    timeout: STEP_TIMEOUT_MS
  });
}

async function waitForOccupancy(page, count) {
  await expect(page.locator("#participant-count")).toHaveText(String(count), {
    timeout: MESSAGE_TIMEOUT_MS
  });
}

async function sendChatMessage(page, content) {
  await page.locator("#chat-input").fill(content);
  await page.locator("#send-btn").click();
  await expect(page.locator("#chat-input")).toHaveValue("", {
    timeout: MESSAGE_TIMEOUT_MS
  });
}

async function expectChatMessage(page, content) {
  await expect(page.locator("#chatroom-messages")).toContainText(content, {
    timeout: MESSAGE_TIMEOUT_MS
  });
}

async function getPersistedMessageContents(page) {
  return page.evaluate(async () => {
    const roomId = String(psynet.var.chatroom_room_id);
    const url =
      `/chatroom_history?room_id=${encodeURIComponent(roomId)}` +
      `&participant_id=${encodeURIComponent(dallinger.identity.participantId)}` +
      `&unique_id=${encodeURIComponent(psynet.uniqueId)}`;
    const response = await fetch(url);
    const data = await response.json();
    return (data.messages || []).map((message) => message.content);
  });
}

async function expectPersistedMessages(page, expectedContents) {
  await expect
    .poll(async () => getPersistedMessageContents(page), {
      timeout: MESSAGE_TIMEOUT_MS
    })
    .toEqual(expect.arrayContaining(expectedContents));
}

test("chatrooms demo relays and persists messages between two participants", async ({
  browser,
  page,
  context
}) => {
  const absDir = path.resolve("demos/experiments/chatrooms");
  const { proc, urlPromise } = startExperiment(absDir);
  const secondContext = await browser.newContext();
  const secondBootstrapPage = await secondContext.newPage();

  try {
    const recruitmentUrl = await urlPromise;
    const participantOnePage = await beginExperiment(
      page,
      context,
      withFreshParticipantIds(recruitmentUrl, "p1")
    );
    const participantTwoPage = await beginExperiment(
      secondBootstrapPage,
      secondContext,
      withFreshParticipantIds(recruitmentUrl, "p2")
    );

    await joinFirstRoom(participantOnePage);
    await joinFirstRoom(participantTwoPage);
    await waitForOccupancy(participantOnePage, 2);
    await waitForOccupancy(participantTwoPage, 2);

    const firstMessage = "Hello from participant one";
    await sendChatMessage(participantOnePage, firstMessage);
    await expectChatMessage(participantOnePage, firstMessage);
    await expectChatMessage(participantTwoPage, firstMessage);

    const secondMessage = "Reply from participant two";
    await sendChatMessage(participantTwoPage, secondMessage);
    await expectChatMessage(participantOnePage, secondMessage);
    await expectChatMessage(participantTwoPage, secondMessage);

    await expectPersistedMessages(participantOnePage, [firstMessage, secondMessage]);
    await expectPersistedMessages(participantTwoPage, [firstMessage, secondMessage]);

    await assertNoBackendError(participantOnePage);
    await assertNoBackendError(participantTwoPage);
  } finally {
    await secondContext.close().catch(() => {});
    await stopExperiment(proc);
  }
});
