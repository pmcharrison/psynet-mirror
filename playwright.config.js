const headless = String(process.env.HEADLESS || "true").toLowerCase() !== "false";
const timeout = Number(process.env.PLAYWRIGHT_TIMEOUT_MS || 10 * 60 * 1000);

/** @type {import('@playwright/test').PlaywrightTestConfig} */
const config = {
  testDir: "tests/playwright",
  workers: 1,
  timeout,
  retries: 0,
  use: {
    headless,
    viewport: { width: 1024, height: 768 },
    permissions: ["microphone", "camera"],
    launchOptions: {
      args: [
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--autoplay-policy=no-user-gesture-required",
        "--use-fake-device-for-media-stream",
        "--use-fake-ui-for-media-stream",
        "--allow-http-screen-capture",
        "--auto-select-desktop-capture-source=Entire screen",
        "--enable-usermedia-screen-capturing"
      ]
    }
  }
};

module.exports = config;
