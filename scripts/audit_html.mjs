#!/usr/bin/env node
/**
 * Static audit of a generated HyperFrames composition, for the failure modes
 * that produce a wrong video with no error anywhere.
 *
 *   node audit_html.mjs index.html
 *   node audit_html.mjs index.html --json
 *
 * This is a supplement to `npx hyperframes check`, not a replacement: that one
 * knows about contrast and overlap, this one knows about the ways a *generated*
 * composition silently drops content or strands an element on screen.
 */
import { readFileSync } from "node:fs";
import { basename } from "node:path";

const args = process.argv.slice(2);
const file = args.find((a) => !a.startsWith("--"));
const asJson = args.includes("--json");
if (!file) {
  console.error("usage: node audit_html.mjs <index.html> [--json]");
  process.exit(2);
}

let src;
try {
  src = readFileSync(file, "utf8");
} catch (e) {
  console.error(`cannot read ${file}: ${e.message}`);
  process.exit(2);
}

const findings = [];
const add = (level, code, msg) => findings.push({ level, code, msg });

const stripComments = src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/<!--[\s\S]*?-->/g, "");

/* ---------- ids ---------- */
const definedIds = new Set([...stripComments.matchAll(/\bid\s*=\s*["']([^"']+)["']/g)].map((m) => m[1]));
const dupes = [...stripComments.matchAll(/\bid\s*=\s*["']([^"']+)["']/g)]
  .map((m) => m[1])
  .filter((v, i, a) => a.indexOf(v) !== i);
if (dupes.length) {
  add("error", "duplicate-id",
    `id(s) defined more than once: ${[...new Set(dupes)].slice(0, 10).join(", ")} — a duplicate id silently misdirects every animation that targets it`);
}

/* Selectors the runtime addresses that nothing in the document defines. */
/* A bare #token inside inline styles is a CSS colour, not a selector:
   #B8F04A, #E9F2E8, #E07FB8. Requiring a leading letter AND excluding the
   hex-colour shapes keeps those out of the orphan report. */
