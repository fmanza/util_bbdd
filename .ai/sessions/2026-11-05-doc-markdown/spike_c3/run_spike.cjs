// Spike C3: valida los casos erDiagram con Mermaid 12.2.0 (local, el de util_bbdd_web) y mermaid@11 (el que carga
// Zensical 0.0.71 desde unpkg), y comprueba el sitio construido por Zensical en Chromium.
const path = require("path");
const fs = require("fs");
const { chromium } = require("C:/Desarrollo/python/libs/util_bbdd_web/frontend/node_modules/playwright");

const BASE_HARNESS = "http://127.0.0.1:8765/";
const BASE_SITE = "http://127.0.0.1:8766/";
const OUT = path.join(__dirname, "out", "spike_results.json");

(async () => {
  const browser = await chromium.launch();
  const report = { harness: {}, site: {} };

  for (const [label, src] of [
    ["mermaid-12.2.0", "mermaid-12.2.0.min.js"],
    ["mermaid@11 (unpkg, como Zensical)", "https://unpkg.com/mermaid@11/dist/mermaid.min.js"],
  ]) {
    const page = await browser.newPage();
    await page.goto(`${BASE_HARNESS}harness.html?src=${encodeURIComponent(src)}`);
    await page.waitForFunction(() => window.__done, null, { timeout: 300000 });
    report.harness[label] = await page.evaluate(() => window.__done);
    await page.close();
  }

  // Sitio Zensical: casos renderizados en la pagina real
  const page = await browser.newPage();
  const consoleErrors = [];
  page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text().slice(0, 200)); });
  const dialogs = [];
  page.on("dialog", async (d) => { dialogs.push(d.message()); await d.dismiss(); });
  const mermaidRequests = [];
  page.on("request", (r) => { if (/mermaid/.test(r.url())) mermaidRequests.push(r.url()); });

  await page.goto(`${BASE_SITE}tables/cases/`, { waitUntil: "networkidle", timeout: 120000 });
  await page.waitForTimeout(8000);
  report.site.cases = await page.evaluate(() => {
    const blocks = [...document.querySelectorAll(".mermaid")];
    return blocks.map((el, i) => {
      const root = el.shadowRoot || el;
      const svg = root.querySelector("svg");
      const txt = (root.textContent || "").slice(0, 120);
      const heading = (() => { let n = el; while (n && !/^H2$/.test(n.tagName)) n = n.previousElementSibling || n.parentElement; return n ? n.id : "?"; })();
      return { i, heading, svg: !!svg, error: /Syntax error|Parse error/i.test(txt) || (svg && /error/i.test(svg.getAttribute("aria-roledescription") || "")) };
    });
  });

  await page.goto(`${BASE_SITE}tables/pedidos/`, { waitUntil: "networkidle", timeout: 120000 });
  await page.waitForTimeout(2000);
  report.site.pedidos = await page.evaluate(() => ({
    title: document.title,
    h1: document.querySelector("h1") && document.querySelector("h1").textContent,
    anchor: !!document.getElementById("col-id"),
    scriptsInContent: document.querySelectorAll("article script, .md-content script").length,
    imgInContent: document.querySelectorAll(".md-content img").length,
    admonition: !!document.querySelector(".admonition.warning"),
    codeBlock: (document.querySelector("pre code") || {}).textContent,
    commentHtml: (document.querySelector(".md-content p strong") || {}).parentElement?.innerHTML,
  }));
  report.site.dialogs = dialogs;
  report.site.mermaidRequests = [...new Set(mermaidRequests)];
  report.site.consoleErrors = consoleErrors.slice(0, 20);

  await browser.close();
  fs.writeFileSync(OUT, JSON.stringify(report, null, 2));
  console.log("ok ->", OUT);
})().catch((e) => { console.error(e); process.exit(1); });
