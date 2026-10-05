#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Timeline assertions for a kinetic-typography composition.

The relative/absolute conversion is the highest-value check in this format: a card
authored at 段内 0.8s in a segment that starts at 70.5s fires at 0.8s -- during the title.
Nothing errors, the first segment still looks right, and half the runtime is wrong.

    assert_timeline.py timeline.json
    assert_timeline.py timeline.json --html index.html
"""
import argparse, json, math, re, sys

ABSOLUTE_KEYS = ('lead', 'sub', 'note', 'num', 'box', 'sign', 'quote', 'wipe')
LIST_KEYS = ('chips', 'rows', 'xrows', 'snaprows', 'ramp', 'colchips')


def walk_times(obj, path, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == 't' and isinstance(v, (int, float)):
                out.append((path + '.' + k, float(v)))
            else:
                walk_times(v, path + '.' + k, out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk_times(v, f'{path}[{i}]', out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('timeline')
    ap.add_argument('--html')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()
    tl = json.load(open(a.timeline))
    errs, warns = [], []

    segs = {s['id']: s for s in tl.get('segs', [])}
    if not segs:
        print('ERROR no segs[] in timeline', file=sys.stderr); return 2

    # ---- 1. 卡片必须落在自己的段里（相对/绝对混用的头号杀手）----
    for sid, c in tl.get('content', {}).items():
        seg = segs.get(sid)
        if not seg:
            errs.append(f'{sid}: content 没有对应的 segs 条目'); continue
        for cd in c.get('cards', []):
            t, out = cd.get('t'), cd.get('out')
            if t is None:
                errs.append(f"{cd.get('id')}: 缺 t"); continue
            rel = round(t - seg['start'], 3)
            if not (-0.001 <= rel <= seg['dur'] + 0.001):
                errs.append(f"{cd.get('id')} ({sid}): t={t} 不在段内 "
                            f"[{seg['start']}, {seg['end']}] → 相对 {rel}，"
                            f"看起来像相对时间没有绝对化")
            if out is not None and out < t:
                errs.append(f"{cd.get('id')} ({sid}): out={out} 早于 t={t} —— 卡片永不出现")
            if out is not None and out > seg['end'] + 0.001:
                warns.append(f"{cd.get('id')} ({sid}): out={out} 超出段尾 {seg['end']}")

    # ---- 2. 素材真实时长：卡片不能要求播放超过素材长度 ----
    lengths = {}
    for cd in (cd for c in tl.get('content', {}).values() for cd in c.get('cards', [])):
        lengths.setdefault(cd['src'], []).append(cd)

    # ---- 3. 所有时间必须有限，且在片长内 ----
    total = tl.get('total', 0)
    times = []
    walk_times(tl, '', times)
    for path, t in times:
        if not math.isfinite(t):
            errs.append(f'{path}: 时间不是有限数（NaN/inf）—— 该元素的 tween 永不触发')
        elif t < -0.001 or t > total + 0.001:
            warns.append(f'{path}: t={t} 超出片长 {total}')

    # ---- 4. 淡出必须晚于入场（非-negotiable 5 的自动化形态）----
    for sid, c in tl.get('content', {}).items():
        seg = segs.get(sid)
        if not seg: continue
        for k in LIST_KEYS:
            items = c.get(k) or []
            for i, x in enumerate(items):
                if x['t'] < seg['start'] - 0.001:
                    errs.append(f"{sid}.{k}[{i}]: t={x['t']} 早于段起点 {seg['start']}")
        for k in ABSOLUTE_KEYS:
            d = c.get(k)
            if d and d['t'] < seg['start'] - 0.001:
                errs.append(f"{sid}.{k}: t={d['t']} 早于段起点 {seg['start']}")

    # ---- 5. 音效不能落在片长之外 ----
    for i, cue in enumerate(tl.get('sfx', [])):
        if not math.isfinite(cue['t']):
            errs.append(f"sfx[{i}]: t 非有限数")
        elif cue['t'] > total:
            errs.append(f"sfx[{i}]: t={cue['t']} 超出片长 {total} —— 不会被渲染")

    # ---- 6. 可选：交叉核对 html ----
    if a.html:
        html = open(a.html).read()
        ids = set(re.findall(r'id="([^"]+)"', html))
        for path, t in times:
            m = re.match(r'(.*)\.t$', path)
            if not m: continue
        for sid, c in tl.get('content', {}).items():
            for cd in c.get('cards', []):
                if cd.get('src') and f'src="assets/{cd["src"]}"' not in html:
                    warns.append(f"{cd.get('id')}: 素材 {cd['src']} 没出现在 html 里")

    for w in warns: print('WARN ', w)
    for e in errs: print('ERROR', e)
    n = len(times)
    if not a.quiet:
        print(f'\n{len(segs)} 段 / {n} 个时间点 / {len(tl.get("sfx", []))} 个音效'
              f' · {len(errs)} error, {len(warns)} warning')
    return 1 if errs else 0


if __name__ == '__main__':
    sys.exit(main())
