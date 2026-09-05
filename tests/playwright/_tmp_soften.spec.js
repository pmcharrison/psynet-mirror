const fs = require("fs");
const path = require("path");
const { test } = require("./fixtures");

const theme = fs.readFileSync(
  path.resolve("psynet/resources/css/participant.css"),
  "utf8"
);
const bootstrap = fs.readFileSync(
  path.resolve("psynet/resources/libraries/bootstrap/bootstrap.min.css"),
  "utf8"
);

// A: as committed. B: neutral labels, so the border alone carries the meaning.
// C: neutral labels plus borders softened as far as 3:1 allows. Each also shown
// with the progress rail recoloured to the chrome tint.
const VARIANTS = {
  a_current: {
    label: "A. as committed: coloured labels, full-strength borders, grey rail",
    css: ""
  },
  b_neutral: {
    label: "B. neutral labels, full-strength borders, rail recoloured to chrome tint",
    css: `
      #timeline-header .progress { background-color: var(--psynet-footer-bg); }
      #timeline-progress-label::before { background-color: var(--psynet-footer-bg); }
      #footer #comment-button { --bs-btn-color: var(--psynet-text); --bs-btn-hover-color: var(--psynet-text); }
    `
  },
  c_softened: {
    label: "C. neutral Comment label, borders softened to the 3:1 floor, chrome rail",
    css: `
      #timeline-header .progress { background-color: var(--psynet-footer-bg); }
      #timeline-progress-label::before { background-color: var(--psynet-footer-bg); }
      #footer #comment-button {
        --bs-btn-color: var(--psynet-text);
        --bs-btn-hover-color: var(--psynet-text);
        --bs-btn-border-color: #4f85d0;
        --bs-btn-hover-border-color: #4f85d0;
      }
      #footer #terminate-button {
        --bs-btn-border-color: #c96167;
        --bs-btn-hover-border-color: #c96167;
      }
    `
  }
};

const FOOTER = `
<nav id="footer" class="navbar fixed-bottom">
  <div id="media-download-progress-bar" style="width: 100%"></div>
  <div class="container py-2 d-flex flex-wrap align-items-center gap-2">
    <span class="psynet-tooltip">
      <span id="reward-summary" class="footer-text psynet-tooltip__trigger" tabindex="0" aria-describedby="reward-tooltip">
        <span class="visually-hidden">Reward: </span><strong>$0.42</strong>
        <svg class="psynet-info" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14Zm0-1.5A5.5 5.5 0 1 0 8 2.5a5.5 5.5 0 0 0 0 11ZM7.25 6.5a.75.75 0 1 1 1.5 0v4a.75.75 0 0 1-1.5 0v-4ZM8 3.75a.9.9 0 1 1 0 1.8.9.9 0 0 1 0-1.8Z"/></svg>
      </span>
      <span id="reward-tooltip" class="psynet-tooltip__content" role="tooltip">Reward earned so far.</span>
    </span>
    <button type="button" class="btn btn-light" id="comment-button">Comment</button>
    <span class="psynet-tooltip psynet-tooltip--end">
      <button id="terminate-button" class="btn btn-danger psynet-tooltip__trigger" aria-describedby="exit-tooltip">Exit</button>
      <span id="exit-tooltip" class="psynet-tooltip__content" role="tooltip">Exit early.</span>
    </span>
  </div>
</nav>`;

test("soften and rail variants", async ({ page }) => {
  for (const [name, v] of Object.entries(VARIANTS)) {
    await page.setViewportSize({ width: 1440, height: 520 });
    await page.setContent(`<!doctype html><html><head><style>
      ${bootstrap}
      ${theme}
      body { margin: 0; }
      ${v.css}
      #variant-label { position: fixed; top: 0; left: 0; right: 0; z-index: 2000;
        font: 600 13px Inter, sans-serif; color: #1f2733; background: #fff;
        border-bottom: 1px solid #dfe5ee; padding: 6px 12px; }
    </style></head><body>
      <div id="variant-label">${v.label}</div>
      <div id="timeline-header" class="header" style="margin-top: 28px">
        <div class="progress">
          <div id="timeline-progress-bar" class="progress-bar" style="width:35%"></div>
          <span id="timeline-progress-label" aria-hidden="true" data-progress="35%"></span>
        </div>
      </div>
      <div id="main-body" class="container psynet-surface">
        <p>Which of these trees did you hear about?</p>
        <div class="psynet-actions"><button id="next-button" class="btn btn-primary btn-lg">Next</button></div>
      </div>
      ${FOOTER}</body></html>`);
    await page.waitForTimeout(200);
    await page.screenshot({ path: `/tmp/soften-${name}.png` });

    const m = await page.evaluate(() => {
      const cs = (s) => getComputedStyle(document.querySelector(s));
      return {
        railBg: cs("#timeline-header .progress").backgroundColor,
        commentBorder: cs("#comment-button").borderTopColor,
        commentText: cs("#comment-button").color,
        exitBorder: cs("#terminate-button").borderTopColor
      };
    });
    console.log(`VARIANT ${name} ${JSON.stringify(m)}`);
  }
});
