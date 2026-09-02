/**
 * The audio meter used to sit in a 500px table, which pushed the coloured
 * status text off the edge of a phone. This check renders the theme markup
 * at a phone viewport so a regression does not need a microphone or a
 * full experiment.
 */
const fs = require("fs");
const path = require("path");
const { test, expect } = require("./fixtures");

const PHONE_VIEWPORT = { width: 375, height: 780 };

test(
  "audio meter status text stays inside a phone viewport",
  { tag: "@both" },
  async ({ page }) => {
    const css = fs.readFileSync(
      path.resolve("psynet/resources/css/participant.css"),
      "utf8"
    );

    await page.setViewportSize(PHONE_VIEWPORT);
    await page.setContent(`<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
${css}
body { margin: 0; }
</style>
</head>
<body>
  <div class="psynet-surface">
    <div class="audio-meter-block">
      <div class="audio-meter">
        <div class="audio-meter__canvas-wrap">
          <canvas id="audio-meter" width="300" height="50"></canvas>
        </div>
        <p id="audio-meter-text" class="audio-meter__text" style="display: block; color: red;">Starting audio meter...</p>
      </div>
    </div>
  </div>
</body>
</html>`);

    const metrics = await page.evaluate(() => {
      const text = document.getElementById("audio-meter-text");
      const meter = document.querySelector(".audio-meter");
      const textRect = text.getBoundingClientRect();
      const meterRect = meter.getBoundingClientRect();
      return {
        textRight: textRect.right,
        textLeft: textRect.left,
        meterRight: meterRect.right,
        viewport: window.innerWidth,
        scrollWidth: document.documentElement.scrollWidth
      };
    });

    expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.viewport + 1);
    expect(metrics.textRight).toBeLessThanOrEqual(metrics.viewport);
    expect(metrics.textLeft).toBeGreaterThanOrEqual(0);
    expect(metrics.meterRight).toBeLessThanOrEqual(metrics.viewport);
  }
);
