#!/usr/bin/env node
/**
 * Live-DOM probe: seek the composition to given times, screenshot each one, and
 * dump computed style + geometry for named elements.
 *
 * This is the tooled form of the "clone the element and compare" technique in
 * references/pitfalls.md. It exists because the highest-leverage debugging move
 * in this format — measure the live page instead of theorising about it — is
 * otherwise hand-written as a throwaway puppeteer script every single time.
 *
 *   node probe_dom.mjs index.html --at 1.2,4.5,9
 *   node probe_dom.mjs index.html --at 12 --ids "#ld1","#xr3" --out qa
 *   node probe_dom.mjs index.html --at 72 --clip 0,100,1080,220 --scale 2
 *   node probe_dom.mjs index.html --at 3,8 --json
 *
 * Flags:
 *   --at <t,t,...>     timestamps in seconds (required)
 *   --ids <sel,...>    element selectors to dump (default: every [id] in the doc)
 *   --out <dir>        screenshot directory (default: qa/probe)
 *   --clip <x,y,w,h>   screenshot clip rect, in canvas pixels
 *   --scale <n>        screenshot deviceScaleFactor (default: 1; use 2 to read glyphs)
 *   --timeline <id>    composition id (default: main)
 *   --chrome <path>    Chrome binary (default: $CHROME_PATH, then common macOS paths)
 *   --media            let <video>/<audio> load, so card pixels appear in the shots
 *   --json             machine-readable output
 *   --keep             do not delete previous screenshots in --out
 *
 * Media is blocked by default, and that is load-bearing, not an optimisation.
 * Letting a composition's videos and music bed load makes the page's main thread
 * stall unpredictably under software decode: the same call that returns in 3ms on
 * one run times out at 120s on the next, with no error from the page. Measured on
 * a real composition (10 clips + a 19MB bed): 12s protocol timeouts ~50% of runs
 * without blocking, 0/6 runs with it — seeks then run in single-digit milliseconds.
 * A layout probe only needs the geometry, and blocking media leaves every box at
 * its real size, so nothing is lost. Pass --media when you need the card pixels.
 */
import { mkdirSync, writeFileSync, existsSync, readdirSync, unlinkSync } from "node:fs";
import { resolve, join, basename } from "node:path";
import { statSync } from "node:fs";
import { homedir } from "node:os";
import { execSync } from "node:child_process";
import { pathToFileURL } from "node:url";

const argv = process.argv.slice(2);
const flag = (name, dflt = null) => {
  const i = argv.indexOf(`--${name}`);
  return i === -1 ? dflt : (argv[i + 1]?.startsWith("--") ? true : argv[i + 1]);
};
const has = (name) => argv.includes(`--${name}`);

const file = argv.find((a) => !a.startsWith("--") && !/^\d|,$/.test(a));
if (!file || flag("at") === null) {
  console.error("usage: node probe_dom.mjs <index.html> --at <t,t,...> [--ids <sel,...>] [--out <dir>] [--clip x,y,w,h] [--scale n] [--json]");
  process.exit(2);
}

// ---- canvas size, read from the composition root when present ----
let width = 1080, height = 1920;
try {
  const src = await import("node:fs").then((m) => m.readFileSync(resolve(file), "utf8"));
  const w = src.match(/data-width="(\d+)"/), h = src.match(/data-height="(\d+)"/);
  if (w) width = +w[1];
  if (h) height = +h[1];
} catch { /* fall back to 1080x1920 */ }

const times = String(flag("at")).split(",").map(Number).filter((n) => Number.isFinite(n));
const timelineId = flag("timeline", "main");
const outDir = resolve(flag("out", join("qa", "probe")));
const scale = Number(flag("scale", 1));
const clipArg = flag("clip", null);
const clip = typeof clipArg === "string"
  ? (([x, y, w, h]) => ({ x, y, width: w, height: h }))(clipArg.split(",").map(Number))
  : null;
const explicitIds = typeof flag("ids", null) === "string" ? String(flag("ids")).split(",") : null;

