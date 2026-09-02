/**
 * Structural invariants for participant-facing pages.
 *
 * These are assertions about how a page is built, not judgements about how it
 * looks, so they can run unattended. They exist because the failures they catch
 * are silent: nothing errors, nothing warns, and the page often looks plausible
 * until some unrelated change disturbs it.
 *
 * Each check corresponds to a defect that reached the default theme at least
 * once:
 *
 *   standards_mode                       Template output emitted before
 *                                        `<!doctype html>` put every
 *                                        participant page into quirks mode.
 *   percentage_height_ineffective        Layouts declared percentage heights
 *                                        against auto-height parents, which
 *                                        only resolved because of quirks mode.
 *   controls_reachable_without_scrolling  A stimulus grew large enough to push
 *                                        the response control off screen on a
 *                                        page that was meant to fit.
 *   no_vertical_overflow                 A page that was meant to fit can
 *                                        still scroll, even if the control
 *                                        happens to peek above the footer.
 *   nothing_permanently_occluded         Content left behind the fixed footer
 *                                        even at the end of the scroll.
 *   no_horizontal_overflow               Content wider than the viewport.
 *
 * Pages that are genuinely meant to scroll, such as consent forms, declare it
 * with `expect_scrolling=True`; see `Page` in psynet/timeline.py.
 *
 * Usage:
 *
 *   const { assertPageInvariants } = require("./participantPageInvariants");
 *   await assertPageInvariants(page, "radio page");
 */
const { expect } = require("./fixtures");

/**
 * Collect invariant violations for the page currently loaded in the browser.
 *
 * Runs entirely inside the page so that it can read layout geometry and the
 * CSSOM. Returns an array of `{check, detail}` objects; an empty array means
 * every invariant held.
 */
const collectViolations = () => {
  const violations = [];
  const round = (n) => Math.round(n);

  // A missing or displaced doctype silently changes the box model and how
  // percentage heights resolve.
  if (document.compatMode !== "CSS1Compat") {
    violations.push({
      check: "standards_mode",
      detail: `document.compatMode is ${document.compatMode}, expected CSS1Compat`,
    });
  }

  // Unless the page declares that it expects scrolling, its response controls
  // must be reachable without scrolling. Declaring intent is the only reliable
  // way to tell a stimulus page that has outgrown the window from a consent
  // form that is meant to be long: the geometry looks identical.
  const mainBody = document.querySelector("#main-body");
  const expectsScrolling = mainBody
    ? mainBody.dataset.expectScrolling === "true"
    : false;

  const footer = document.querySelector("#footer");
  const footerVisible = footer && getComputedStyle(footer).display !== "none";
  const footerRect = footerVisible ? footer.getBoundingClientRect() : null;
  const usableBottom = footerRect ? footerRect.top : window.innerHeight;

  if (mainBody && !expectsScrolling) {
    const selectors = ["#next-button", "#reset-button", ".push-button", "#consent"];
    for (const selector of selectors) {
      for (const element of document.querySelectorAll(selector)) {
        const style = getComputedStyle(element);
        if (style.display === "none" || style.visibility === "hidden") continue;
        const rect = element.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) continue;
        if (rect.top >= 0 && rect.bottom <= usableBottom) continue;
        violations.push({
          check: "controls_reachable_without_scrolling",
          detail:
            `${selector} spans y=${round(rect.top)}-${round(rect.bottom)} but the ` +
            `usable area is 0-${round(usableBottom)} ` +
            `(viewport ${window.innerHeight}px, document ` +
            `${round(document.documentElement.scrollHeight)}px). Either make the page ` +
            "fit, or pass expect_scrolling=True to the page if it is meant to scroll",
        });
      }
    }

    // Reachability alone is not enough: a Next button can sit just above the
    // footer while the content surface still extends a few centimetres below
    // the fold, which is the scrollbar participants notice on a laptop.
    const scrollHeight = Math.max(
      document.documentElement.scrollHeight,
      document.body ? document.body.scrollHeight : 0
    );
    if (scrollHeight > window.innerHeight + 1) {
      violations.push({
        check: "no_vertical_overflow",
        detail:
          `document scrollHeight ${round(scrollHeight)} exceeds viewport height ` +
          `${window.innerHeight}px, so the page can scroll. Either make the page ` +
          "fit, or pass expect_scrolling=True to the page if it is meant to scroll",
      });
    }
  }

  // A percentage height resolves only against an ancestor with a definite
  // height. Against an auto-height parent it silently becomes auto in standards
  // mode, and resolves against the viewport in quirks mode, so the same markup
  // behaves differently depending on the document mode.
  //
  // Candidates come from stylesheet rules and from inline style attributes,
  // because either can declare the height.
  const candidates = new Map();
  const addCandidate = (element, height, origin) => {
    if (!candidates.has(element)) candidates.set(element, { height, origin });
  };

  for (const sheet of document.styleSheets) {
    let rules;
    try {
      rules = sheet.cssRules;
    } catch (error) {
      continue; // cross-origin stylesheet
    }
    for (const rule of rules) {
      if (!rule.selectorText || !rule.style) continue;
      const height = rule.style.getPropertyValue("height");
      if (!height || !height.trim().endsWith("%")) continue;
      let matches;
      try {
        matches = document.querySelectorAll(rule.selectorText);
      } catch (error) {
        continue; // selector unsupported by querySelectorAll
      }
      for (const element of matches) {
        addCandidate(element, height.trim(), rule.selectorText);
      }
    }
  }

  for (const element of document.querySelectorAll("[style]")) {
    const height = element.style.height;
    if (height && height.trim().endsWith("%")) {
      addCandidate(element, height.trim(), "inline style");
    }
  }

  for (const [element, { height, origin }] of candidates) {
    if (element === document.documentElement || element === document.body) continue;
    const parent = element.parentElement;
    if (!parent) continue;
    const style = getComputedStyle(element);
    if (
      style.display === "none" ||
      style.position === "absolute" ||
      style.position === "fixed"
    ) {
      continue;
    }

    // Probe: collapse the element. If the parent shrinks with it, the parent's
    // height is derived from its children, so it has no definite height for the
    // percentage to resolve against.
    const parentHeight = parent.getBoundingClientRect().height;
    if (parentHeight === 0) continue;
    const savedHeight = element.style.height;
    element.style.height = "0px";
    const collapsedParentHeight = parent.getBoundingClientRect().height;
    element.style.height = savedHeight;

    if (collapsedParentHeight < parentHeight - 1) {
      const label = element.id ? `#${element.id}` : element.tagName.toLowerCase();
      violations.push({
        check: "percentage_height_ineffective",
        detail:
          `${label} declares height:${height} (${origin}) against an auto-height parent ` +
          `(collapsing it shrank the parent from ${round(parentHeight)}px to ` +
          `${round(collapsedParentHeight)}px), so the declared height depends on ` +
          "quirks-mode behaviour rather than resolving as written",
      });
    }
  }

  const scrollWidth = document.documentElement.scrollWidth;
  if (scrollWidth > window.innerWidth + 1) {
    violations.push({
      check: "no_horizontal_overflow",
      detail: `document scrollWidth ${scrollWidth} exceeds viewport width ${window.innerWidth}`,
    });
  }

  return violations;
};

