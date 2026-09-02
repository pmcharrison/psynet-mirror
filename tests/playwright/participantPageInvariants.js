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
 *   standards_mode                 Template output emitted before
 *                                  `<!doctype html>` put every participant page
 *                                  into quirks mode.
 *   percentage_height_ineffective  Layouts declared percentage heights against
 *                                  auto-height parents, which only resolved
 *                                  because of quirks mode.
 *   action_not_occluded            A response control was partly hidden behind
 *                                  the fixed footer.
 *   no_horizontal_overflow         Content wider than the viewport.
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

  // A response control that starts above the fold must not be partly hidden
  // behind the fixed footer. A control entirely below the fold is fine: that
  // is ordinary scrolling, not occlusion.
  //
  // This check is therefore viewport-relative, and callers should pin a
  // representative desktop viewport. On a very short viewport the control falls
  // below the fold and the check has nothing to say; on a very tall one the
  // page never reaches the footer.
  const footer = document.querySelector("#footer");
  if (footer && getComputedStyle(footer).display !== "none") {
    const footerRect = footer.getBoundingClientRect();
    const selectors = ["#next-button", "#reset-button", ".push-button", "#consent"];
    for (const selector of selectors) {
      for (const element of document.querySelectorAll(selector)) {
        const style = getComputedStyle(element);
        if (style.display === "none" || style.visibility === "hidden") continue;
        const rect = element.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) continue;
        const startsAboveFold = rect.top < window.innerHeight;
        const intersectsFooter =
          rect.bottom > footerRect.top && rect.top < footerRect.bottom;
        if (startsAboveFold && intersectsFooter) {
          violations.push({
            check: "action_not_occluded",
            detail:
              `${selector} spans y=${round(rect.top)}-${round(rect.bottom)} but the ` +
              `fixed footer starts at y=${round(footerRect.top)}`,
          });
        }
      }
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
  const violations = await page.evaluate(collectViolations);
  expect(violations, formatViolations(label, violations)).toEqual([]);
}

/**
 * Assert that the page's primary action is fully visible without scrolling.
 *
 * Use this for pages that are meant to fit on screen: a single stimulus and a
 * single response control. It is a stronger statement than the occlusion
 * invariant, which only fires when a control happens to straddle the footer,
 * and it is the contract that `GraphicPrompt.max_viewport_height` exists to
 * uphold. Do not use it for pages that legitimately scroll, such as consent.
 */
async function assertPrimaryActionVisibleWithoutScrolling(page, label) {
  const geometry = await page.evaluate(() => {
    const button = document.querySelector("#next-button");
    if (!button) return null;
    const rect = button.getBoundingClientRect();
    const footer = document.querySelector("#footer");
    const footerVisible = footer && getComputedStyle(footer).display !== "none";
    const footerRect = footerVisible ? footer.getBoundingClientRect() : null;
    return {
      top: Math.round(rect.top),
      bottom: Math.round(rect.bottom),
      scrollY: Math.round(window.scrollY),
      viewportHeight: window.innerHeight,
      documentHeight: Math.round(document.documentElement.scrollHeight),
      limit: Math.round(footerRect ? footerRect.top : window.innerHeight),
    };
  });

  expect(geometry, `${label}: expected a #next-button to assert against`).not.toBeNull();

  const visible = geometry.top >= 0 && geometry.bottom <= geometry.limit;
  expect(
    visible,
    `${label}: the primary action should be fully visible without scrolling, but ` +
      `#next-button spans y=${geometry.top}-${geometry.bottom} while the usable area ` +
      `ends at y=${geometry.limit} (viewport ${geometry.viewportHeight}px, document ` +
      `${geometry.documentHeight}px, scrollY ${geometry.scrollY})`
  ).toBe(true);
}

module.exports = {
  assertPageInvariants,
  assertPrimaryActionVisibleWithoutScrolling,
  collectViolations,
};
