const { spawn } = require("child_process");
const fs = require("fs");
const net = require("net");
const path = require("path");
const readline = require("readline");

const RECRUITMENT_URL_RE =
  /http:\/\/(?:localhost|127\.0\.0\.1):\d+\/ad\?recruiter=[a-zA-Z0-9]+&assignmentId=[a-zA-Z0-9]+&hitId=[a-zA-Z0-9]+&workerId=[a-zA-Z0-9]+&mode=debug/;

const PSYNET_ERROR_SELECTORS = ["#error-text", "#error-text-main"];
let latestBackendLogPath = null;
const DEBUG_PORT = Number(process.env.PSYNET_DEBUG_PORT || 5000);

function isPortInUse(port) {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    socket.setTimeout(400);
    socket.once("connect", () => {
      socket.destroy();
      resolve(true);
    });
    const onUnavailable = () => resolve(false);
    socket.once("error", onUnavailable);
    socket.once("timeout", onUnavailable);
    socket.connect(port, "127.0.0.1");
  });
}

async function waitForPortToBeFree(port, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (!(await isPortInUse(port))) {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  return !(await isPortInUse(port));
}

function killProcessTree(proc, signal) {
  if (!proc || !proc.pid) {
    return;
  }
  try {
    process.kill(-proc.pid, signal);
  } catch (error) {
    if (!error || error.code !== "ESRCH") {
      throw error;
    }
  }
}

function isParticipantPageUrl(url) {
  if (!url) {
    return false;
  }
  return /http:\/\/(?:localhost|127\.0\.0\.1):\d+\/(ad|consent|start|timeline|questionnaire|recruiter-exit)\b/.test(
    url
  );
}

async function closeAuxiliaryPages(context, keepPage) {
  for (const existingPage of context.pages()) {
    if (existingPage === keepPage || existingPage.isClosed()) {
      continue;
    }
    if (!isParticipantPageUrl(existingPage.url())) {
      await existingPage.close().catch(() => {});
    }
  }
}

async function resolveParticipantPage(context, fallbackPage, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const pages = context.pages();
    for (const candidate of pages) {
      if (!candidate.isClosed() && isParticipantPageUrl(candidate.url())) {
        return candidate;
      }
    }
    if (!fallbackPage.isClosed() && isParticipantPageUrl(fallbackPage.url())) {
      return fallbackPage;
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  return fallbackPage;
}

function resolvePsynetCommand() {
  if (process.env.PSYNET_CMD) {
    return process.env.PSYNET_CMD;
  }
  const venvPsynet = path.join(process.cwd(), ".venv", "bin", "psynet");
  if (fs.existsSync(venvPsynet)) {
    return venvPsynet;
  }
  return "psynet";
}

function startExperiment(experimentDir) {
  const psynetCmd = resolvePsynetCommand();
  if (!psynetCmd) {
    throw new Error("Unable to resolve psynet command.");
  }
  const logsDir = path.join(process.cwd(), "test-results", "psynet-backend-logs");
  fs.mkdirSync(logsDir, { recursive: true });
  const experimentName = path.basename(experimentDir);
  const logPath = path.join(logsDir, `${experimentName}-${Date.now()}.log`);
  const logStream = fs.createWriteStream(logPath, { flags: "a" });
  latestBackendLogPath = logPath;

  // Auto-reload debug mode can restart while tests are running (e.g., after local
  // recording assets are written), which destabilizes DB state mid-test.
  // Legacy mode avoids those reload cycles and is more reliable for Playwright.
  const args = ["debug", "local", "--legacy"];
  const proc = spawn(psynetCmd, args, {
    detached: true,
    cwd: experimentDir,
    env: {
      ...process.env,
      KEEP_OLD_CHROME_WINDOWS_IN_DEBUG_MODE: "1",
      BROWSER: "false",
      SKIP_PYTHON_VERSION_CHECK: "1",
      SKIP_DEPENDENCY_CHECK: "1"
    },
    stdio: ["ignore", "pipe", "pipe"]
  });

  const outputLines = [];
  let resolveUrl;
  let rejectUrl;
  const urlPromise = new Promise((resolve, reject) => {
    resolveUrl = resolve;
    rejectUrl = reject;
  });

  const handleLine = (line) => {
    outputLines.push(line);
    logStream.write(`${line}\n`);

    if (line.includes("Address already in use")) {
      rejectUrl(
        new Error(
          `Startup failed because port ${DEBUG_PORT} is already in use.\n` +
            `Recent output:\n${outputLines.slice(-50).join("\n")}\n` +
            `Backend log: ${logPath}`
        )
      );
    }
    if (outputLines.length > 200) {
      outputLines.shift();
    }
    const match = line.match(RECRUITMENT_URL_RE);
    if (match) {
      resolveUrl(match[0]);
    }
  };

  const rlOut = readline.createInterface({ input: proc.stdout });
  rlOut.on("line", handleLine);

  const rlErr = readline.createInterface({ input: proc.stderr });
  rlErr.on("line", handleLine);

  const timeoutMs = Number(process.env.PSYNET_RECRUITMENT_TIMEOUT_MS || 120000);
  const timeoutHandle = setTimeout(() => {
    const tail = outputLines.slice(-50).join("\n");
    rejectUrl(
      new Error(
        `Timed out waiting for recruitment URL after ${timeoutMs}ms.\n` +
          `Recent output:\n${tail}\n` +
          `Backend log: ${logPath}`
      )
    );
  }, timeoutMs);

  urlPromise.finally(() => clearTimeout(timeoutHandle));

  proc.on("exit", (code) => {
    logStream.end();
    if (code !== 0) {
      const tail = outputLines.slice(-50).join("\n");
      rejectUrl(
        new Error(
          `psynet debug local exited with code ${code}.\n` +
            `Recent output:\n${tail}\n` +
            `Backend log: ${logPath}`
        )
      );
    }
  });

  return {
    proc,
    urlPromise,
    logPath,
    getRecentOutput: () => outputLines.slice(-50).join("\n")
  };
}

async function stopExperiment(proc) {
  if (!proc) {
    return;
  }

  const waitForExit = (timeoutMs) =>
    new Promise((resolve) => {
      if (proc.exitCode !== null || proc.signalCode !== null) {
        resolve(true);
        return;
      }
      let finished = false;
      const done = (didExit) => {
        if (finished) {
          return;
        }
        finished = true;
        resolve(didExit);
      };
      const timer = setTimeout(() => {
        proc.off("exit", onExit);
        done(false);
      }, timeoutMs);
      const onExit = () => {
        clearTimeout(timer);
        done(true);
      };
      proc.once("exit", onExit);
    });

  let exited = proc.exitCode !== null || proc.signalCode !== null;
  if (!exited) {
    killProcessTree(proc, "SIGINT");
    exited = await waitForExit(3000);
  }

  if (!exited) {
    killProcessTree(proc, "SIGKILL");
    await waitForExit(3000);
  }

  // Detached child processes can outlive the parent; ensure the port is actually free.
  await waitForPortToBeFree(DEBUG_PORT, 10000);
  if (await isPortInUse(DEBUG_PORT)) {
    killProcessTree(proc, "SIGKILL");
    await waitForPortToBeFree(DEBUG_PORT, 10000);
  }
}

async function beginExperiment(page, context, url) {
  await page.goto(url);
  await page.waitForSelector("button.btn-primary", { timeout: 30000 });
  await page.click("button.btn-primary");

  let newPage = null;
  try {
    newPage = await context.waitForEvent("page", { timeout: 2000 });
  } catch (e) {
    newPage = null;
  }

  let targetPage = newPage || page;
  targetPage = await resolveParticipantPage(context, targetPage);
  await targetPage.waitForLoadState("domcontentloaded");
  await closeAuxiliaryPages(context, targetPage);
  return targetPage;
}

async function getPossibleBackendError(page) {
  if (!page || page.isClosed()) {
    return null;
  }

  const details = await page
    .evaluate((selectors) => {
      const hasErrorTemplate = selectors.every(
        (selector) => document.querySelector(selector) !== null
      );
      const title = (document?.title || "").trim();
      const headerText = (document.querySelector("#header")?.textContent || "").trim();
      const errorText = (document.querySelector("#error-text")?.textContent || "").trim();
      const detailText = (
        document.querySelector("#error-text-main")?.textContent || ""
      ).trim();

      return {
        hasErrorTemplate,
        title,
        headerText,
        errorText,
        detailText
      };
    }, PSYNET_ERROR_SELECTORS)
    .catch(() => null);

  if (!details || !details.hasErrorTemplate) {
    return null;
  }

  return {
    title: details.title,
    headerText: details.headerText,
    errorText: details.errorText,
    detailText: details.detailText
  };
}

async function assertNoBackendError(page) {
  const error = await getPossibleBackendError(page);
  if (!error) {
    return;
  }

  throw new Error(
    `PsyNet backend error page detected.\n` +
      `URL: ${page.url()}\n` +
      `Title: ${error.title || "<none>"}\n` +
      `Header: ${error.headerText || "<none>"}\n` +
      `Error text: ${error.errorText || "<none>"}\n` +
      `Details: ${error.detailText || "<none>"}\n` +
      `Backend log: ${latestBackendLogPath || "<unknown>"}`
  );
}

async function acceptConsents(page) {
  const deadlineMs = Date.now() + 90000;
  let settledWithoutConsent = 0;

  while (Date.now() < deadlineMs) {
    await assertNoBackendError(page);
    const consent = page.locator("#consent");
    const consentVisible =
      (await consent.count()) > 0 && (await consent.first().isVisible());

    if (!consentVisible) {
      const onConsentPage = /\/consent\b/.test(page.url());
      if (onConsentPage) {
        await Promise.race([
          page.waitForSelector("#consent", { timeout: 2000 }),
          page.waitForURL((nextUrl) => !/\/consent\b/.test(nextUrl.toString()), {
            timeout: 2000
          })
        ]).catch(() => {});
        continue;
      }

      const readyForExperiment = await page
        .waitForFunction(() => {
          const hasNext = !!document.getElementById("next-button");
          const hasMainBody = !!document.getElementById("main-body");
          const hasPrompt = !!document.getElementById("prompt-text");
          const hasFinish = !!document.getElementById("Finish");
          return hasNext || hasMainBody || hasPrompt || hasFinish;
        }, { timeout: 1500 })
        .then(() => true)
        .catch(() => false);

      if (readyForExperiment) {
        settledWithoutConsent += 1;
        if (settledWithoutConsent >= 2) {
          return;
        }
      } else {
        settledWithoutConsent = 0;
      }

      await page.waitForTimeout(200);
      continue;
    }

    settledWithoutConsent = 0;
    const previousUrl = page.url();

    await consent.first().click({ force: true });

    await Promise.race([
      page.waitForURL((url) => url.toString() !== previousUrl, { timeout: 15000 }),
      page.waitForFunction(() => {
        const button = document.getElementById("consent");
        return !button || button.offsetParent === null;
      }, { timeout: 15000 }),
      page.waitForLoadState("networkidle", { timeout: 15000 })
    ]).catch(() => {});

    await page.waitForTimeout(300);
  }

  throw new Error("Timed out while accepting consent pages.");
}

async function getPageUuid(page) {
  try {
    return await page.evaluate(() => window.pageUuid);
  } catch (e) {
    return null;
  }
}

async function waitForPageChange(page, oldUuid, timeoutMs) {
  if (!oldUuid) {
    await page.waitForTimeout(500);
    return;
  }
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    await assertNoBackendError(page);
    const changed = await page
      .evaluate((uuid) => window.pageUuid && window.pageUuid !== uuid, oldUuid)
      .catch(() => false);
    if (changed) {
      return;
    }
    await page.waitForTimeout(200);
  }
  throw new Error(`Timed out waiting for page change after ${timeoutMs}ms.`);
}

async function kickoffTrial(page) {
  if ((await page.locator("#audio-prompt-play").count()) > 0) {
    if (await page.locator("#audio-prompt-play").isEnabled()) {
      await page.click("#audio-prompt-play", { force: true }).catch(() => {});
    }
  }
  if ((await page.locator("#btn-record-record").count()) > 0) {
    if (await page.locator("#btn-record-record").isEnabled()) {
      await page.click("#btn-record-record", { force: true }).catch(() => {});
    }
  }
  if ((await page.locator("#buttonStart").count()) > 0) {
    if (await page.locator("#buttonStart").isEnabled()) {
      await page.click("#buttonStart", { force: true }).catch(() => {});
    }
  }
}

async function clickNext(page, timeoutMs) {
  const oldUuid = await getPageUuid(page);
  await page.click("#next-button");
  await waitForPageChange(page, oldUuid, timeoutMs);
}

async function clickNextAndWait(page, timeoutMs = 60000) {
  await waitForNextEnabled(page, timeoutMs);
  await clickNext(page, timeoutMs);
}

async function waitForNextEnabled(page, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    await assertNoBackendError(page);
    const isEnabled = await page
      .evaluate(() => {
        const btn = document.getElementById("next-button");
        return !!btn && !btn.hasAttribute("disabled");
      })
      .catch(() => false);
    if (isEnabled) {
      return;
    }
    await page.waitForTimeout(200);
  }
  throw new Error(`Timed out waiting for next button to be enabled after ${timeoutMs}ms.`);
}

