// Measure and screenshot the brief at printed A4 size: content width 188 mm, page height 279 mm.
import { chromium } from "playwright-core";
import { pathToFileURL } from "node:url";
const [html, outDir] = process.argv.slice(2);
const mm = 96 / 25.4;
const b = await chromium.launch({ channel: "msedge", headless: true });
const page = await b.newPage({ viewport: { width: Math.round(188 * mm), height: 1200 }, deviceScaleFactor: 2 });
await page.emulateMedia({ media: "print" });
await page.goto(pathToFileURL(html).href, { waitUntil: "load" });
await page.waitForTimeout(500);
const info = await page.evaluate(() => {
  const pb = document.querySelector(".pagebreak");
  const r = (el) => Math.round(el.getBoundingClientRect().top + window.scrollY);
  return { total: document.documentElement.scrollHeight, pagebreak: pb ? r(pb) : null,
           sections: [...document.querySelectorAll("h2, figure")].map((e) => [e.textContent.trim().slice(0, 30), r(e), Math.round(e.getBoundingClientRect().height)]) };
});
const pageH = Math.round(279 * mm);
console.log(JSON.stringify({ pageHeightPx: pageH, ...info }, null, 1));
const p1 = info.pagebreak ?? pageH;
await page.screenshot({ path: `${outDir}/brief-p1.png`, clip: { x: 0, y: 0, width: Math.round(188 * mm), height: Math.min(p1, info.total) }, fullPage: true });
const s2 = info.pagebreak ?? pageH; if (info.total > s2) await page.screenshot({ path: `${outDir}/brief-p2.png`, clip: { x: 0, y: s2, width: Math.round(188 * mm), height: info.total - s2 }, fullPage: true });
await b.close();
