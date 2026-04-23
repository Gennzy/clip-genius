"""Orchestrates the ingest → transcribe → highlight → render pipeline."""
from __future__ import annotations

import logging
import traceback
from pathlib import Path

from .clipper import render_clip
from .config import (
    DEFAULT_NUM_CLIPS,
    MAX_CLIP_SEC,
    MIN_CLIP_SEC,
    TARGET_CLIP_SEC,
    WATERMARK_TEXT,
)
from .highlights import select_highlights
from .ingest import ingest
from .jobs import Job, update
from .models import ClipInfo
from .transcribe import transcribe

log = logging.getLogger("clipgenius.pipeline")


def run_pipeline(
    job: Job,
    *,
    url: str | None = None,
    upload_path: Path | None = None,
    upload_name: str | None = None,
    num_clips: int = DEFAULT_NUM_CLIPS,
) -> None:
    """Execute the full pipeline for ``job`` and update its progress as we go."""
    try:
        update(job, status="downloading", progress=0.05, message="Fetching source…")
        source = ingest(url=url, upload=upload_path, upload_name=upload_name, workdir=job.workdir)
        update(
            job,
            status="extracting_audio",
            progress=0.20,
            message="Audio ready, preparing for transcription",
            source_title=source.title,
            source_duration=source.duration,
        )

        update(job, status="transcribing", progress=0.25, message="Transcribing audio (this can take a while)…")
        transcript = transcribe(source.audio_path)
        update(job, progress=0.60, message=f"Transcript done ({len(transcript.segments)} segments, lang={transcript.language})")

        update(job, status="analyzing", progress=0.65, message="Scoring highlights…")
        highlights = select_highlights(
            transcript,
            source.audio_path,
            n=num_clips,
            min_sec=MIN_CLIP_SEC,
            max_sec=MAX_CLIP_SEC,
            target_sec=TARGET_CLIP_SEC,
        )
        if not highlights:
            raise RuntimeError("No highlights could be extracted (audio may be silent or too short)")
        update(
            job,
            status="rendering",
            progress=0.70,
            message=f"Rendering {len(highlights)} clips…",
        )

        clips: list[ClipInfo] = []
        total = len(highlights)
        for i, hl in enumerate(highlights):
            rendered = render_clip(
                source_video=source.video_path,
                highlight=hl,
                workdir=job.workdir,
                index=i + 1,
                watermark=WATERMARK_TEXT,
            )
            rel = rendered.path.relative_to(job.workdir).as_posix()
            clips.append(
                ClipInfo(
                    index=i + 1,
                    start=round(hl.start, 2),
                    end=round(hl.end, 2),
                    duration=round(hl.end - hl.start, 2),
                    title=hl.title,
                    score=round(hl.score, 4),
                    transcript=hl.transcript,
                    url=f"/jobs/{job.id}/files/{rel}",
                )
            )
            update(
                job,
                progress=0.70 + 0.28 * ((i + 1) / total),
                message=f"Rendered clip {i + 1}/{total}",
                clips=list(clips),
            )

        update(
            job,
            status="done",
            progress=1.0,
            message=f"Done — {len(clips)} clips ready",
            clips=clips,
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("Pipeline failed for job %s", job.id)
        update(
            job,
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
            message="Pipeline failed",
        )
        # Persist traceback on disk for debugging.
        (job.workdir / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
