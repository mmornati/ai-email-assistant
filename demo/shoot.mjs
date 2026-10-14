// Screenshots for the site, taken from the demo console (website/demo/) on the invented mailbox.
//   python3 -m http.server -d site 8000 &   (after scripts/build-site.sh, or any server mapping / to the site)
//   npm i playwright && node demo/shoot.mjs http://127.0.0.1:8000 docs/assets/screens
// PW_EXE may point at an installed Chromium. Needs cwebp (brew install webp).
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import { mkdirSync, rmSync } from "node:fs";
import { join } from "node:path";

const [base = "http://127.0.0.1:8000", out = "docs/assets/screens"] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const PANELS = [
  ["inbox-before", "step=arrive&shot=inbox", 1200, 1130],
  ["inbox-after", "step=apply&shot=inbox", 1200, 1130],
  ["tasks", "step=apply&shot=tasks", 900, 0],
  ["board", "step=apply&shot=board", 900, 0],
  ["linemap", "step=apply&shot=map", 1300, 0],
  ["terminal-dry-run", "step=preview&shot=terminal", 1100, 0],
  ["terminal-usage", "step=apply&shot=terminal", 1100, 0],
];
const PAGES = [["console-preview", "step=preview"], ["console-apply", "step=apply"], ["console-quiet", "step=quiet"]];

const browser = await chromium.launch(process.env.PW_EXE ? { executablePath: process.env.PW_EXE } : {});
for (const theme of ["light", "dark"]) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 2, colorScheme: theme, reducedMotion: "reduce" });
  const shoot = async (name, query, width, maxHeight) => {
    await page.setViewportSize({ width: width || 1440, height: 1000 });
    await page.goto(`${base}/demo/?${query}&theme=${theme}`, { waitUntil: "networkidle" });
    await page.waitForSelector("html[data-ready]");
    await page.evaluate(() => document.fonts.ready);
    const png = join(out, `${name}-${theme}.png`);
    if (query.includes("shot=")) {
      const box = await page.locator("[data-panel].on").boundingBox();
      await page.screenshot({ path: png, clip: { x: 0, y: box.y, width: box.width, height: maxHeight ? Math.min(maxHeight, box.height) : box.height }, fullPage: true });
    } else {
      await page.screenshot({ path: png });
    }
    execFileSync("cwebp", ["-quiet", "-q", "84", "-resize", String(Math.min(2400, (width || 1440) * 2)), "0", png, "-o", png.replace(/\.png$/, ".webp")]);
    rmSync(png);
    console.log(`${name}-${theme}.webp`);
  };
  for (const [name, q, w, h] of PANELS) await shoot(name, q, w, h);
  for (const [name, q] of PAGES) await shoot(name, q, 1440, 0);
  await page.close();
}
await browser.close();
