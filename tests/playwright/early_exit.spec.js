const fs = require("fs");
const path = require("path");
const { test, expect } = require("./fixtures");

const EARLY_EXIT_JS = fs.readFileSync(
  path.resolve("psynet/resources/scripts/psynet.early-exit.js"),
  "utf8"
);

test(
  "untracked error recovery does not execute an exit plan",
  { tag: "@both" },
  async ({ page }) => {
    let executeRequests = 0;
    let completionAttempts = 0;
    await page.route("http://psynet.test/error", async (route) => {
      await route.fulfill({
        contentType: "text/html; charset=utf-8",
        body: `
          <div id="automatic-early-exit"
               data-assignment-id="assignment-1"
               data-offer-id=""
               data-preparation-post-url="">
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
    await page.route("**/execute_early_exit_plan/**", async (route) => {
      executeRequests += 1;
      await route.abort();
    });
    await page.route("http://psynet.test/worker_complete", async (route) => {
      completionAttempts += 1;
      await route.abort();
    });

    await page.goto("http://psynet.test/error");
    await page.addScriptTag({ content: EARLY_EXIT_JS });
    await page.evaluate(() => window.psynetEarlyExit.init());

    await expect(page.locator("#automatic-early-exit-ready")).toBeVisible();
    await expect(page.locator("#automatic-early-exit-continue")).toHaveCount(0);
    expect(executeRequests).toBe(0);
    expect(completionAttempts).toBe(0);
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
               data-offer-id="offer-1"
               data-action-post-url="/prolific-submission-listener"
               data-action-post-data='{"assignmentId":"assignment-1","participantId":"42"}'>
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
      "http://psynet.test/execute_early_exit_plan/assignment-1",
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
    await page.route("http://psynet.test/release", async (route) => {
      await route.fulfill({
        contentType: "text/html; charset=utf-8",
        body: "<p>Your participation has been recorded. You may close this page.</p>"
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
    await expect(page).toHaveURL("http://psynet.test/release");
    await expect(page.locator("p")).toHaveText(
      "Your participation has been recorded. You may close this page."
    );
    expect(prolificSubmission).toEqual({
      assignmentId: "assignment-1",
      participantId: "42"
    });
  }
);

test(
  "Lucid recovery keeps its readable page before redirecting",
  { tag: "@both" },
  async ({ page }) => {
    await page.route("http://psynet.test/error", async (route) => {
      await route.fulfill({
        contentType: "text/html; charset=utf-8",
        body: `
          <h1>An error occurred</h1>
          <p>We're sorry, but an error means you cannot continue with this study.</p>
          <div id="automatic-early-exit"
               data-assignment-id="rid-1"
               data-offer-id="offer-1"
               data-destination-url="http://psynet.test/lucid"
               data-auto-redirect-delay-ms="250">
            <div id="automatic-early-exit-pending">Loading</div>
            <p id="automatic-early-exit-failure" hidden>Try again.</p>
            <button id="automatic-early-exit-retry" hidden>Try again</button>
            <p id="automatic-early-exit-ready" hidden>
              Your responses have been saved. We will return you to your panel
              provider in a few seconds.
            </p>
            <button id="automatic-early-exit-continue" hidden>
              Return to your panel
            </button>
          </div>
        `
      });
    });
    await page.route(
      "http://psynet.test/execute_early_exit_plan/rid-1",
      async (route) => {
        await route.fulfill({
          contentType: "application/json",
          body: JSON.stringify({
            release_url: "http://psynet.test/release"
          })
        });
      }
    );
    await page.route("http://psynet.test/lucid", async (route) => {
      await route.fulfill({
        contentType: "text/html",
        body: "<h1>Lucid</h1>"
      });
    });

    await page.goto("http://psynet.test/error");
    await page.addScriptTag({ content: EARLY_EXIT_JS });
    await page.evaluate(() => window.psynetEarlyExit.init());

    await expect(page.locator("#automatic-early-exit-ready")).toBeVisible();
    await expect(page.locator("#automatic-early-exit-continue")).toHaveText(
      "Return to your panel"
    );
    await expect(page).toHaveURL("http://psynet.test/lucid");
  }
);

test(
  "untracked Lucid errors use the same redirect presentation without an exit plan",
  { tag: "@both" },
  async ({ page }) => {
    let executeRequests = 0;
    await page.route("http://psynet.test/error", async (route) => {
      await route.fulfill({
        contentType: "text/html; charset=utf-8",
        body: `
          <div id="automatic-early-exit"
               data-assignment-id="rid-1"
               data-offer-id=""
               data-destination-url="http://psynet.test/lucid"
               data-auto-redirect-delay-ms="100">
            <div id="automatic-early-exit-pending">Loading</div>
            <p id="automatic-early-exit-failure" hidden></p>
            <button id="automatic-early-exit-retry" hidden>Try again</button>
            <p id="automatic-early-exit-ready" hidden>
              We will return you to your panel provider in a few seconds.
            </p>
            <button id="automatic-early-exit-continue" hidden>
              Return to your panel
            </button>
          </div>
        `
      });
    });
    await page.route("**/execute_early_exit_plan/**", async (route) => {
      executeRequests += 1;
      await route.abort();
    });
    await page.route("http://psynet.test/lucid", async (route) => {
      await route.fulfill({
        contentType: "text/html",
        body: "<h1>Lucid</h1>"
      });
    });

    await page.goto("http://psynet.test/error");
    await page.addScriptTag({ content: EARLY_EXIT_JS });
    await page.evaluate(() => window.psynetEarlyExit.init());

    await expect(page.locator("#automatic-early-exit-ready")).toBeVisible();
    await expect(page).toHaveURL("http://psynet.test/lucid");
    expect(executeRequests).toBe(0);
  }
);

test(
  "errors reach a reloadable timeline recovery page instead of a resubmittable form",
  { tag: "@both" },
  async ({ page }) => {
    const methods = [];
    await page.route("http://psynet.test/start", async (route) => {
      await route.fulfill({
        contentType: "text/html; charset=utf-8",
        body: "<h1>Start</h1>"
      });
    });
    await page.route("http://psynet.test/timeline**", async (route) => {
      methods.push(route.request().method());
      await route.fulfill({
        contentType: "text/html; charset=utf-8",
        body: "<h1>An error occurred</h1>"
      });
    });

    await page.goto("http://psynet.test/start");
    await page.addScriptTag({ content: EARLY_EXIT_JS });
    await Promise.all([
      page.waitForURL(
        "http://psynet.test/timeline?unique_id=worker-1%3Aassignment-1"
      ),
      // Deferred so the navigation does not tear down this evaluation.
      page.evaluate(() =>
        setTimeout(
          () =>
            window.psynetErrorPage.go({
              uniqueId: "worker-1:assignment-1"
            }),
          0
        )
      )
    ]);

    // A POST-rendered page would prompt the participant to confirm
    // resubmission here rather than simply loading again.
    await page.reload();
    await expect(page.locator("h1")).toHaveText("An error occurred");
    expect(methods).toEqual(["GET", "GET"]);

    // The failed page is replaced rather than pushed, so Back cannot revive it.
    await page.goBack();
    await expect(page).not.toHaveURL(/timeline/);
  }
);

test(
  "automatic recovery does not loop on a stale offer",
  { tag: "@both" },
  async ({ page }) => {
    let pageLoads = 0;
    await page.route("http://psynet.test/error", async (route) => {
      pageLoads += 1;
      await route.fulfill({
        contentType: "text/html; charset=utf-8",
        body: `
          <div id="automatic-early-exit"
               data-assignment-id="assignment-1"
               data-offer-id="stale">
            <div id="automatic-early-exit-pending">Loading</div>
            <p id="automatic-early-exit-failure" hidden>Try again.</p>
            <button id="automatic-early-exit-retry" hidden>Try again</button>
            <p id="automatic-early-exit-ready" hidden>Done.</p>
            <button id="automatic-early-exit-continue" hidden>Continue</button>
          </div>
        `
      });
    });
    await page.route(
      "http://psynet.test/execute_early_exit_plan/assignment-1",
      async (route) => {
        await route.fulfill({
          status: 409,
          contentType: "application/json",
          body: JSON.stringify({ error_code: "stale_early_exit_offer" })
        });
      }
    );

    await page.goto("http://psynet.test/error");
    await page.addScriptTag({ content: EARLY_EXIT_JS });
    await page.evaluate(() => window.psynetEarlyExit.init());

    await page.locator("#automatic-early-exit-continue").click();
    await expect(page.locator("#automatic-early-exit-failure")).toBeVisible();
    expect(pageLoads).toBe(1);

    await page.locator("#automatic-early-exit-retry").click();
    await expect.poll(() => pageLoads).toBe(2);
  }
);
