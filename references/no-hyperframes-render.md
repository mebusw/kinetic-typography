# 没有 hyperframes 时：自建确定性渲染链 + 素材剪辑

本技能默认有 `/hyperframes-core` / `/hyperframes-cli`。**不是每个环境都有。**
这一篇是六集竖屏真人口播在没有 CLI 的情况下完整交付出来的做法——
渲染链、探针、以及"素材剪辑"这一整块本来由 CLI 承担、现在得自己写的部分。

判定条件：`which hyperframes` 为空、且 `~/.workbuddy/skills/_agents/` 下没有
`hyperframes-core`。这时候不要退化成"用 ffmpeg 硬拼"——那会丢掉整套 QA 门禁。

---

## A. 渲染链：GSAP timeline + Chromium + 逐帧截图

核心思路：**合成仍然是 HTML + 一条暂停的 GSAP 主时间轴，只是不靠实时播放出片，
而是逐帧 `seek(t)` 后截图，把 PNG 流直接喂给 ffmpeg。**

```
timeline.json → build.mjs → index.html（GSAP paused timeline）
                                ↓
        Playwright/Chromium  page.evaluate(__seek(t)) → page.screenshot()
                                ↓  PNG 流
        ffmpeg -f image2pipe -framerate 30 -i - -i mix.wav → out.mp4
```

这样做的好处是**确定性**：同一份 `timeline.json` 永远出同一批帧，不受机器负载影响；
而且是"渲染一次"的前提——版面问题必须在截图前解决掉。

### 必须暴露的页面接口

生成器要在 `index.html` 里挂上这五个，QA 与渲染共用同一套：

```js
window.__TOTAL__                    // 总时长
window.__SEGS__                     // [{id,t0,t1}...] 供 QA 抽样
window.__seek(t) = async (t) => {}  // 主时间轴 seek + 所有 <video> 同步 seek
window.__ready() = async () => {}   // 等所有 video loadeddata，再 pause
window.__geom(ids)                  // 返回指定 id 的真实几何（含 opacity）
```

`__seek` 里两件事别忘了：
1. `if (!isFinite(t)) t = 0` —— 一个 `NaN` 会让整条时间轴静默停在原地。
2. **每个 `<video>` 都要按绝对时间 seek 并 `await` 到 `seeked`**，
   否则逐帧截图会拍到没跟上帧的视频（表现为卡片是黑的或者一直第一帧）。

### 成本预算（实测，M 系列 / Chromium headless）

| 项 | 实测 |
|---|---|
| `page.screenshot()` PNG | ≈ 42 ms/帧 |
| `page.screenshot()` JPEG | ≈ 21 ms/帧 |
| 视频 seek + 双 rAF | ≈ 13 ms/帧 |
| 合计 | ≈ 47 ms/帧 → **111s @30fps 约 90 秒** |

所以：一集一分钟半的片子 ≈ 一分半钟渲染。**这恰好证明了"截图先验版面"的必要性**——
六集各渲染一次是 15 分钟，任何一集因为版面问题重渲染一次就是 1.5 分钟白烧。

渲染跑在**前台**（non-negotiable 8），多集再外层用 bash 循环串起来。

###看不到画面时怎么办

有些环境（含部分预览模型）**无法查看图片**。这时候"截图自己看一眼"这条
non-negotiable 11 失效，必须把每一条视觉检查**换算成数值检查**，否则就是裸奔：

| 原来的做法 | 换成 |
|---|---|
| 看接触表找压字 | `check_occlusion` 的四类重叠（几何 + 阈值） |
| 看字号够不够 | 量叶子节点的 `fontSize`，< 28px 报错 |
| 看有没有出安全区 | 量 `top/bottom` 与 `meta.safe` 比较 |
| 看元素有没有按时上场 | `--geom "t=54.3:id1,id2"` 打印该时刻每个 id 的框与 opacity |
| 看画面糊不糊/黑不黑 | 对源素材**逐秒量平均亮度**，见下面 B 节 |

`--geom` 是最有用的一条：它把"我觉得这里挤了"变成
`b1h y 226→458` 和 `b1l y 400→458` 两个数字，重叠一眼可见。
六集所有版面 bug 都是这么抓出来的，一次都没有靠肉眼。

---

## B. 素材剪辑

### 选片段前先逐秒量亮度

录屏里翻页、切窗口的那几秒是**暗场/过渡帧**。凭时间码挑的"第 4–9 秒"很可能正好是黑的。
切素材之前先跑一遍：

```bash
ffmpeg -i src.mov -vf "fps=1,scale=64:36,format=gray" -f rawvideo - 2>/dev/null \
| python3 -c "
import sys
d=sys.stdin.buffer.read()
for i,b in enumerate(d):
    v=b/255
    print(f'{i:3d}s {v:.2f} ' + ('#'*int(v*40)))
"
```

实测一份 45 秒的翻页录屏：0–1、9–10、28–29、35–36 秒是暗的，4–8、11–27、30–33 是亮的。
**所有卡片片段都只从亮区取**，这一步省掉了六集返工。

### 每个片段量一次真实宽高，存进 manifest

`ffprobe` 一次，把 `width/height/dur/aspect` 写进 `assets-manifest.json`，
卡片高度一律由 `h = w / aspect` 算出来。手写高度是"16:9 的图被拉成长条、
竖屏录屏被压成一条"的唯一原因。

### 多段拼接：音视频交错输入

一次 `filter_complex` 拼接时，输入必须**交错**：

```
[v0][a0][v1][a1][v2][a2] concat=n=3:v=1:a=1
```

写成 `[v0][v1][v2][a0][a1][a2]` 是最常见的错法——ffmpeg 不报错，
出来的是画面接对了、声音错位或者整段静音。

统一输出 `30fps / crf18 / yuv420p`，避免后面合成时再转一次。

### 长录屏在系列里"分段 + 变长"

同一份 60 秒的图例墙滚动，六集都要用。除了"各取一段不同区间"，**还要取不同的长度**
（8.0s / 10.5s / 5.97s / 8.0s）：两个都是 8 秒的窗口，即使区间不同，
节奏和停留位置看着仍然是同一个镜头。

### 收紧（tighten）用的参数

```bash
silencedetect=noise=-38dB:d=0.30
PAD     = 0.18   # 保留的停顿头
TARGET  = 0.40   # 留白压到 0.40s
```

口误/重复起头另外给 `--slips` 区间（先听一遍标出来），和静音段合并后一起剪。
**剪完必须重新转录**——见 `references/real-voiceover.md`，时间轴只能从剪后的稿子解。