// ---- locate a WORKING puppeteer-core ----
// Several copies live in the npx cache and they are not interchangeable: a copy
// paired with a mismatched Chromium can pass a trivial evaluate and then kill the
// renderer the moment request interception aborts a file:// media request. So every
// candidate is smoke-tested, and the first one that survives is used.
let noIntercept = false;
async function loadPuppeteer(chrome) {
  const candidates = [];
  const glob = `${homedir()}/.npm/_npx`;
  if (existsSync(glob)) {
    const dirs = readdirSync(glob)
      .map((d) => ({ d, m: statSync(join(glob, d)).mtimeMs }))
      .sort((a, b) => b.m - a.m);
    for (const { d } of dirs) {
      candidates.push(`${glob}/${d}/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js`);
    }
  }
  for (const name of ["puppeteer-core", "puppeteer"]) {
    try { candidates.push(import.meta.resolve(name)); } catch { /* not resolvable here */ }
  }

  const tried = [];
  for (const c of candidates) {
    if (!existsSync(c)) continue;
    let mod;
    try { mod = (await import(pathToFileURL(c).href)).default; } catch (e) { tried.push(`${basename(c)}: import failed`); continue; }
    if (typeof mod?.launch !== "function") { tried.push(`${basename(c)}: no launch()`); continue; }
    let browser;
    try {
      browser = await mod.launch({
        headless: "new", executablePath: chrome, protocolTimeout: 20000,
        args: ["--no-sandbox", "--about:blank"],
      });
      const page = await browser.newPage();
      await page.setRequestInterception(true);
      page.on("request", (r) => (r.resourceType() === "media" ? r.abort() : r.continue()).catch(() => {}));
      await page.goto("data:text/html,<video src=x.mp4></video>", { waitUntil: "domcontentloaded" });
      await page.evaluate("1+1");           // the call shape that dies on a bad copy
      await page.screenshot({ path: "/dev/null" }).catch(() => {});
      await browser.close();
      return mod;
    } catch (e) {
      try { await browser?.close(); } catch { /* already gone */ }
      tried.push(`${basename(c)}: ${String(e).split("\n")[0].slice(0, 60)}`);
    }
  }
  // Nothing passed the interception smoke test. Fall back rather than die: media
  // loads, the probe is slower and flakier, but it still measures geometry.
  if (candidates.length) {
    console.error("note: no puppeteer-core passed the media-interception smoke test; retrying without it.\n  tried:\n    " + tried.join("\n    "));
    for (const c of candidates) {
      if (!existsSync(c)) continue;
      try {
        const mod = (await import(pathToFileURL(c).href)).default;
        if (typeof mod?.launch === "function") { noIntercept = true; return mod; }
      } catch { /* try the next one */ }
    }
  }
  console.error("no usable puppeteer-core found. Run `npx hyperframes render` once to populate the npx cache, then retry.\n  tried:\n    " + tried.join("\n    "));
  process.exit(3);
}

function findChrome() {
  const given = flag("chrome", null);
  if (typeof given === "string") return given;
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  const mac = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
  ];
  for (const p of mac) if (existsSync(p)) return p;
  try {
    const out = execSync("command -v google-chrome || command -v chromium || command -v chromium-browser", { shell: "/bin/zsh" })
      .toString().trim();
    if (out) return out;
  } catch { /* not on PATH */ }
  console.error("cannot find a Chrome binary. Pass --chrome <path> or set CHROME_PATH.");
  process.exit(3);
}

const chrome = findChrome();
const puppeteer = await loadPuppeteer(chrome);
mkdirSync(outDir, { recursive: true });
if (!has("keep")) {
  for (const f of readdirSync(outDir)) if (/^probe-.*\.png$/.test(f)) { try { unlinkSync(join(outDir, f)); } catch {} }
}

if (!has("json")) process.stderr.write("probe: launching…\r");
const browser = await puppeteer.launch({
  headless: "new",
  executablePath: chrome,
  protocolTimeout: 120000,
  // NB: deliberately no --autoplay-policy override. Forcing eager autoplay makes a
  // composition with many videos + a music bed decode all of them at once, which can
  // keep the page's main thread busy long enough that the first evaluate times out.
  // A layout probe does not need playback.
  args: ["--no-sandbox", "--allow-file-access-from-files", "--hide-scrollbars", "--mute-audio"],
});
const page = await browser.newPage();
await page.setViewport({ width, height, deviceScaleFactor: scale });

if (!has("media") && !noIntercept) {
  await page.setRequestInterception(true);
  page.on("request", (r) => {
    if (r.resourceType() === "media") r.abort().catch(() => {});
    else r.continue().catch(() => {});
  });
}

const problems = [];
page.on("pageerror", (e) => problems.push("pageerror: " + String(e).slice(0, 300)));
page.on("requestfailed", (r) => problems.push("requestfailed: " + r.url().split("/").pop() + " " + (r.failure()?.errorText || "")));
page.on("console", (m) => { if (m.type() === "warn" || m.type() === "error") problems.push(`console.${m.type()}: ${m.text().slice(0, 200)}`); });

