"""Fetch source video (local upload or URL) and extract a mono 16kHz WAV."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import (
    YT_DLP_COOKIES_FILE,
    YT_DLP_COOKIES_FROM_BROWSER,
    YT_DLP_EXTRACTOR_ARGS,
)


@dataclass
class SourceMedia:
    video_path: Path
    audio_path: Path
    duration: float
    title: str


class YtDlpError(RuntimeError):
    """yt-dlp failed in a way we can surface to the end user."""


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def _run_yt_dlp(args: list[str]) -> subprocess.CompletedProcess:
    """Run yt-dlp with our shared auth/extractor flags, raising YtDlpError on failure."""
    base = ["yt-dlp", "--no-playlist", "--restrict-filenames", "--retries", "3"]
    if YT_DLP_EXTRACTOR_ARGS:
        base += ["--extractor-args", YT_DLP_EXTRACTOR_ARGS]
    if YT_DLP_COOKIES_FILE:
        base += ["--cookies", YT_DLP_COOKIES_FILE]
    if YT_DLP_COOKIES_FROM_BROWSER:
        base += ["--cookies-from-browser", YT_DLP_COOKIES_FROM_BROWSER]

    proc = subprocess.run(base + args, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise YtDlpError(_friendly_ytdlp_error(proc.stderr))
    return proc


_BOT_CHECK_RE = re.compile(r"sign in to confirm|confirm.+not a bot", re.IGNORECASE)


def _friendly_ytdlp_error(stderr: str) -> str:
    """Collapse yt-dlp stderr into something we can show in the UI."""
    lines = [ln for ln in (stderr or "").splitlines() if ln.strip()]
    # Find the last `ERROR:` line yt-dlp emitted.
    last_error = next((ln for ln in reversed(lines) if ln.lstrip().startswith("ERROR")), "")
    short = last_error or (lines[-1] if lines else "yt-dlp exited with non-zero status")

    if _BOT_CHECK_RE.search(short):
        return (
            "YouTube is blocking the download with a bot check. "
            "Upload the file directly, or set the CLIPGENIUS_YT_DLP_COOKIES_FILE "
            "env var to a Netscape cookies.txt exported from a signed-in browser "
            "(see README → Troubleshooting)."
        )
    return f"yt-dlp: {short.removeprefix('ERROR: ').strip()}"


def probe_duration(path: Path) -> float:
    res = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ]
    )
    data = json.loads(res.stdout)
    return float(data["format"]["duration"])


def download_url(url: str, workdir: Path) -> tuple[Path, str]:
    """Download a video from a URL using yt-dlp. Returns (path, title)."""
    out_tpl = str(workdir / "source.%(ext)s")
    proc = _run_yt_dlp(
        [
            "-f",
            "bv*+ba/b",
            "--merge-output-format",
            "mp4",
            "-o",
            out_tpl,
            "--print-json",
            "--quiet",
            "--no-warnings",
            url,
        ]
    )
    candidates = sorted(workdir.glob("source.*"))
    if not candidates:
        raise YtDlpError("yt-dlp finished but produced no file")
    video = candidates[0]
    # `--print-json` printed metadata to stdout; parse the last JSON object
    # (there's usually exactly one, but we defend against warnings above it).
    title = video.stem
    for line in reversed(proc.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                title = json.loads(line).get("title") or title
                break
            except json.JSONDecodeError:
                continue
    return video, title


def save_upload(src: Path, workdir: Path, original_name: str) -> Path:
    """Copy an uploaded file into the workdir preserving its extension."""
    suffix = Path(original_name).suffix or ".mp4"
    dst = workdir / f"source{suffix}"
    shutil.copyfile(src, dst)
    return dst


def extract_audio(video: Path, workdir: Path) -> Path:
    """Extract mono 16kHz PCM WAV for transcription and RMS analysis."""
    out = workdir / "audio.wav"
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-acodec",
            "pcm_s16le",
            str(out),
        ]
    )
    return out


def ingest(*, url: str | None, upload: Path | None, upload_name: str | None, workdir: Path) -> SourceMedia:
    if url:
        video, title = download_url(url, workdir)
    elif upload is not None and upload_name is not None:
        video = save_upload(upload, workdir, upload_name)
        title = Path(upload_name).stem
    else:
        raise ValueError("Either url or upload must be provided")
    audio = extract_audio(video, workdir)
    duration = probe_duration(video)
    return SourceMedia(video_path=video, audio_path=audio, duration=duration, title=title)
