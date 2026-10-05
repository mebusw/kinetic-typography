#!/usr/bin/env bash
# Post-render gate. The three checks everyone runs — exists, non-empty, duration — all
# pass on a film built with the wrong audio master. This adds the one that does not.
#
#   verify_render.sh renders/episode.mp4 voice   # expects a narration master
#   verify_render.sh renders/episode.mp4 bgm     # expects a bed-only guide master
#   verify_render.sh renders/episode.mp4          # checks only, no loudness band
#
# Optional: --expect-total <seconds> to cross-check against timeline.json's total.
set -uo pipefail

FILE="${1:-}"; KIND="${2:-}"
[ -n "$FILE" ] || { echo "usage: verify_render.sh <file.mp4> [voice|bgm] [--expect-total S]" >&2; exit 2; }
[ -f "$FILE" ] || { echo "FAIL  文件不存在: $FILE" >&2; exit 1; }

SIZE=$(stat -f%z "$FILE" 2>/dev/null || stat -c%s "$FILE")
[ "$SIZE" -gt 0 ] || { echo "FAIL  文件为空" >&2; exit 1; }

probe() { ffprobe -v error -select_streams "$1" -show_entries "$2" -of csv=p=0 "$FILE"; }
VDUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$FILE")
W=$(probe v:0 stream=width); H=$(probe v:0 stream=height)
FRAMES=$(probe v:0 stream=nb_frames); FPS=$(probe v:0 stream=r_frame_rate)
HAS_AUDIO=$(probe a:0 stream=codec_type)

echo "文件    $FILE"
echo "大小    $(( SIZE / 1048576 )) MB"
echo "视频    ${W}x${H} @ ${FPS} · ${FRAMES} 帧 · ${VDUR}s"
echo "音轨    ${HAS_AUDIO:-无}"
rc=0

# ---- 响度判别式：唯一能分辨"渲染的是哪一条母带"的信号 ----
if [ -n "$KIND" ]; then
  LUFS=$(ffmpeg -hide_banner -nostats -i "$FILE" -af ebur128=peak=true -f null /dev/null 2>&1 \
         | awk '/^    I:/{gsub(/ /,"",$2); print $2}' | tail -1)
  PEAK=$(ffmpeg -hide_banner -nostats -i "$FILE" -af ebur128=peak=true -f null /dev/null 2>&1 \
         | awk '/Peak:/{gsub(/ /,"",$2); print $2}' | tail -1)
  echo "响度    ${LUFS:-?} LUFS · 真峰 ${PEAK:-?} dBFS  (期望母带: $KIND)"
  if [ -z "${LUFS:-}" ]; then
    echo "FAIL  读不到响度" >&2; rc=1
  else
    # 有人声 −16..−20 / 纯配乐 −23..−25；出界通常不是"太响"，是**母带选错了**
    case "$KIND" in
      voice) in_band=$(awk -v v="$LUFS" 'BEGIN{print (v>=-21 && v<=-15)?"1":"0"}') ;;
      bgm)   in_band=$(awk -v v="$LUFS" 'BEGIN{print (v>=-27 && v<=-22)?"1":"0"}') ;;
      *)     in_band=1 ;;
    esac
    if [ "$in_band" != "1" ]; then
      echo "FAIL  响度 $LUFS LUFS 不在 '$KIND' 母带区间 —— 大概率渲染成了另一条母带，" >&2
      echo "      而时长/分辨率/帧数全部正常。检查构建时母带轨参数。" >&2
      rc=1
    fi
  fi
  case "$PEAK" in
    -0.*) echo "WARN  真峰 $PEAK dBFS 偏高，AAC 编码后可能过载" >&2 ;;
  esac
fi

# ---- 可选：与 timeline.json 的 total 对齐 ----
if [ "${3:-}" = "--expect-total" ]; then
  EXP="$4"
  if [ -n "$EXP" ]; then
    D=$(awk -v a="$VDUR" -v b="$EXP" 'BEGIN{d=a-b; if(d<0)d=-d; print d}')
    if awk -v d="$D" 'BEGIN{exit !(d<=0.5)}'; then
      echo "片长    $VDUR s（时间轴 $EXP s，差 ${D}s）"
    else
      echo "FAIL  片长 $VDUR s 与时间轴 $EXP s 相差 ${D}s" >&2; rc=1
    fi
  fi
fi

[ $rc -eq 0 ] && echo "✅ 通过" || echo "❌ 未通过" >&2
exit $rc
