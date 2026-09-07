const fs = require("fs");
const path = require("path");
const { test, expect } = require("./fixtures");

const EARLY_EXIT_JS = fs.readFileSync(
  path.resolve("psynet/resources/scripts/psynet.early-exit.js"),
  "utf8"
);

test(
  "an error recovery plan executes without asking the participant",
  { tag: "@both" },
  async ({ page }) => {
    let submittedOffer;
    await page.route("http://psynet.test/error", async (route) => {
      await route.fulfill({
        contentType: "text/html",
        body: `
          <div id="automatic-early-exit"
               data-assignment-id="assignment-1"
               data-offer-id="offer-1">
            <p id="automatic-early-exit-pending">Ending your session safely...</p>
            <p id="automatic-early-exit-failure" hidden>Try again.</p>
            <button id="automatic-early-exit-retry" hidden>Try again</button>
            <p id="automatic-early-exit-ready" hidden>
              Your session is ready to finish.
            </p>
            <button id="automatic-early-exit-continue" hidden>
              Finish session
            </button>
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
    await page.route("http://psynet.test/release", async (route) => {
      await route.fulfill({
        contentType: "text/html",
        body: "<h1>Session ended after an error</h1>"
      });
    });

    await page.goto("http://psynet.test/error");
    await page.addScriptTag({ content: EARLY_EXIT_JS });
    await page.evaluate(() => window.psynetEarlyExit.init());

    await expect(page).toHaveURL("http://psynet.test/error");
    await expect(page.locator("#automatic-early-exit-ready")).toBeVisible();
    await expect(page.locator("#automatic-early-exit-continue")).toBeVisible();
    expect(submittedOffer).toEqual({ offer_id: "offer-1" });

    await page.locator("#automatic-early-exit-continue").click();
    await expect(page).toHaveURL("http://psynet.test/release");
    await expect(page.locator("h1")).toHaveText("Session ended after an error");
  }
);