/**
 * Detect content that stays behind the fixed footer even at the end of the
 * scroll, which no amount of scrolling can reveal.
 *
 * Scrolls to the end, restoring the original position afterwards. The scroll is
 * repeated until the position stops changing: a single jump can land short
 * while layout is still settling, which reports occlusion that is not there.
 */
const collectScrollViolations = async () => {
  const footer = document.querySelector("#footer");
  if (!footer || getComputedStyle(footer).display === "none") return [];

  const scroller = document.scrollingElement || document.documentElement;
  const originalScrollTop = scroller.scrollTop;

  let previous = -1;
  for (let i = 0; i < 40 && scroller.scrollTop !== previous; i++) {
    previous = scroller.scrollTop;
    scroller.scrollTop = scroller.scrollHeight;
    await new Promise((resolve) => setTimeout(resolve, 50));
  }

  const footerTop = footer.getBoundingClientRect().top;
  const violations = [];
  const selectors = ["#next-button", "#reset-button", ".push-button", "#consent"];
  for (const selector of selectors) {
    for (const element of document.querySelectorAll(selector)) {
      const style = getComputedStyle(element);
      if (style.display === "none" || style.visibility === "hidden") continue;
      if (style.position === "fixed") continue; // pinned on purpose
      const rect = element.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) continue;
      if (rect.bottom > footerTop && rect.top < footer.getBoundingClientRect().bottom) {
        violations.push({
          check: "nothing_permanently_occluded",
          detail:
            `${selector} is still behind the fixed footer at the end of the scroll ` +
            `(spans y=${Math.round(rect.top)}-${Math.round(rect.bottom)}, footer starts ` +
            `at y=${Math.round(footerTop)}), so it can never be fully seen`,
        });
      }
    }
  }

  scroller.scrollTop = originalScrollTop;
  return violations;
};

function formatViolations(label, violations) {
  const lines = violations.map((v) => `  - [${v.check}] ${v.detail}`);
  return `Participant page invariants failed on ${label}:\n${lines.join("\n")}`;
}

/**
 * Assert that the current page satisfies every invariant.
 *
 * `label` identifies the page in the failure message; Playwright attaches its
 * own screenshot and trace on failure, so the report shows what the page looked
 * like when the assertion fired.
 */
async function assertPageInvariants(page, label) {
  // Park the pointer so hover styling cannot influence geometry.
  await page.mouse.move(0, 0).catch(() => {});
  const violations = [
    ...(await page.evaluate(collectViolations)),
    ...(await page.evaluate(collectScrollViolations)),
  ];
  expect(violations, formatViolations(label, violations)).toEqual([]);
}

module.exports = {
  assertPageInvariants,
  collectViolations,
  collectScrollViolations,
};
