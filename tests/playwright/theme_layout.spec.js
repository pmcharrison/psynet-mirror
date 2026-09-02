/**
 * Layout contracts from the default-theme review that can be checked without
 * a running experiment: graphic size on a short landscape phone, vertical
 * push-button columns, footer clearance on pages without a footer, caption
 * contrast for color "white", and audio-meter setLevel/applyColor.
 */
const fs = require("fs");
const path = require("path");
const { test, expect } = require("./fixtures");

const THEME_CSS = fs.readFileSync(
  path.resolve("psynet/resources/css/participant.css"),
  "utf8"
);
const AUDIO_METER_JS = fs.readFileSync(
  path.resolve("psynet/templates/macros/control/audio_meter.js"),
  "utf8"
);

async function renderTheme(page, { html, extraCss = "", viewport, scripts = [], htmlAttrs = "" }) {
  await page.setViewportSize(viewport);
  await page.setContent(`<!doctype html>
<html ${htmlAttrs}>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
${THEME_CSS}
body { margin: 0; }
${extraCss}
</style>
</head>
<body>
${html}
</body>
</html>`);
  for (const script of scripts) {
    await page.addScriptTag({ content: script });
  }
}

test(
  "landscape graphics stay visible on a short phone",
  { tag: "@both" },
  async ({ page }) => {
    const aspect = (16 / 9).toFixed(6);
    await renderTheme(page, {
      viewport: { width: 780, height: 375 },
      html: `
        <div class="psynet-surface">
          <div id="graphic-prompt" style="
            width: min(90.0000vw, 100%, calc(60.0000vh * ${aspect}),
              max(var(--psynet-graphic-min-size),
              calc((100vh - var(--psynet-graphic-vertical-chrome)) * ${aspect})));
            aspect-ratio: 16 / 9;
            height: auto;
            background: #dfe5ee;
          "></div>
        </div>`
    });

    const box = await page.locator("#graphic-prompt").boundingBox();
    expect(box).not.toBeNull();
    expect(box.width).toBeGreaterThan(80);
    expect(box.height).toBeGreaterThan(40);
    expect(box.width / box.height).toBeCloseTo(16 / 9, 2);
  }
);

test(
  "vertical push-button lists stay in one scrolling column",
  { tag: "@both" },
  async ({ page }) => {
    const buttons = Array.from(
      { length: 20 },
      (_, i) => `<button type="button" class="push-button">Option ${i + 1}</button>`
    ).join("");
    await renderTheme(page, {
      viewport: { width: 1280, height: 720 },
      extraCss: `.push-button { min-height: 40px; min-width: 220px; }`,
      html: `<div class="push-button-container push-button-container--vertical">${buttons}</div>`
    });

    const metrics = await page.evaluate(() => {
      const container = document.querySelector(".push-button-container");
      const buttons = [...document.querySelectorAll(".push-button")];
      const lefts = buttons.map((button) => Math.round(button.getBoundingClientRect().left));
      return {
        uniqueLefts: [...new Set(lefts)].length,
        scrollHeight: container.scrollHeight,
        clientHeight: container.clientHeight,
        count: buttons.length
      };
    });

    expect(metrics.count).toBe(20);
    expect(metrics.uniqueLefts).toBe(1);
    expect(metrics.scrollHeight).toBeGreaterThan(metrics.clientHeight);
  }
);

test(
  "pages without a footer do not reserve footer clearance",
  { tag: "@both" },
  async ({ page }) => {
    await renderTheme(page, {
      viewport: { width: 1280, height: 720 },
      html: `
        <div class="container d-flex align-items-center justify-content-center" style="min-height: 90vh">
          <div class="psynet-surface">
            <h3>To proceed, click the button below.</h3>
            <button type="button" class="btn btn-primary">Next</button>
          </div>
        </div>`
    });

    const noFooter = await page.evaluate(() => ({
      paddingBottom: getComputedStyle(document.body).paddingBottom,
      scrollHeight: document.documentElement.scrollHeight,
      viewport: window.innerHeight
    }));
    expect(parseFloat(noFooter.paddingBottom)).toBe(0);
    expect(noFooter.scrollHeight).toBeLessThanOrEqual(noFooter.viewport + 1);

    await renderTheme(page, {
      viewport: { width: 1280, height: 720 },
      html: `
        <div id="main-body" class="psynet-surface"><p>Timeline content</p></div>
        <nav id="footer" class="navbar fixed-bottom">Reward</nav>`
    });
    const withFooter = await page.evaluate(
      () => getComputedStyle(document.body).paddingBottom
    );
    expect(parseFloat(withFooter)).toBeGreaterThan(0);
  }
);

test(
  "white captions stay distinct from the dark-mode surface",
  { tag: "@both" },
  async ({ page }) => {
    await renderTheme(page, {
      viewport: { width: 800, height: 600 },
      htmlAttrs: 'data-bs-theme="dark"',
      html: `
        <div class="psynet-surface" id="surface">
          <p id="caption" style="color: white">Get ready</p>
        </div>`
    });

    const colors = await page.evaluate(() => ({
      caption: getComputedStyle(document.getElementById("caption")).color,
      surface: getComputedStyle(document.getElementById("surface")).backgroundColor
    }));
    expect(colors.caption).not.toBe(colors.surface);
  }
);

test(
  "audio meter setLevel and applyColor update the CSS bar",
  { tag: "@both" },
  async ({ page }) => {
    await renderTheme(page, {
      viewport: { width: 800, height: 600 },
      html: `
        <div class="audio-meter">
          <div id="audio-meter" class="audio-meter__track" role="meter"
               aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
            <div class="audio-meter__fill" style="width: 0%;"></div>
          </div>
          <p id="audio-meter-text" class="audio-meter__text">Just right.</p>
        </div>`,
      scripts: [
        `window.psynet = {
           page: { control: {} },
           theme: {
             namedColors: {
               red: "var(--psynet-danger)",
               green: "var(--psynet-success)"
             },
             resolveColor: function (color) {
               if (color == null || color === "") return color;
               return this.namedColors[String(color).trim().toLowerCase()] || color;
             }
           }
         };`,
        AUDIO_METER_JS
      ]
    });

    const result = await page.evaluate(() => {
      const control = psynet.page.control.audioMeter;
      control.track = document.getElementById("audio-meter");
      control.fill = control.track.querySelector(".audio-meter__fill");
      control.audioMeterText = document.getElementById("audio-meter-text");
      control.setLevel(0.4);
      control.applyColor("red");
      return {
        fillWidth: control.fill.style.width,
        ariaNow: control.track.getAttribute("aria-valuenow"),
        fillToken: control.track.style.getPropertyValue("--audio-meter-fill"),
        textColor: control.audioMeterText.style.color
      };
    });

    expect(result.fillWidth).toBe("40%");
    expect(result.ariaNow).toBe("40");
    expect(result.fillToken).toBe("var(--psynet-danger)");
    expect(result.textColor).toBe("var(--psynet-danger)");
  }
);
