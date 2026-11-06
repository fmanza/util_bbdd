// CC2 (grupo C): sitio Zensical con Mermaid local (markdown.mermaid_js) y sin acceso a Internet.
// Bloquea toda petición que no sea a 127.0.0.1 y comprueba que los diagramas se dibujan.
const fs = require("fs");
const path = require("path");
const { chromium } = require("C:/Desarrollo/python/libs/util_bbdd_web/frontend/node_modules/playwright");

const base = process.argv[2]; // http://127.0.0.1:PORT/
const label = process.argv[3];

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
  const blocked = [];
  const errors = [];
  await page.route("**/*", (route) => {
    const url = route.request().url();
    if (url.startsWith("http://127.0.0.1")) return route.continue();
    blocked.push(url);
    return route.abort();
  });
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text().slice(0, 160)); });
  await page.goto(`${base}tables/pedidos/`, { waitUntil: "networkidle", timeout: 60000 });
  await page.waitForTimeout(6000);
  const blocks = await page.evaluate(() =>
    [...document.querySelectorAll(".mermaid, pre.mermaid, div.mermaid")].map((n) => ({
      tag: n.tagName,
      height: Math.round(n.getBoundingClientRect().height),
      rawVisible: (n.innerText || "").trim().startsWith("erDiagram"),
    })));
  const mermaidVersion = await page.evaluate(() => (window.mermaid && window.mermaid.version) || null);
  await page.screenshot({ path: path.join(__dirname, `cc2_${label}.png`), fullPage: false });
  const result = { label, blocks, blocked: [...new Set(blocked)], errors, mermaidVersion };
  fs.writeFileSync(path.join(__dirname, `cc2_${label}.json`), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