const HEX_COLOUR = /^(?:[0-9A-Fa-f]{8}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3,4})$/;
const selectorIds = new Set(
  [...stripComments.matchAll(/(?:^|[^\w-])#([A-Za-z_][\w-]*)/g)]
    .map((m) => m[1])
    .filter((id) => !HEX_COLOUR.test(id) && !id.startsWith("root") && !/^(root|stage|clip)$/i.test(id)),
);
const orphans = [...selectorIds].filter((id) => !definedIds.has(id));
if (orphans.length) {
  add("error", "unresolved-selector",
    `selector(s) target ids that are never defined: ${orphans.slice(0, 12).join(", ")}${orphans.length > 12 ? " …" : ""} — this is what "arithmetic id recycling" produces: the runtime logs one "target not found" and the art is silently wrong`);
}

/* ---------- video elements ---------- */
for (const m of stripComments.matchAll(/<video\b([^>]*)>/gi)) {
  const attrs = m[1];
  if (!/\bid\s*=/.test(attrs)) {
    add("error", "video-without-id",
      `a <video> has no id: ${attrs.trim().slice(0, 70)} — the frame renders FROZEN (a still) without one`);
  }
  if (/\btransform\s*:/i.test(attrs) || /\bstyle\s*=[^>]*transform/i.test(attrs)) {
    add("error", "transformed-video",
      `a transform is applied to the <video> itself: ${attrs.trim().slice(0, 70)} — animate the untimed wrapper div instead, or the picture is misplaced and miscropped`);
  }
}

/* ---------- unitless CSS values in generated code ---------- */
const UNITLESS = /(?:^|[\s;,(])(width|height|top|left|right|bottom|font-size|gap|padding|margin|border-radius|letter-spacing|line-height)\s*:\s*(\d+(?:\.\d+)?)(?=\s*[;}\s,)])/gi;
const unitless = [];
for (const m of stripComments.matchAll(UNITLESS)) {
  const v = parseFloat(m[2]);
  const ok = m[1].toLowerCase() === "line-height" || m[1].toLowerCase() === "z-index";
  if (!ok && !(v === 0)) unitless.push(`${m[1]}: ${m[2]}`);
}
if (unitless.length) {
  add("error", "unitless-css",
    `CSS numeric value(s) with no unit: ${[...new Set(unitless)].slice(0, 10).join("; ")} — a bare number is an implicit syntax error that HTML renders anyway; the element silently gets the wrong size`);
}

/* ---------- animation on layout properties ---------- */
for (const prop of ["left", "top", "width", "height", "margin", "padding"]) {
  const re = new RegExp(`(?:gsap\\.(?:to|from|fromTo|set)|tween|animate)\\s*\\([^)]*\\{[^}]*\\b${prop}\\s*:`, "g");
  const hits = [...stripComments.matchAll(re)];
  if (hits.length) {
    add("error", "layout-animation",
      `animation targets layout property \`${prop}\` (${hits.length} site(s)) — animate transform and opacity only; layout properties quantize to whole pixels and stutter during render`);
  }
}

/* ---------- non-finite times ---------- */
const nonFinite = [
  ...stripComments.matchAll(/\b(t|t0|t1|start|at|time|dur|duration)\s*[:=]\s*(NaN|undefined|null|Infinity)\b/gi),
  // A bare non-finite literal passed as a tween's position argument:
  //   gsap.to("#el", { opacity: 0 }, NaN)
  ...stripComments.matchAll(/\.(?:to|from|fromTo|set)\s*\([^()]*,\s*(NaN|undefined|null|Infinity)\s*[,)]/g),
];
if (nonFinite.length) {
  add("error", "non-finite-time",
    `${nonFinite.length} time argument(s) are NaN/undefined/null — the tween never fires, so the element never leaves and sits on screen for the whole film`);
}

/* ---------- fromTo / immediateRender hazards ---------- */
let immediate = 0;
for (const m of stripComments.matchAll(/immediateRender\s*:\s*true/gi)) immediate++;
if (immediate) {
  add("warn", "immediate-render",
    `${immediate} fromTo/immediateRender:true — the "from" state applies at seek(0), so if the fade-out is scheduled before the fade-in completes, the element is stranded on screen for the whole film. Route fades through one fadeOut() helper that computes max(end - tail, tIn + durIn + eps).`);
}

/* A fadeOut whose start is a literal could not be verified without running it;
   flag the shape that is safe by construction and the shape that is not. */
if (/\.to\s*\([^)]*opacity\s*:\s*0/.test(stripComments) && !/function\s+fadeOut|fadeOut\s*=\s*\(|const\s+fadeOut/.test(stripComments)) {
  add("warn", "no-fade-helper",
    "no fadeOut() helper found, but opacity-to-0 tweens exist — consolidate them into one helper that guarantees the fade-out starts after the fade-in ends");
}

/* ---------- elements that fade in but never fade out ----------
   The group-fade bug: a "19 + dot matrix" beat faded out the number and the
   label but not the 19 individual dots, so the grid stayed on screen for the
   rest of the film. A warn, because a deliberately persistent element
   (progress rail, step track) legitimately has no fade-out. */
const idsOf = (arg) =>
  [...arg.matchAll(/#([A-Za-z_][\w-]*)/g)].map((m) => m[1]);

const fadedIn = new Map();   // id -> the tween text that faded it in
const fadedOut = new Set();

for (const m of stripComments.matchAll(/\.fromTo\s*\(\s*(\[[^\]]*\]|"[^"]*"|'[^']*')\s*,\s*\{([\s\S]*?)\}\s*,\s*\{([\s\S]*?)\}\s*,/g)) {
  const [, sel, fromVars, toVars] = m;
  if (!/opacity\s*:\s*0/.test(fromVars)) continue;
  if (/opacity\s*:\s*0/.test(toVars)) continue;      // that is a fade-out in disguise
  for (const id of idsOf(sel)) fadedIn.set(id, m[0].replace(/\s+/g, " ").slice(0, 90));
}
for (const m of stripComments.matchAll(/\.(?:to|set)\s*\(\s*(\[[^\]]*\]|"[^"]*"|'[^']*')\s*,\s*\{([\s\S]*?)\}/g)) {
  if (!/opacity\s*:\s*0/.test(m[2])) continue;
  for (const id of idsOf(m[1])) fadedOut.add(id);
}
const strandedByGroup = [...fadedIn.keys()].filter((id) => !fadedOut.has(id));
if (strandedByGroup.length) {
  add("warn", "never-fades-out",
    `${strandedByGroup.length} element(s) fade in but nothing ever fades them out: ${strandedByGroup.slice(0, 12).join(", ")}${strandedByGroup.length > 12 ? " \u2026" : ""}\n` +
    `      Check each against its DOM parent before acting. Legitimate: it is a CHILD of an element that does fade out, and inherits it. ` +
    `Real strand: a sibling or standalone mark in a group whose parent and label fade but whose children do not \u2014 the dot-matrix case, where a "19 + 19 dots" beat faded the number and left the grid on screen for the rest of the film. Collect every child into one selector array and fade them together. ` +
    `Intended persistence: say so explicitly with set(opacity:0) at t=0 and a fade-out after the last segment that uses it.`);
}

/* ---------- report ---------- */
const errors = findings.filter((f) => f.level === "error");
const warns = findings.filter((f) => f.level === "warn");

if (asJson) {
  console.log(JSON.stringify({ file: basename(file), errors, warnings: warns }, null, 2));
} else {
  console.log(`audit ${file}: ${definedIds.size} ids defined · ${selectorIds.size} ids referenced\n`);
  for (const f of findings) {
    console.log(`${f.level.toUpperCase().padEnd(5)} [${f.code}] ${f.msg}`);
  }
  if (!findings.length) console.log("no static hazards found");
  console.log(`\n${errors.length} error(s), ${warns.length} warning(s)`);
  console.log("This is a static audit. It cannot see layout, overlap, or contrast —");
  console.log("run `npx hyperframes check`, then snapshot every segment, then render once.");
}

process.exit(errors.length ? 1 : 0);
