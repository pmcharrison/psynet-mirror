const fs = require("fs");
const path = require("path");
const { test, expect } = require("./fixtures");

const EARLY_EXIT_JS = fs.readFileSync(
  path.resolve("psynet/resources/scripts/psynet.early-exit.js"),
  "utf8"
);

test(
  "generic error recovery finishes without a redundant participant action",
  { tag: "@both" },
  async ({ page }) => {
    let submittedOffer;
    let completedParticipant;
    await page.route("http://psynet.test/error", async (route) => {
      await route.fulfill({
        contentType: "text/html; charset=utf-8",
        body: `
          <div id="automatic-early-exit"
               data-assignment-id="assignment-1"
               data-participant-id="42"
               data-offer-id="offer-1"
               data-action="close_page">
            <p id="automatic-early-exit-pending">Saving...</p>
            <p id="automatic-early-exit-failure" hidden>Try again.</p>
            <button id="automatic-early-exit-retry" hidden>Try again</button>
            <p id="automatic-early-exit-ready" hidden>
              Your responses have been saved. You may close this page.
            </p>
          </div>
        `
      });
    });
    await page.route(
      "http://psynet.test/set_participant_as_early_exited/assignment-1",
      async (route) => {
        submittedOffer = route.request().postDataJSON();
        await route.fulfill({
          contentType: "application/json",
          body: JSON.stringify({
            release_url: "http://psynet.test/release"
          })
        });
      }
    );
    await page.route("http://psynet.test/worker_complete", async (route) => {
      completedParticipant = Object.fromEntries(
        new URLSearchParams(route.request().postData())
      );
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ status: "success" })
      });
    });

    await page.goto("http://psynet.test/error");
    await page.addScriptTag({ content: EARLY_EXIT_JS });
    await page.evaluate(() => window.psynetEarlyExit.init());

    await expect(page).toHaveURL("http://psynet.test/error");
    await expect(page.locator("#automatic-early-exit-ready")).toBeVisible();
    await expect(page.locator("#automatic-early-exit-continue")).toHaveCount(0);
    expect(submittedOffer).toEqual({ offer_id: "offer-1" });
    expect(completedParticipant).toEqual({ participant_id: "42" });

    await page.waitForTimeout(500);
    await expect(page).toHaveURL("http://psynet.test/error");
  }
);

test(
  "Prolific recovery explains and performs its direct submission",
  { tag: "@both" },
  async ({ page }) => {
    let prolificSubmission;
    await page.route("http://psynet.test/error", async (route) => {
      await route.fulfill({
        contentType: "text/html; charset=utf-8",
        body: `
          <div id="automatic-early-exit"
               data-assignment-id="assignment-1"
               data-participant-id="42"
               data-offer-id="offer-1"
               data-action="post_and_redirect"
               data-post-url="/prolific-submission-listener"
               data-post-data='{"assignmentId":"assignment-1","participantId":"42"}'
               data-redirect-url="http://psynet.test/prolific">
            <p id="automatic-early-exit-pending">Saving...</p>
            <p id="automatic-early-exit-failure" hidden>Try again.</p>
            <button id="automatic-early-exit-retry" hidden>Try again</button>
            <p id="automatic-early-exit-ready" hidden>
              Prolific will pay you £0.25.
            </p>
            <button id="automatic-early-exit-continue" hidden>
              Submit to Prolific
            </button>
          </div>
        `
      });
    });
    await page.route(
      "http://psynet.test/set_participant_as_early_exited/assignment-1",
      async (route) => {
        await route.fulfill({
          contentType: "application/json",
          body: JSON.stringify({
            release_url: "http://psynet.test/release"
          })
        });
      }
    );
    await page.route(
      "http://psynet.test/prolific-submission-listener",
      async (route) => {
        prolificSubmission = Object.fromEntries(
          new URLSearchParams(route.request().postData())
        );
        await route.fulfill({
          contentType: "application/json",
          body: JSON.stringify({ status: "success" })
        });
      }
    );
    await page.route("http://psynet.test/prolific", async (route) => {
      await route.fulfill({
        contentType: "text/html",
        body: "<h1>Prolific</h1>"
      });
    });

    await page.goto("http://psynet.test/error");
    await page.addScriptTag({ content: EARLY_EXIT_JS });
    await page.evaluate(() => window.psynetEarlyExit.init());

    await expect(page.locator("#automatic-early-exit-ready")).toContainText(
      "Prolific will pay you £0.25."
    );
    await expect(page.locator("#automatic-early-exit-continue")).toHaveText(
      "Submit to Prolific"
    );
    expect(prolificSubmission).toBeUndefined();

    await page.locator("#automatic-early-exit-continue").click();
    await expect(page).toHaveURL("http://psynet.test/prolific");
    expect(prolificSubmission).toEqual({
      assignmentId: "assignment-1",
      participantId: "42"
    });
  }
);
