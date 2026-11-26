// Visit every route and click every internal control; print uncaught errors with stacks.
import { chromium } from "playwright-core";

const base = process.argv[2] ?? "http://127.0.0.1:8765";
const routes = process.argv.slice(3).length ? process.argv.slice(3) : ["/", "/studio", "/studio/new", "/studio/inventory",
  "/studio/clinical", "/studio/identity", "/studio/attacks", "/studio/assurance"];
const browser = await chromium.launch({ channel: "msedge", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const seen = new Map();
let where = "";
page.on("pageerror", (e) => { const k = String(e.stack || e).slice(0, 900); if (!seen.has(k)) seen.set(k, where); });
page.on("console", async (m) => { if (m.type() === "error") { const args = await Promise.all(m.args().map((a) => a.jsonValue().catch(() => "?"))); const k = "console: " + args.map(String).join(" | ").slice(-700); if (!seen.has(k)) seen.set(k, where); } });
for (const r of routes) {
  where = `load ${r}`;
  await page.goto(base + r, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  const n = await page.locator("a[href^='/'], a[href^='#'], button").count();
  for (let i = 0; i < n; i++) {
    await page.goto(base + r, { waitUntil: "networkidle" });
    const el = page.locator("a[href^='/'], a[href^='#'], button").nth(i);
    if (!(await el.isVisible().catch(() => false))) continue;
    where = `${r} click #${i} "${((await el.textContent()) || "").trim().slice(0, 30)}"`;
    await el.click({ timeout: 2500 }).catch(() => {});
    await page.waitForTimeout(500);
  }
}
for (const [k, w] of seen) console.log(`--- ${w}\n${k}\n`);
console.log(`errors: ${seen.size}`);
await browser.close();
