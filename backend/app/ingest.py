"""Fetch source video (local upload or URL) and extract a mono 16kHz WAV."""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SourceMedia:
    video_path: Path
    audio_path: Path
    duration: float
    title: str


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


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
    # Prefer mp4/m4a if available; otherwise let yt-dlp pick the best.
    _run(
        [
            "yt-dlp",
            "-f",
            "bv*+ba/b",
            "--merge-output-format",
            "mp4",
            "--no-playlist",
            "--restrict-filenames",
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
        raise RuntimeError("yt-dlp finished but produced no file")
    video = candidates[0]
    # Grab metadata via a separate --print-json pass (it was printed above but we re-probe for simplicity).
    try:
        meta_res = _run(["yt-dlp", "-J", "--no-playlist", url])
        meta = json.loads(meta_res.stdout)
        title = meta.get("title") or video.stem
    except Exception:
        title = video.stem
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