async function clickAudioPlay(page) {
  if ((await page.locator("#audio-prompt-play").count()) > 0) {
    await page.click("#audio-prompt-play", { force: true });
    return true;
  }
  return false;
}

async function clickRecord(page) {
  if ((await page.locator("#btn-record-record").count()) > 0) {
    await page.click("#btn-record-record", { force: true });
    return true;
  }
  return false;
}

async function clickStartButton(page) {
  if ((await page.locator("#buttonStart").count()) > 0) {
    await page.click("#buttonStart", { force: true });
    return true;
  }
  return false;
}

async function submitAnswerAndWait(page, answer, timeoutMs = 60000) {
  const oldUuid = await getPageUuid(page);
  await page.waitForFunction(
    () => typeof psynet !== "undefined" && typeof psynet.nextPage === "function",
    null,
    { timeout: Math.min(timeoutMs, 15000) }
  );
  await page.evaluate((payload) => psynet.nextPage(payload), answer);
  await waitForPageChange(page, oldUuid, timeoutMs);
}

async function getPromptText(page) {
  const prompt = page.locator("#prompt-text");
  if ((await prompt.count()) === 0) {
    return "";
  }
  return (await prompt.first().innerText()).trim();
}

async function advanceOneStep(page, options = {}) {
  const timeoutMs = options.timeoutMs ?? 60000;
  await acceptConsents(page);

  const nextButton = page.locator("#next-button");
  if ((await nextButton.count()) === 0) {
    return false;
  }

  if (!(await nextButton.isEnabled())) {
    await kickoffTrial(page);
    await waitForNextEnabled(page, Math.min(timeoutMs, 15000)).catch(() => {});
  }

  if (!(await nextButton.isEnabled())) {
    return false;
  }

  await clickNext(page, timeoutMs);
  return true;
}

