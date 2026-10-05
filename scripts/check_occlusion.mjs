#!/usr/bin/env node
// Three overlap checks for a composition with a talking-head slot.
//
//   node check_occlusion.mjs index.html --at 1.2,4.5,8.9 [--selector .fcwrap]
//
// 1. text  vs face-cam   — unreadable copy
// 2. face-cam vs cards  — the screen recording is hidden
// 3. text  vs cards     — both unreadable
//
// Notes that decide whether this is usable:
//   · text is measured with a Range, not its element box. List rows and notes are
//     full-width divs, so box-based checking reports the whole 900px and the report
//     fills with false positives, which is worse than not checking.
//   · the whole sweep runs in ONE page.evaluate. A CDP round trip per seek is what
//     makes a probe time out on a long composition.
//   · sample at 70-90% of each segment. A frame at the segment start lands in the gap
//     before anything animates in and reads as a layout bug that is not there.
// puppeteer-core 通常不在本 skill 的依赖里；按 PUPPETEER_CORE / NODE_PATH 解析，
// 找不到就用 CHROME_PATH 直接调 CDP 浏览器也一样。
let puppeteer;
for (const spec of [process.env.PUPPETEER_CORE, 'puppeteer-core', 'puppeteer'].filter(Boolean)) {
  try { puppeteer = (await import(spec)).default; break; } catch { /* 试下一个 */ }
}
if (!puppeteer) {
  console.error('需要 puppeteer-core。设置 PUPPETEER_CORE=/abs/path/to/puppeteer-core/lib/puppeteer/puppeteer-core.js');
  process.exit(2);
}
import path from 'node:path';

const args = process.argv.slice(2);
const html = args[0];
const times = (args[args.indexOf('--at') + 1] || '').split(',').filter(Boolean).map(Number);
const slotSel = args.includes('--selector') ? args[args.indexOf('--selector') + 1] : '.fcwrap';
const chrome = process.env.CHROME_PATH ||
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

const TEXT_SEL = ['.lead','.sub','.note','.sign','.quote','.chip','.rampline','.rowin',
                  '.xrowin','.srowin','.ctabox','.cchip','.numtx','.bignum','.wipeTx'];

const browser = await puppeteer.launch({
  executablePath: chrome, headless: 'new', protocolTimeout: 900000,
  args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required', '--disable-dev-shm-usage'],
});
const page = await browser.newPage();
await page.setViewport({ width: 1080, height: 1920 });
await page.goto('file://' + path.resolve(html), { waitUntil: 'domcontentloaded', timeout: 120000 });
await page.waitForFunction('!!(window.__timelines && window.__timelines["main"])',
                           { timeout: 120000, polling: 400 });

const rep = await page.evaluate((times, slotSel, TEXT_SEL) => {
  // media → static stub: geometry is what we are measuring, not pixels
  document.querySelectorAll('video,audio').forEach((el) => {
    const ph = document.createElement('div');
    ph.style.cssText = 'width:100%;height:100%;background:#141830';
    ph.dataset.src = el.getAttribute('src') || '';
    if (el.parentNode) el.parentNode.replaceChild(ph, el);
  });
  const tl = window.__timelines['main'];
  const out = [];
  for (const t of times) {
    tl.seek(t, false);
    const slotEl = document.querySelector(slotSel);
    const slot = slotEl ? slotEl.getBoundingClientRect() : null;
    const shells = [...document.querySelectorAll('.shell')]
      .filter((s) => parseFloat(getComputedStyle(s).opacity) > 0.25)
      .map((s) => ({ box: s.getBoundingClientRect(),
                      src: s.querySelector('video')?.dataset.src || 'card' }));
    const texts = [];
    document.querySelectorAll(TEXT_SEL.join(',')).forEach((el) => {
      if (parseFloat(getComputedStyle(el).opacity) < 0.25) return;
      const eb = el.getBoundingClientRect();
      const rng = document.createRange(); rng.selectNodeContents(el);
      const rb = rng.getBoundingClientRect();
      // 用字形真实范围收窄（全宽 div 的盒子会淹掉整个报告）
      const b = (rb.width > 2 && rb.height > 2)
        ? { left: Math.max(eb.left, rb.left), right: Math.min(eb.right, rb.right),
            top: rb.top, bottom: rb.bottom }
        : eb;
      if (b.width < 2 || b.height < 2) return;
      texts.push({ b, cls: String(el.className), txt: (el.textContent || '').trim().slice(0, 24) });
    });
    const hits = [];
    const ov = (a, b) => [Math.min(a.right, b.right) - Math.max(a.left, b.left),
                          Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top)];
    for (const x of texts) {
      if (slot) {
        const o = ov(x.b, slot);
        if (o[0] > 2 && o[1] > 2)
          hits.push({ kind: 'text/face-cam', cls: x.cls, txt: x.txt, ov: o.map(Math.round) });
      }
      for (const s of shells) {
        const o = ov(x.b, s.box);
        if (o[0] > 2 && o[1] > 2)
          hits.push({ kind: 'text/card', cls: x.cls, txt: x.txt, ov: o.map(Math.round) });
      }
    }
    if (slot) for (const s of shells) {
      const o = ov(slot, s.box);
      if (o[0] > 2 && o[1] > 2)
        hits.push({ kind: 'face-cam/card', cls: s.src, txt: '', ov: o.map(Math.round) });
    }
    if (hits.length) out.push({ t, hits });
  }
  return out;
}, times, slotSel, TEXT_SEL);

let bad = 0;
for (const r of rep) {
  bad++;
  console.log(`\nt=${r.t}`);
  for (const h of r.hits)
    console.log(`   [${h.kind}] ${h.cls}${h.txt ? ' | ' + h.txt : ''} | 重叠 ${h.ov.join('x')}px`);
}
console.log(bad === 0
  ? `\n✅ 无遮挡：${times.length} 个采样时刻，三项检查全部干净`
  : `\n❌ ${bad}/${times.length} 个时刻有重叠`);
await browser.close();
process.exit(bad === 0 ? 0 : 1);
