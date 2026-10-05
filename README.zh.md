# Kinetic Typography · 竖屏动态文字短视频

[中文](README.zh.md) · **[English](README.md)**

把一份策划稿或口播稿，变成一条**竖屏（9:16）动态文字短视频**——字幕自己会动、素材自己会排、BGM 自己会配，并且**预留好你后期录脸出镜的位置**。

面向人的这份说明只讲三件事：**它做什么、值在哪、怎么用**。
原理、判据和踩坑记录都在给 AI 读的 [`SKILL.md`](SKILL.md) 与 `references/` 里，不需要你翻。

---

## 一、它做什么

给它一份口播稿（哪怕你还没录音），它交付：

| 产出 | 说明 |
|---|---|
| **竖屏成片** | 1080×1920，30fps，文字为主角，有设计的动效，不是套模板字幕 |
| **`打点表.md`** | 每一句话该在第几秒上屏——你照着录口播就能对上画面 |
| **`timeline.json`** | 内容与时间轴的唯一数据源，改一句文案只动这个文件 |
| **音频** | BGM 已按人声电平配好并做了闪避，不抢人声 |

它负责字幕设计、素材剪辑、BGM 配乐与混音；你只管**录口播**和**录脸出镜**。

## 二、值在哪

- **省掉最贵的一步。** 版面问题在抽帧阶段就改完，不靠反复重渲染试错。
- **口播不用等。** 还没录音也能开工；等你录完，节拍已经对好了。
- **改文案很便宜。** 改一句话只动 `timeline.json`，画面自动跟着走。
- **不会静默出错。** 生成阶段自带校验：漏发的元素、越界的卡片、没单位的数值，在渲染前就拦下来。
- **预留录脸位。** 左下或右下按竖屏短边四分之一留好，后期直接贴进去，不用重排版面。
- **混音不吵。** 音乐按人声 RMS 定标并自动闪避，音效单独走不会被压掉。

## 三、怎么用

### 0. 安装

对 Codex 或任何 Agent 说：

```bash
帮我安装这个 SKILL, `npx skills add -g github.com/mebusw/kinetic-typography`
```

### 1. 调用

装在 `~/.agents/skills/kinetic-typography`，在 Codex 里直接说：

```
用 $kinetic-typography 把这份策划稿做成一条竖屏动态文字视频：
  还没录口播，先按口播节奏打点，配 BGM；
  录脸视频后期自己录，一般是正方形或横屏，放在下方左侧或右侧。
```

或者不点名技能，直接描述任务即可自动触发。

### 2. 你需要准备的

**最少只要一份文案。** 其余有就更好：

- 必需：口播稿 / 策划稿
- 可选：照片、录屏素材、片头片尾、品牌色与字体
- 可选：已录的口播或录脸视频（有就直接用，没有它留位）

### 3. 它会来找你确认一次

在动手排版前，它会把 **`打点表.md`** 和视觉方向交给你过一遍。**这是唯一需要你介入的节点**——确认文案和节拍，之后它自己跑到成片。

### 4. 单独用某个工具

五个脚本 + 一个调试探针都能独立跑，全部支持 `--help`：

```bash
S=~/.agents/skills/kinetic-typography/scripts

# 测量分段时间（时长是量出来的，不是按字数估的）
python3 $S/measure_segments.py audio/vo --gap 0.35 --out audio/segments.json

# 渲染前校验时间轴，并自动生成打点表
python3 $S/validate_timeline.py timeline.json --out 打点表.md

# 比对生成结果，抓出「JSON 里有、页面上没有」的元素
python3 $S/validate_timeline.py timeline.json --html index.html

# 静态审查成片代码
node    $S/audit_html.mjs index.html

# 文字颜色对比度（算出来，不靠眼睛）
python3 $S/contrast.py "#7A9086" --bg "#08120E" --suggest

# 配 BGM：按人声 RMS 定标 + 侧链闪避
python3 $S/level_audio.py --voice vo.wav --music bgm.wav --out bed.wav --offset -22 --duck

# 画面不对劲时，直接去运行页面里量
node    $S/probe_dom.mjs index.html --at 1.2,4.5,9
```

新项目从 [`assets/timeline.template.json`](assets/timeline.template.json) 起步。

## 四、里面有什么

```
SKILL.md          主流程与硬规则（给 AI 读）
references/       详细手册：流程、版式与动效、音频、改稿、踩坑
scripts/          6 个可独立运行的工具
assets/           时间轴模板
agents/           UI 显示名与默认提示词
```

## 五、依赖

- Python 3（`contrast.py` 纯标准库，无需第三方包）
- FFmpeg / FFprobe
- Node.js 22+
- HyperFrames CLI（`npx hyperframes`）
- `probe_dom.mjs` 另需本机 Chrome

---

## 许可与维护

技能文件本身可自由取用修改。**它生成的视频里出现的素材版权自负**——录屏、照片、音乐请确认可用范围。

改完记得跑一次自检：

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
```