async function advanceUntilPromptContains(page, text, options = {}) {
  const maxSteps = options.maxSteps ?? 20;
  const stallLimit = options.stallLimit ?? 6;
  const timeoutMs = options.timeoutMs ?? 60000;
  let stalledAttempts = 0;

  for (let step = 0; step < maxSteps; step += 1) {
    const promptText = await getPromptText(page);
    if (promptText.includes(text)) {
      return;
    }

    const progressed = await advanceOneStep(page, { timeoutMs });
    if (progressed) {
      stalledAttempts = 0;
      continue;
    }

    stalledAttempts += 1;
    if (stalledAttempts >= stallLimit) {
      throw new Error(
        `Could not progress to prompt containing "${text}". Current prompt: "${promptText}".`
      );
    }
    await page.waitForTimeout(1000);
  }

  throw new Error(`Did not reach prompt containing "${text}" within ${maxSteps} steps.`);
}

async function withExperiment(page, context, experimentDir, runTest) {
  const { proc, urlPromise } = startExperiment(experimentDir);
  let experimentPage = null;
  try {
    const url = await urlPromise;
    experimentPage = await beginExperiment(page, context, url);
    await acceptConsents(experimentPage);
    return await runTest(experimentPage);
  } finally {
    if (experimentPage && !experimentPage.isClosed()) {
      await experimentPage.goto("about:blank").catch(() => {});
    }
    await stopExperiment(proc);
  }
}

