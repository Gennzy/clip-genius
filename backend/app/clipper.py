"""Render vertical 9:16 clips with burned-in subtitles and watermark."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import WATERMARK_TEXT
from .highlights import Highlight
from .transcribe import Word


@dataclass
class RenderedClip:
    path: Path
    subtitle_path: Path


def _fmt_ass_time(t: float) -> str:
    if t < 0:
        t = 0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t - h * 3600 - m * 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _group_words(words: list[Word], max_chars: int = 22, max_words: int = 4) -> list[tuple[float, float, str]]:
    """Group words into short phrase-level subtitle chunks."""
    groups: list[tuple[float, float, str]] = []
    if not words:
        return groups
    cur: list[Word] = []
    for w in words:
        prospective = (" ".join(x.text for x in cur) + " " + w.text).strip()
        if cur and (len(prospective) > max_chars or len(cur) >= max_words):
            groups.append((cur[0].start, cur[-1].end, " ".join(x.text for x in cur)))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        groups.append((cur[0].start, cur[-1].end, " ".join(x.text for x in cur)))
    return groups


def _build_ass(highlight: Highlight, watermark: str) -> str:
    # Times are relative to the start of the highlight (we seek via ffmpeg -ss
    # and remux, so the clip begins at t=0 after the cut).
    groups = _group_words(highlight.words)
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,DejaVu Sans,74,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,6,2,2,80,80,280,1
Style: Watermark,DejaVu Sans,38,&H99FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,1,2,40,40,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    duration = max(0.5, highlight.end - highlight.start)
    for g_start, g_end, text in groups:
        rel_start = max(0.0, g_start - highlight.start)
        rel_end = min(duration, max(rel_start + 0.3, g_end - highlight.start))
        safe = text.replace("\n", " ").replace("{", "(").replace("}", ")")
        lines.append(
            f"Dialogue: 0,{_fmt_ass_time(rel_start)},{_fmt_ass_time(rel_end)},Caption,,0,0,0,,{safe}\n"
        )
    # Watermark shown for the full clip duration.
    lines.append(
        f"Dialogue: 0,{_fmt_ass_time(0)},{_fmt_ass_time(duration)},Watermark,,0,0,0,,{watermark}\n"
    )
    return "".join(lines)


def render_clip(
    *,
    source_video: Path,
    highlight: Highlight,
    workdir: Path,
    index: int,
    watermark: str | None = None,
) -> RenderedClip:
    """Cut the source, reframe to 9:16, burn subs and watermark, encode."""
    watermark = watermark or WATERMARK_TEXT
    clips_dir = workdir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    out_path = clips_dir / f"clip_{index:02d}.mp4"
    ass_path = clips_dir / f"clip_{index:02d}.ass"
    ass_path.write_text(_build_ass(highlight, watermark), encoding="utf-8")

    # Reframe: scale source so its height fills 1920, then center-crop width to 1080.
    # If the source is portrait, this still works (it will just pad with scale).
    vf = (
        "scale=-2:1920,crop=1080:1920:(in_w-1080)/2:0,"
        f"ass='{ass_path.as_posix()}'"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{highlight.start:.3f}",
        "-to",
        f"{highlight.end:.3f}",
        "-i",
        str(source_video),
        "-vf",
        vf,
        "-r",
        "30",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "22",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return RenderedClip(path=out_path, subtitle_path=ass_path)