if (!has("json")) process.stderr.write("probe: loading page…\r");
await page.goto(pathToFileURL(resolve(file)).href, { waitUntil: "domcontentloaded" });

// Wait on a CONDITION, not on a fixed sleep. A fixed sleep is a race: sometimes the
// runtime is up, sometimes the main thread is still busy and the first evaluate
// times out with no useful message. Retry the wait itself too.
let ready = false;
for (let attempt = 1; attempt <= 3 && !ready; attempt++) {
  try {
    await page.waitForFunction((id) => !!(window.__timelines && window.__timelines[id]),
      { timeout: 20000 }, timelineId);
    ready = true;
  } catch {
    if (!has("json")) process.stderr.write(`probe: timeline not ready (attempt ${attempt})…\r`);
  }
}
if (!ready) {
  console.error(`window.__timelines["${timelineId}"] never appeared. The runtime script did not load or threw.`);
  for (const p of [...new Set(problems)]) console.error("  " + p);
  await browser.close();
  process.exit(4);
}
const tlDur = await page.evaluate((id) => window.__timelines[id].duration(), timelineId);
await new Promise((r) => setTimeout(r, 200));

const results = [];
for (const t of times) {
  if (!has("json")) process.stderr.write(`probe: seeking ${t}s…\r`);
  await page.evaluate(([tt, id]) => window.__timelines[id].seek(tt, true), [t, timelineId]);
  await new Promise((r) => setTimeout(r, 140));

  const dump = await page.evaluate((sel) => {
    const nodes = sel ? [...document.querySelectorAll(sel)] : [...document.querySelectorAll("[id]")];
    return nodes.map((n) => {
      const s = getComputedStyle(n), r = n.getBoundingClientRect();
      return {
        id: n.id,
        tag: n.tagName.toLowerCase(),
        opacity: +(+s.opacity).toFixed(3),
        rect: [r.x, r.y, r.width, r.height].map((v) => Math.round(v)),
        position: s.position,
        transform: s.transform === "none" ? "" : s.transform,
        filter: s.filter === "none" ? "" : s.filter,
        font: `${s.fontFamily.split(",")[0]} ${s.fontWeight} ${s.fontSize}`,
        text: (n.textContent || "").trim().replace(/\s+/g, " ").slice(0, 42),
      };
    });
  }, explicitIds);

  // elements that claim a full-frame box while sitting outside it
  const strays = dump.filter((d) => d.rect[0] + d.rect[2] <= 1 || d.rect[1] + d.rect[3] <= 1);
  const visible = dump.filter((d) => d.opacity > 0.02 && d.rect[2] > 0 && d.rect[3] > 0);

  const name = `probe-${String(t).replace(".", "_")}s.png`;
  const path = join(outDir, name);
  await page.screenshot(clip ? { path, clip: { ...clip } } : { path });

  results.push({ t, file: path, visible, all: dump, strays });
}

// ---- report ----
if (has("json")) {
  console.log(JSON.stringify({ canvas: { width, height }, duration: tlDur, shots: results, problems }, null, 1));
} else {
  console.log(`canvas ${width}×${height} · timeline "${timelineId}" duration ${Number(tlDur).toFixed(2)}s · ${results.length} frame(s) → ${outDir}\n`);
  for (const r of results) {
    console.log(`── t=${r.t}s  ${r.file}`);
    for (const d of r.visible) {
      const [x, y, w, h] = d.rect;
      const off = x < 0 || y < 0 || x + w > width || y + h > height ? "  ⚠ outside canvas" : "";
      console.log(`   ${d.id.padEnd(12)} op=${String(d.opacity).padEnd(5)} [${String(x).padStart(5)},${String(y).padStart(5)} ${String(w).padStart(5)}×${String(h).padStart(4)}]  ${d.font}  ${d.text}${off}`);
    }
    if (!r.visible.length) console.log("   (nothing visible at this time)");
    if (r.strays.length) console.log(`   ⚠ ${r.strays.length} element(s) collapsed to zero size: ${r.strays.map((s) => s.id).join(", ")}`);
  }
  if (problems.length) {
    console.log("\npage problems:");
    for (const p of [...new Set(problems)]) console.log("  " + p);
  } else {
    console.log("\nno page errors, no failed requests, no GSAP target warnings.");
  }
}
await browser.close();