async function clickFinish(page, timeoutMs) {
  await page.click("#Finish");
  await page.waitForFunction(
    () => window.location.href.includes("recruiter-exit"),
    { timeout: timeoutMs }
  ).catch(() => {});
}

async function advanceUntilFinish(page, options = {}) {
  const maxSteps = options.maxSteps ?? 120;
  const timeoutMs = options.timeoutMs ?? 90000;

  for (let i = 0; i < maxSteps; i += 1) {
    await acceptConsents(page);

    const finish = page.locator("#Finish");
    if ((await finish.count()) > 0 && (await finish.isVisible())) {
      await clickFinish(page, timeoutMs);
      return;
    }

    const nextButton = page.locator("#next-button");
    if ((await nextButton.count()) > 0) {
      if (await nextButton.isEnabled()) {
        await clickNext(page, timeoutMs);
        continue;
      }
      const oldUuid = await getPageUuid(page);
      await kickoffTrial(page);
      await page.waitForTimeout(1000);
      if (await nextButton.isEnabled()) {
        await clickNext(page, timeoutMs);
        continue;
      }

      // Some pages (e.g., recording/upload pages) need real-time processing before
      // the next button becomes available. Wait for natural readiness.
      await waitForNextEnabled(page, Math.min(timeoutMs, 30000)).catch(() => {});
      if (await nextButton.isEnabled()) {
        await clickNext(page, timeoutMs);
        continue;
      }

      const changed = await page
        .evaluate((uuid) => !!window.pageUuid && window.pageUuid !== uuid, oldUuid)
        .catch(() => false);
      if (changed) {
        continue;
      }

      await assertNoBackendError(page);
      await page.waitForTimeout(500);
      continue;
    }

    const oldUuid = await getPageUuid(page);
    await kickoffTrial(page);
    await waitForPageChange(page, oldUuid, Math.min(timeoutMs, 30000)).catch(
      () => {}
    );
    const changed = await page
      .evaluate((uuid) => !!window.pageUuid && window.pageUuid !== uuid, oldUuid)
      .catch(() => false);
    if (changed) {
      continue;
    }
    await assertNoBackendError(page);
    await page.waitForTimeout(500);
  }

  throw new Error("Experiment did not finish within expected steps.");
}

module.exports = {
  advanceUntilFinish,
  advanceUntilPromptContains,
  advanceOneStep,
  assertNoBackendError,
  beginExperiment,
  acceptConsents,
  clickAudioPlay,
  clickNextAndWait,
  clickRecord,
  clickStartButton,
  getPromptText,
  getPageUuid,
  submitAnswerAndWait,
  startExperiment,
  stopExperiment,
  withExperiment,
  waitForNextEnabled,
  waitForPageChange
};
