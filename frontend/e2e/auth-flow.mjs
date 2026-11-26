// Human-in-the-loop flow: authorisation is locked while findings are open, each finding needs a
// written review, then a checkbox-confirmed authorisation, then revoke. Client-side navigation only
// (decisions live in memory and are lost on reload by design).
// Usage: node e2e/auth-flow.mjs [baseUrl] [shotDir]
import { chromium } from "playwright-core";

const base = process.argv[2] ?? "http://127.0.0.1:8765";
const shots = process.argv[3];
const browser = await chromium.launch({ channel: "msedge", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
let loads = 0;
page.on("load", () => loads++);
page.on("console", (m) => m.type() === "error" && errors.push(m.text().slice(0, 160)));
page.on("pageerror", (e) => errors.push(`pageerror: ${String(e).slice(0, 160)}`));
const result = {};
const nav = async (href) => { await page.locator(`aside a[href="${href}"]`).first().click(); await page.waitForTimeout(700); };

await page.goto(base + "/workspace", { waitUntil: "networkidle" });
const startLoads = loads;
await nav("/assurance");
const authBtn = page.locator("main button", { hasText: "Authorise release" }).first();
result.lockedWhileOpen = await authBtn.isDisabled();

await nav("/workspace");
let reviewed = 0;
for (let i = 0; i < 20; i++) {
  const btn = page.locator("main button", { hasText: "Mark reviewed" }).first();
  if (!(await btn.count())) break;
  await btn.click();
  const submit = page.locator(".dialog button[type=submit]");
  result.reviewSubmitDisabledWhenEmpty ??= await submit.isDisabled();
  await page.locator("#review-note").fill("Checked in the e2e flow (synthetic data).");
  await submit.click();
  await page.waitForTimeout(400);
  reviewed++;
}
result.reviewed = reviewed;

await nav("/assurance");
result.readinessAfterReview = (await page.locator(".badge").filter({ hasText: /ready|review|blocked/i }).first().textContent())?.trim();
result.unlockedAfterReview = !(await authBtn.isDisabled());
if (result.unlockedAfterReview) {
  await authBtn.click();
  const submit = page.locator(".dialog button[type=submit]");
  result.confirmDisabledWithoutCheckbox = await submit.isDisabled();
  await page.locator(".dialog input[type=checkbox]").check();
  await submit.click();
  await page.waitForTimeout(1500);
  result.authorised = await page.locator("main", { hasText: "Authorised" }).locator("text=Revoke authorisation").count() > 0;
  if (shots) await page.screenshot({ path: `${shots}/assurance-authorised.png` });
  await page.locator("main button", { hasText: "Revoke authorisation" }).click();
  await page.waitForTimeout(400);
  result.revoked = !(await page.locator("main button", { hasText: "Revoke authorisation" }).count());
}
result.fullReloads = loads - startLoads;
result.consoleErrors = [...new Set(errors)];
console.log(JSON.stringify(result, null, 2));
await browser.close();
