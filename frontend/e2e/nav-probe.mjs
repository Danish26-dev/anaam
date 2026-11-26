// Navigation probe: counts full document loads while clicking internal controls.
// Usage: node e2e/nav-probe.mjs [baseUrl]   (uses the installed Microsoft Edge; no browser download)
import { chromium } from "playwright-core";

const base = process.argv[2] ?? "http://127.0.0.1:8765";
const browser = await chromium.launch({ channel: "msedge", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
let loads = 0;
const errors = [];
page.on("load", () => loads++);
page.on("console", (m) => m.type() === "error" && errors.push(m.text().slice(0, 160)));
page.on("pageerror", (e) => errors.push(`pageerror: ${String(e).slice(0, 160)}`));

await page.goto(base + "/", { waitUntil: "networkidle" });
const start = loads;
const steps = [];
// every same-origin link and every button on the landing page, then the studio nav
const internalLinks = await page.$$eval("a[href]", (as) =>
  as.map((a) => ({ text: (a.textContent || "").trim().slice(0, 40), href: a.getAttribute("href") }))
    .filter((a) => a.href && !a.href.startsWith("http")));
for (const l of internalLinks) {
  const before = loads;
  await page.goto(base + "/", { waitUntil: "networkidle" });
  const baseLoads = loads;
  const el = page.locator(`a[href="${l.href}"]`).first();
  if (!(await el.isVisible().catch(() => false))) continue;
  if (l.href.startsWith('#main')) continue;
  await el.click({ timeout: 3000 }).catch(() => {});
  await page.waitForTimeout(600);
  steps.push({ from: "/", click: l.text || l.href, href: l.href, url: page.url().replace(base, ""), fullReload: loads > baseLoads });
  void before;
}
await page.goto(base + "/studio", { waitUntil: "networkidle" });
const navLinks = await page.$$eval("aside a[href]", (as) => as.map((a) => a.getAttribute("href")));
for (const href of navLinks) {
  const b = loads;
  await page.locator(`aside a[href="${href}"]`).first().click({ timeout: 3000 }).catch(() => {});
  await page.waitForTimeout(500);
  steps.push({ from: "studio", click: href, url: page.url().replace(base, ""), fullReload: loads > b });
}
// buttons inside the studio pages
for (const route of ["/studio", "/studio/new", "/studio/inventory", "/studio/identity", "/studio/attacks", "/studio/assurance"]) {
  await page.goto(base + route, { waitUntil: "networkidle" });
  const n = await page.locator("main button, main a[href^='/']").count();
  for (let i = 0; i < Math.min(n, 12); i++) {
    await page.goto(base + route, { waitUntil: "networkidle" });
    const el = page.locator("main button, main a[href^='/']").nth(i);
    if (!(await el.isVisible().catch(() => false))) continue;
    const label = ((await el.textContent()) || "").trim().slice(0, 30);
    const b = loads;
    await el.click({ timeout: 2000 }).catch(() => {});
    await page.waitForTimeout(400);
    if (loads > b) steps.push({ from: route, click: label, url: page.url().replace(base, ""), fullReload: true });
  }
}
// back / forward / direct access
await page.goto(base + "/studio/identity", { waitUntil: "networkidle" });
const direct = await page.locator("h1").first().textContent();
await page.goBack(); await page.waitForTimeout(300);
await page.goForward(); await page.waitForTimeout(300);
const reloadsTotal = steps.filter((s) => s.fullReload);
console.log(JSON.stringify({ internalLinksOnLanding: internalLinks.length, steps: steps.length,
  fullReloads: reloadsTotal, directRouteH1: direct, consoleErrors: [...new Set(errors)].slice(0, 15), loadsSinceStart: loads - start }, null, 2));
await browser.close();
