const path = require("path");
const { test, expect } = require("./fixtures");

const {
  assertInplaceTimelinePathActive,
  assertNoBackendError,
  clickNextAndWait,
  completeInitialGateway,
  waitForMainBodyContains,
  withExperiment
} = require("./psynetHarness");

const STEP_TIMEOUT_MS = 120000;

test("legacy js_var globals warn, error, and restore across pages", async ({
  page,
  context
}) => {
  const absDir = path.resolve("tests/playwright/experiments/js_var_globals");

  await withExperiment(page, context, absDir, async (experimentPage) => {
    const warnings = [];
    experimentPage.on("console", (message) => {
      if (message.type() === "warning") {
        warnings.push(message.text());
      }
    });

    await completeInitialGateway(experimentPage);
    await assertInplaceTimelinePathActive(experimentPage, 20000);
    await waitForMainBodyContains(experimentPage, "Alpha page", STEP_TIMEOUT_MS);

    const alphaState = await experimentPage.evaluate(() => {
      window.unrelated_existing = 9;
      const descriptor = Object.getOwnPropertyDescriptor(
        window,
        "legacy_alpha"
      );
      const explicitValue = window.legacy_alpha;
      const bareValue = Function("return legacy_alpha")();
      window.legacy_alpha = 7;
      return {
        hasGetter: typeof descriptor?.get === "function",
        explicitValue,
        bareValue,
        assignedValue: window.legacy_alpha,
        canonicalValue: psynet.var.legacy_alpha,
        missingType: Function("return typeof unrelated_missing")(),
        unrelatedValue: window.unrelated_existing
      };
    });
    expect(alphaState).toEqual({
      hasGetter: true,
      explicitValue: 1,
      bareValue: 1,
      assignedValue: 7,
      canonicalValue: 1,
      missingType: "undefined",
      unrelatedValue: 9
    });
    await expect
      .poll(
        () =>
          warnings.filter((message) => message.includes('"legacy_alpha"')).length,
        { timeout: STEP_TIMEOUT_MS }
      )
      .toBe(1);

    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);
    await waitForMainBodyContains(experimentPage, "Beta page", STEP_TIMEOUT_MS);
    const betaState = await experimentPage.evaluate(() => {
      psynetTemplateData.flags.legacyJsVarGlobals = "error";
      let error;
      try {
        Function("return legacy_beta")();
      } catch (caught) {
        error = {
          name: caught.name,
          message: caught.message
        };
      }
      return {
        alphaDescriptor: Object.getOwnPropertyDescriptor(
          window,
          "legacy_alpha"
        ),
        canonicalValue: psynet.var.legacy_beta,
        error,
        unrelatedValue: window.unrelated_existing
      };
    });
    expect(betaState).toEqual({
      alphaDescriptor: undefined,
      canonicalValue: 2,
      error: {
        name: "ReferenceError",
        message:
          'Legacy global js_vars access "legacy_beta" is disabled. ' +
          'Use psynet.var["legacy_beta"] instead.'
      },
      unrelatedValue: 9
    });

    await experimentPage.evaluate(() => {
      Object.defineProperty(window, "restored_global", {
        configurable: true,
        enumerable: false,
        value: 42,
        writable: true
      });
    });
    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);
    await waitForMainBodyContains(
      experimentPage,
      "Descriptor page",
      STEP_TIMEOUT_MS
    );
    const descriptorState = await experimentPage.evaluate(() => {
      const descriptor = Object.getOwnPropertyDescriptor(
        window,
        "restored_global"
      );
      return {
        hasGetter: typeof descriptor?.get === "function",
        legacyValue: window.restored_global,
        canonicalValue: psynet.var.restored_global
      };
    });
    expect(descriptorState).toEqual({
      hasGetter: true,
      legacyValue: 3,
      canonicalValue: 3
    });

    const offState = await experimentPage.evaluate(() => {
      const templateDataElement = document.getElementById(
        "psynet-template-data"
      );
      const templateData = JSON.parse(templateDataElement.textContent);
      templateData.flags.legacyJsVarGlobals = "off";
      templateDataElement.textContent = JSON.stringify(templateData);
      psynet.refreshTemplateData();

      const descriptor = Object.getOwnPropertyDescriptor(
        window,
        "restored_global"
      );
      return {
        hasGetter: typeof descriptor?.get === "function",
        restoredValue: window.restored_global,
        enumerable: descriptor?.enumerable,
        canonicalValue: psynet.var.restored_global
      };
    });
    expect(offState).toEqual({
      hasGetter: false,
      restoredValue: 42,
      enumerable: false,
      canonicalValue: 3
    });

    await clickNextAndWait(experimentPage, STEP_TIMEOUT_MS);
    await waitForMainBodyContains(experimentPage, "Cleanup page", STEP_TIMEOUT_MS);
    expect(
      await experimentPage.evaluate(() => ({
        restoredValue: window.restored_global,
        unrelatedValue: window.unrelated_existing
      }))
    ).toEqual({
      restoredValue: 42,
      unrelatedValue: 9
    });
    await assertNoBackendError(experimentPage);
  });
});
