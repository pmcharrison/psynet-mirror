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
            Ending your session safely...
          </div>
          <button id="automatic-early-exit-retry" hidden>Try again</button>
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

    await expect(page).toHaveURL("http://psynet.test/release");
    await expect(page.locator("h1")).toHaveText("Session ended after an error");
    expect(submittedOffer).toEqual({ offer_id: "offer-1" });
  }
);
