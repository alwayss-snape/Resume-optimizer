// Browser walkthrough (P9.4): upload -> Check details -> Review -> Results -> Arrange at 1440 and 390 px,
// light and dark, in the installed Google Chrome. Reports console errors, 5xx responses, horizontal
// overflow, a keyboard move and a mouse hide + Undo in Arrange; screenshots go to .
// Run from web/ against scripts/walkthrough_server.py:  OUT=/tmp/shots node ../scripts/walkthrough.cjs
// LIVE=1 (P9.11): against the real app with the real AI (uvicorn app.api.main:app --port 8010): one
// combination (1440 light unless ONLY says otherwise), drafting allowed up to 6 minutes, the AI's wait
// countdown recorded if the service asks for one, the rewrites counted on Review. Downloads are checked always.
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
const LIVE = Boolean(process.env.LIVE);
const DRAFT_T = LIVE ? 360000 : T;  // the free AI service can make drafting wait a few minutes
(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const report = [];
  const only = process.env.ONLY || (LIVE ? "1440-light" : "");  // e.g. ONLY=390-dark for one combination
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
      // P9.14: the form's two actions sit after both inputs
      notes.push("landing: actions after inputs=" + await page.evaluate(() => {
        const jd = document.querySelector("textarea:not([id$=-paste])"), b = [...document.querySelectorAll("button")].find((x) => x.textContent.trim() === "Just check my match");
        return Boolean(jd && b && (jd.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING));
      }));
      await page.getByRole("button", { name: "Tailor my resume", exact: true }).click();
      await page.getByRole("button", { name: /Looks right, draft rewrites/ }).waitFor();
      notes.push("details: also-read=" + await page.getByText("Also read from your file").count()
        + " unplaced=" + await page.getByText("Lines we couldn't place").count());
      await overflow("2-details");
      await page.getByRole("button", { name: /Looks right, draft rewrites/ }).click();
      // P9.7: a wait from the AI service shows as one countdown line under the running step
      const waits = new Set();
      const t0 = Date.now();
      const watch = setInterval(() => page.locator('[data-testid="wait"] [aria-hidden="true"]').allTextContents()
        .then((t) => t.forEach((x) => waits.add(x.replace(/\d+/g, "N").trim()))).catch(() => {}), 500);
      await page.getByRole("button", { name: "Generate my resume" }).first().waitFor({ timeout: DRAFT_T })
        .finally(() => clearInterval(watch));
      notes.push(`drafting: ${Math.round((Date.now() - t0) / 1000)} s, wait lines seen=${JSON.stringify([...waits])}`);
      const states = await page.locator("article").evaluateAll((cards) => cards.map((c) =>
        (c.textContent.match(/Pass|Check|Kept as is|Will be dropped|Not rewritten|rejected/) || ["?"])[0]));
      const tally = {};
      states.forEach((x) => { tally[x] = (tally[x] || 0) + 1; });
      notes.push("review cards: " + JSON.stringify(tally));
      notes.push("review: conditions=" + await page.getByText("Job conditions").count());
      await overflow("3-review");
      // keyboard: focus the visible Generate button and press Enter
      const gen = page.getByRole("button", { name: "Generate my resume" });
      const n = await gen.count();
      for (let i = 0; i < n; i++) if (await gen.nth(i).isVisible()) { await gen.nth(i).focus(); break; }
      await page.keyboard.press("Enter");
      await page.getByRole("button", { name: /Arrange and edit/ }).waitFor({ timeout: LIVE ? DRAFT_T : 180000 });
      await overflow("4-results");
      for (const name of ["Download PDF", "Download DOCX"]) {
        const button = page.getByRole("button", { name });
        if (!await button.count()) { notes.push(`no "${name}" button`); continue; }
        const [download] = await Promise.all([page.waitForEvent("download"), button.click()]);
        const file = `${S}/${tag}-${download.suggestedFilename()}`;
        await download.saveAs(file);
        notes.push(`${name}: ${download.suggestedFilename()} ${fs.statSync(file).size} bytes`);
      }
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
