const fs = require("fs"), path = require("path");
const { chromium } = require("C:/Desarrollo/python/libs/util_bbdd_web/frontend/node_modules/playwright");
(async () => {
  const b = await chromium.launch(); const rep = {};
  for (const [l, s] of [["v12", "mermaid-12.2.0.min.js"], ["v11", "https://unpkg.com/mermaid@11.17.2/dist/mermaid.min.js"]]) {
    const p = await b.newPage();
    await p.goto(`http://127.0.0.1:8765/harness.html?src=${encodeURIComponent(s)}`);
    await p.waitForFunction(() => window.__done, null, { timeout: 120000 });
    rep[l] = await p.evaluate(async () => {
      const out = [];
      for (const c of (await (await fetch("cases.json")).json())) {
        let parse = "ok", text = "";
        try { await window.mermaid.parse(c.text); const r = await window.mermaid.render("r" + out.length, c.text);
              const d = document.createElement("div"); d.innerHTML = r.svg; d.querySelectorAll("style").forEach((x) => x.remove()); text = d.textContent.replace(/\s+/g, " ").trim(); }
        catch (e) { parse = "fail: " + String(e.message || e).split("\n")[0]; }
        out.push({ id: c.id, parse, text });
      }
      return out;
    });
    await p.close();
  }
  await b.close(); fs.writeFileSync(path.join(__dirname, "out", "round3_results.json"), JSON.stringify(rep, null, 1));
})();
