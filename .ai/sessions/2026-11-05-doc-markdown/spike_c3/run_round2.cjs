const path = require("path");
const fs = require("fs");
const { chromium } = require("C:/Desarrollo/python/libs/util_bbdd_web/frontend/node_modules/playwright");

(async () => {
  const browser = await chromium.launch();
  const report = { harness: {}, site: {} };
  for (const [label, src] of [
    ["mermaid-12.2.0", "mermaid-12.2.0.min.js"],
    ["mermaid@11.17.2", "https://unpkg.com/mermaid@11.17.2/dist/mermaid.min.js"],
  ]) {
    const page = await browser.newPage();
    await page.goto(`http://127.0.0.1:8765/harness.html?src=${encodeURIComponent(src)}`);
    await page.waitForFunction(() => window.__done, null, { timeout: 300000 });
    report.harness[label] = await page.evaluate(() => window.__done);
    await page.close();
  }
  // Sitio: estado real de los bloques mermaid tras renderizar
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
  await page.goto("http://127.0.0.1:8766/tables/cases/", { waitUntil: "networkidle", timeout: 120000 });
  await page.waitForTimeout(15000);
  report.site.blocks = await page.evaluate(() =>
    [...document.querySelectorAll("h2")].map((h) => {
      let n = h.nextElementSibling;
      while (n && !n.matches(".mermaid, pre.mermaid, div.mermaid") && n.tagName !== "H2") n = n.nextElementSibling;
      if (!n || n.tagName === "H2") return { id: h.id, found: false };
      const r = n.getBoundingClientRect();
      return {
        id: h.id, tag: n.tagName, cls: n.className, shadow: !!n.shadowRoot, height: Math.round(r.height),
        hasSvgChild: !!n.querySelector("svg"), rawTextVisible: (n.innerText || "").trim().startsWith("erDiagram"),
        dataProcessed: n.getAttribute("data-processed"),
      };
    }));
  await page.locator("h2#base").scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(__dirname, "out", "site_base.png") });
  await page.locator("h2#alias_hostile").scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(__dirname, "out", "site_alias_hostile.png") });
  await browser.close();
  fs.writeFileSync(path.join(__dirname, "out", "round2_results.json"), JSON.stringify(report, null, 2));
  console.log("ok");
})().catch((e) => { console.error(e); process.exit(1); });
