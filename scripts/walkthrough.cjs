// Browser walkthrough (P9.4): upload -> Check details -> Review -> Results -> Arrange at 1440 and 390 px,
// light and dark, in the installed Google Chrome. Reports console errors, 5xx responses, horizontal
// overflow, a keyboard move and a mouse hide + Undo in Arrange; screenshots go to .
// Run from web/ against scripts/walkthrough_server.py:  OUT=/tmp/shots node ../scripts/walkthrough.cjs
const path = require("path");
const { chromium } = require(path.join(__dirname, "../web/node_modules/playwright-core"));
const fs = require("fs");
const R = path.join(__dirname, "..") + "/";
const S = process.env.OUT || "/tmp/tailores-walkthrough";
const BASE = process.env.BASE || "http://127.0.0.1:8010/";
fs.mkdirSync(S + "/shots", { recursive: true });
const RESUME = R + "docs/user_testing/2026-10-02/resumes/nurse.docx";
const JD = fs.readFileSync(R + "data/eval/personas/nurse/jd.txt", "utf8");
const T = 60000;
(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const report = [];
  const only = process.env.ONLY;  // e.g. ONLY=390-dark for one combination
  for (const [w, h] of [[1440, 900], [390, 844]]) for (const scheme of ["light", "dark"]) {
    if (only && only !== `${w}-${scheme}`) continue;
    const tag = `${w}-${scheme}`, notes = [];
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, colorScheme: scheme });
    const page = await ctx.newPage();
    page.setDefaultTimeout(T);
    page.on("console", (m) => { if (m.type() === "error") notes.push("console: " + m.text().slice(0, 200)); });
    page.on("pageerror", (e) => notes.push("pageerror: " + String(e).slice(0, 200)));
    page.on("response", (r) => { if (r.status() >= 500) notes.push(`HTTP ${r.status()} ${r.url()}`); });
    const overflow = async (step) => {
      await page.waitForTimeout(1500);  // let entrance animations settle
      const o = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      if (o > 1) notes.push(`${step}: horizontal overflow ${o}px`);
      const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
      await page.screenshot({ path: `${S}/shots/${tag}-${step}.png`, fullPage: false });
      return bg;
    };
    try {
      await page.goto(BASE, { waitUntil: "networkidle" });
      const bg = await overflow("1-landing");
      notes.push(`body background ${bg}`);
      await page.locator('input[type="file"]').setInputFiles(RESUME);
      await page.getByLabel("The job description").fill(JD);
      await page.getByRole("button", { name: "Read my resume" }).click();
      await page.getByRole("button", { name: /Looks right, draft rewrites/ }).waitFor();
      notes.push("details: also-read=" + await page.getByText("Also read from your file").count()
        + " unplaced=" + await page.getByText("Lines we couldn't place").count());
      await overflow("2-details");
      await page.getByRole("button", { name: /Looks right, draft rewrites/ }).click();
      await page.getByRole("button", { name: "Generate my resume" }).first().waitFor();
      notes.push("review: conditions=" + await page.getByText("Job conditions").count());
      await overflow("3-review");
      // keyboard: focus the visible Generate button and press Enter
      const gen = page.getByRole("button", { name: "Generate my resume" });
      const n = await gen.count();
      for (let i = 0; i < n; i++) if (await gen.nth(i).isVisible()) { await gen.nth(i).focus(); break; }
      await page.keyboard.press("Enter");
      await page.getByRole("button", { name: /Arrange and edit/ }).waitFor({ timeout: 180000 });
      await overflow("4-results");
      await page.getByRole("button", { name: /Arrange and edit/ }).click();
      await page.getByLabel("Sections, in order").waitFor();
      await overflow("5-arrange");
      const ups = page.getByRole("button", { name: /^Move .* down$/ });
      notes.push("arrange: move-down buttons=" + await ups.count());
      if (await ups.count()) {
        const first = page.getByLabel("Sections, in order").locator("li").first();
        const before = (await first.textContent()).slice(0, 40);
        await ups.first().focus(); await page.keyboard.press("Enter");
        await page.waitForTimeout(1500);
        const after = (await page.getByLabel("Sections, in order").locator("li").first().textContent()).slice(0, 40);
        notes.push(`arrange keyboard move: first section "${before}" -> "${after}"`);
        const focused = await page.evaluate(() => document.activeElement?.getAttribute("aria-label"));
        notes.push(`focus after move: ${focused}`);
      }
      // mouse: hide the Summary section, then Undo
      const show = page.getByLabel("Show Summary");
      if (await show.count()) {
        await show.first().click();
        await page.waitForTimeout(1500);
        notes.push("mouse hide: Summary shown=" + await show.first().isChecked());
        await page.getByRole("button", { name: "Undo" }).click();
        await page.waitForTimeout(1500);
        notes.push("after Undo: Summary shown=" + await show.first().isChecked());
      } else notes.push("no 'Show Summary' control found");
      await overflow("6-arranged");
    } catch (e) {
      notes.push("FAILED: " + String(e).split("\n")[0].slice(0, 300));
      await page.screenshot({ path: `${S}/shots/${tag}-failed.png` }).catch(() => {});
    }
    report.push({ tag, notes });
    await ctx.close();
  }
  await browser.close();
  console.log(JSON.stringify(report, null, 1));
})();
