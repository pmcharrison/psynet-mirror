/**
 * Layout contracts from the default-theme review that can be checked without
 * a running experiment: graphic size on a short landscape phone, vertical
 * push-button columns, footer clearance on pages without a footer, caption
 * contrast for color "white", audio-meter setLevel/applyColor, and the
 * in-page `psynetLayout.check()` API.
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
const BOOTSTRAP_CSS = fs.readFileSync(
  path.resolve("psynet/resources/libraries/bootstrap/bootstrap.min.css"),
  "utf8"
);

async function renderTheme(
  page,
  {
    html,
    extraCss = "",
    viewport,
    scripts = [],
    htmlAttrs = "",
    // Load Bootstrap before the theme, as participant pages do, for rules the
    // theme only adjusts rather than defines.
    includeBootstrap = false
  }
) {
  await page.setViewportSize(viewport);
  await page.setContent(`<!doctype html>
<html ${htmlAttrs}>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
${includeBootstrap ? BOOTSTRAP_CSS : ""}
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
  "vertical push-button lists stay in one column and grow the page",
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
      const lefts = buttons.map((button) =>
        Math.round(button.getBoundingClientRect().left)
      );
      const last = buttons[buttons.length - 1].getBoundingClientRect();
      return {
        uniqueLefts: [...new Set(lefts)].length,
        containerScroll: container.scrollHeight - container.clientHeight,
        pageScroll: document.documentElement.scrollHeight - window.innerHeight,
        lastBottom: last.bottom,
        count: buttons.length
      };
    });

    expect(metrics.count).toBe(20);
    expect(metrics.uniqueLefts).toBe(1);
    expect(metrics.containerScroll).toBeLessThanOrEqual(1);
    expect(metrics.pageScroll).toBeGreaterThan(1);
    expect(metrics.lastBottom).toBeGreaterThan(720);
  }
);

test(
  "long option lists grow their panel and scroll the page",
  { tag: "@both" },
  async ({ page }) => {
    const options = Array.from(
      { length: 16 },
      (_, i) =>
        `<label class="psynet-option">
           <input type="radio" name="opt" class="response">
           <span class="psynet-option-label">Option ${i + 1}</span>
         </label>`
    ).join("");
    await renderTheme(page, {
      viewport: { width: 1280, height: 720 },
      html: `<div class="control-container psynet-options">${options}</div>`
    });

    const metrics = await page.evaluate(() => {
      const panel = document.querySelector(".psynet-options");
      const style = getComputedStyle(panel);
      return {
        panelScroll: panel.scrollHeight - panel.clientHeight,
        pageScroll: document.documentElement.scrollHeight - window.innerHeight,
        background: style.backgroundColor,
        borderWidth: style.borderTopWidth
      };
    });

    // The panel behind the rows stays, but it no longer scrolls internally.
    expect(metrics.panelScroll).toBeLessThanOrEqual(1);
    expect(metrics.pageScroll).toBeGreaterThan(1);
    expect(metrics.background).not.toBe("rgba(0, 0, 0, 0)");
    expect(parseFloat(metrics.borderWidth)).toBeGreaterThan(0);
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
  "transient pages show a spinner immediately",
  { tag: "@both" },
  async ({ page }) => {
    await renderTheme(page, {
      viewport: { width: 1280, height: 720 },
      includeBootstrap: true,
      html: `<div id="main-body" class="psynet-surface">
               <div class="psynet-activity" role="status">
                 <span class="spinner-border" aria-hidden="true"></span>
                 <span class="visually-hidden">Working...</span>
               </div>
             </div>`
    });

    const spinner = page.locator(".psynet-activity .spinner-border");
    await expect(spinner).toBeVisible();

    const state = await spinner.evaluate((element) => {
      const style = getComputedStyle(element);
      return {
        opacity: parseFloat(style.opacity),
        animationDelay: style.animationDelay,
        animationName: style.animationName,
        color: style.color,
        // Layout size, not getBoundingClientRect: the spinner is rotating, and
        // a rotated square reports a bounding box up to 1.41x its own size.
        width: style.width,
        height: style.height
      };
    });

    // No delayed reveal: the spinner is there from the first frame.
    expect(state.opacity).toBe(1);
    expect(state.animationDelay).toBe("0s");
    expect(state.animationName).toBe("spinner-border");
    // The theme's sizing and accent colour win over Bootstrap's defaults.
    expect(state.width).toBe("40px");
    expect(state.height).toBe("40px");
    expect(state.color).toBe("rgb(48, 112, 200)");
  }
);

test(
  "media progress mirrors the timeline bar and follows the footer",
  { tag: "@both" },
  async ({ page }) => {
    const header = `
      <div id="timeline-header" class="header">
        <div class="progress">
          <div id="timeline-progress-bar" class="progress-bar" style="width:12%"></div>
        </div>
      </div>`;
    const bar = `<div id="media-download-progress-bar" style="width: 40%"></div>`;
    const bootstrapNavbar = `
      .navbar { --bs-navbar-padding-y: 0.5rem; --bs-navbar-padding-x: 0;
                position: relative; display: flex; flex-wrap: wrap;
                align-items: center;
                padding: var(--bs-navbar-padding-y) var(--bs-navbar-padding-x); }
      .fixed-bottom { position: fixed; bottom: 0; left: 0; right: 0; }
      .container { width: 100%; padding-inline: 0.75rem; margin-inline: auto; }
      .py-2 { padding-top: 0.5rem; padding-bottom: 0.5rem; }
      .progress { display: flex; overflow: hidden; }`;

    // No footer: the bar takes the bottom edge, like the top bar takes the top.
    await renderTheme(page, {
      viewport: { width: 1280, height: 720 },
      extraCss: bootstrapNavbar,
      html: `${header}<div id="main-body" class="psynet-surface"><p>Trial</p></div>${bar}`
    });

    let geometry = await page.evaluate(() => {
      const media = document.getElementById("media-download-progress-bar");
      const top = document.querySelector("#timeline-header .progress");
      const mediaRect = media.getBoundingClientRect();
      return {
        topHeight: getComputedStyle(top).height,
        mediaHeight: getComputedStyle(media).height,
        mediaBottom: Math.round(mediaRect.bottom),
        mediaWidth: Math.round(mediaRect.width),
        viewport: window.innerHeight,
        bodyPaddingBottom: getComputedStyle(document.body).paddingBottom
      };
    });

    // A thinner rail than the labelled bar at the top of the page.
    expect(parseFloat(geometry.mediaHeight)).toBeGreaterThan(0);
    expect(parseFloat(geometry.mediaHeight)).toBeLessThan(
      parseFloat(geometry.topHeight)
    );
    expect(geometry.mediaBottom).toBe(geometry.viewport);
    // Width still tracks progress rather than filling the page.
    expect(geometry.mediaWidth).toBe(512);
    // Room reserved so scrolled content cannot hide under it.
    expect(geometry.bodyPaddingBottom).toBe(geometry.mediaHeight);

    // With a footer it rides the footer's top edge instead.
    await renderTheme(page, {
      viewport: { width: 1280, height: 720 },
      extraCss: bootstrapNavbar,
      html: `${header}<div id="main-body" class="psynet-surface"><p>Trial</p></div>
             <nav id="footer" class="navbar fixed-bottom">${bar}
               <div class="container py-2"><div class="footer-text">Reward: $0.42</div></div>
             </nav>`
    });

    geometry = await page.evaluate(() => {
      const media = document.getElementById("media-download-progress-bar");
      const footer = document.getElementById("footer");
      return {
        mediaTop: Math.round(media.getBoundingClientRect().top),
        footerTop: Math.round(footer.getBoundingClientRect().top),
        footerBorderTop: getComputedStyle(footer).borderTopWidth,
        mediaHeight: getComputedStyle(media).height,
        mediaToken: getComputedStyle(document.documentElement)
          .getPropertyValue("--psynet-media-progress-height")
          .trim()
      };
    });

    // The bar sits just inside the footer's top border, not over it.
    expect(geometry.mediaTop - geometry.footerTop).toBe(
      parseFloat(geometry.footerBorderTop)
    );
    // Still its own token height, whatever the theme sets it to.
    expect(geometry.mediaHeight).toBe(geometry.mediaToken);
  }
);

test(
  "footer text is centred below the progress bar",
  { tag: "@both" },
  async ({ page }) => {
    await renderTheme(page, {
      viewport: { width: 1280, height: 720 },
      // Same markup as timeline-page.html's footer macro, with the progress bar
      // full width as it is on a page with no media to download.
      html: `
        <nav id="footer" class="navbar fixed-bottom">
          <div id="media-download-progress-bar" style="width: 100%"></div>
          <div class="container py-2 d-flex flex-wrap align-items-center gap-2">
            <div class="footer-text">Reward: <strong>$0.00</strong></div>
          </div>
        </nav>`,
      // The theme relies on Bootstrap for .navbar padding and .fixed-bottom.
      extraCss: `
        .navbar { --bs-navbar-padding-y: 0.5rem; --bs-navbar-padding-x: 0;
                  position: relative; display: flex; flex-wrap: wrap;
                  align-items: center;
                  padding: var(--bs-navbar-padding-y) var(--bs-navbar-padding-x); }
        .fixed-bottom { position: fixed; bottom: 0; left: 0; right: 0; }
        .container { width: 100%; padding-inline: 0.75rem; margin-inline: auto; }
        .py-2 { padding-top: 0.5rem; padding-bottom: 0.5rem; }
        .d-flex { display: flex; }
        .align-items-center { align-items: center; }`
    });

    const offset = await page.evaluate(() => {
      const footer = document.getElementById("footer");
      const bar = document.getElementById("media-download-progress-bar");
      const text = footer.querySelector(".footer-text");
      const footerRect = footer.getBoundingClientRect();
      const barRect = bar.getBoundingClientRect();
      const textRect = text.getBoundingClientRect();
      // The strip participants see starts below the progress bar.
      const stripTop = barRect.bottom;
      return (
        textRect.top - stripTop - (footerRect.bottom - textRect.bottom)
      );
    });

    // Positive means the text sits low, negative means it sits high.
    expect(Math.abs(offset)).toBeLessThanOrEqual(1);
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

const LAYOUT_JS_PATH = path.resolve("psynet/resources/scripts/psynet.layout.js");

async function renderLayoutFixture(page, html, viewport = { width: 1280, height: 720 }) {
  await page.setViewportSize(viewport);
  await page.setContent(`<!doctype html>
<html>
<body>
${html}
</body>
</html>`);
  await page.addScriptTag({ path: LAYOUT_JS_PATH });
}

test(
  "layout check reports overflow on a tall page that does not expect scrolling",
  { tag: "@both" },
  async ({ page }) => {
    await renderLayoutFixture(
      page,
      `<div id="main-body" style="height: 2000px">tall</div>`
    );
    const violations = await page.evaluate(async () => window.psynetLayout.check());
    expect(violations.map((item) => item.check)).toContain("no_vertical_overflow");
  }
);

test(
  "layout check skips overflow when expect_scrolling is set",
  { tag: "@both" },
  async ({ page }) => {
    await renderLayoutFixture(
      page,
      `<div id="main-body" data-expect-scrolling="true" style="height: 2000px">tall</div>`
    );
    const violations = await page.evaluate(async () => window.psynetLayout.check());
    expect(violations.map((item) => item.check)).not.toContain("no_vertical_overflow");
    expect(violations.map((item) => item.check)).not.toContain(
      "controls_reachable_without_scrolling"
    );
  }
);

test(
  "layout check is empty on a short page",
  { tag: "@both" },
  async ({ page }) => {
    await renderLayoutFixture(page, `<div id="main-body"><p>short</p></div>`);
    const violations = await page.evaluate(async () => window.psynetLayout.check());
    expect(violations).toEqual([]);
  }
);

test(
  "layout API attaches to an existing psynet object",
  { tag: "@both" },
  async ({ page }) => {
    await page.setContent("<!doctype html><body></body>");
    await page.addScriptTag({ content: "window.psynet = {};" });
    await page.addScriptTag({ path: LAYOUT_JS_PATH });
    const attached = await page.evaluate(
      () => window.psynet.layout === window.psynetLayout
    );
    expect(attached).toBe(true);
  }
);

test(
  "layout helper fails when the page API is missing",
  { tag: "@both" },
  async ({ page }) => {
    const { assertPageInvariants } = require("./participantPageInvariants");
    await page.setContent("<!doctype html><p>bare</p>");
    await expect(assertPageInvariants(page, "bare page")).rejects.toThrow(
      /psynetLayout/
    );
  }
);
