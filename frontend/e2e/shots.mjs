// Screenshots of routes in the installed Edge, after the page settles; prints console errors.
// Usage: node e2e/shots.mjs <outDir> <width>x<height> <route> [route...]
import { chromium } from "playwright-core";
import { mkdirSync } from "node:fs";

const [outDir, size, ...routes] = process.argv.slice(2);
const [w, h] = size.split("x").map(Number);
const base = process.env.BASE ?? "http://127.0.0.1:8765";
mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch({ channel: "msedge", headless: true, args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const page = await browser.newPage({ viewport: { width: w, height: h }, reducedMotion: process.env.REDUCED ? "reduce" : "no-preference" });
const errors = [];
page.on("pageerror", (e) => errors.push(`pageerror ${String(e).slice(0, 200)}`));
page.on("console", (m) => m.type() === "error" && errors.push(`console ${m.text().slice(0, 200)}`));
for (const r of routes) {
  const [path, action] = r.split("@");
  await page.goto(base + path, { waitUntil: "networkidle" });
  await page.waitForTimeout(Number(process.env.WAIT ?? 2500));
  if (action) {
    for (const sel of action.split("|")) { await page.locator(sel).first().click({ timeout: 3000 }).catch(() => {}); await page.waitForTimeout(700); }
  }
  const name = (path.replace(/[/?=&#]+/g, "_").replace(/^_|_$/g, "") || "landing") + (action ? "_act" : "");
  await page.screenshot({ path: `${outDir}/${name}.png`, fullPage: !!process.env.FULL });
  console.log(`${r} -> ${name}.png`);
}
console.log(`errors: ${errors.length}`);
for (const e of [...new Set(errors)].slice(0, 10)) console.log("  " + e);
await browser.close();
