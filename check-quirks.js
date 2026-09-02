const { chromium } = require("@playwright/test");
const BASE = "http://127.0.0.1:5000";

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const report = {};

  await page.goto(`${BASE}/ad?generate_tokens=true&recruiter=hotair`, { waitUntil: "networkidle" });
  report.ad = {
    compatMode: await page.evaluate(() => document.compatMode),
    themeStyleBlocks: await page.evaluate(
      () => document.querySelectorAll("#logo_container").length
    ),
    nodesBeforeHead: await page.evaluate(() => {
      // Anything the parser had to relocate because it preceded <head>.
      return document.body ? document.body.firstElementChild?.tagName : null;
    }),
  };

  await page.locator("#begin-button").click();
  await page.waitForTimeout(600);
  report.consent = { compatMode: await page.evaluate(() => document.compatMode) };

  await page.locator("#consent").click();
  await page.waitForURL(/timeline/, { timeout: 30000 });
  await page.waitForTimeout(1200);
  report.timeline = {
    compatMode: await page.evaluate(() => document.compatMode),
    logoContainers: await page.evaluate(() => document.querySelectorAll("#logo_container").length),
    footerRuleCount: await page.evaluate(() => {
      let n = 0;
      for (const s of document.styleSheets) {
        let rules;
        try { rules = s.cssRules; } catch (e) { continue; }
        for (const r of rules) if (r.selectorText === "#footer") n++;
      }
      return n;
    }),
    boxSizingSample: await page.evaluate(() => {
      const el = document.querySelector("#main-body");
      return el ? getComputedStyle(el).boxSizing : null;
    }),
  };

  console.log(JSON.stringify(report, null, 2));
  await browser.close();
})().catch((e) => { console.error("FAILED:", e); process.exit(1); });
