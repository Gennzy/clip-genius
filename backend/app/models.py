"""Pydantic schemas exposed by the ClipGenius API."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

JobStatus = Literal["queued", "downloading", "extracting_audio", "transcribing", "analyzing", "rendering", "done", "failed"]


class JobCreateResponse(BaseModel):
    job_id: str


class ClipInfo(BaseModel):
    index: int
    start: float
    end: float
    duration: float
    title: str
    score: float
    transcript: str
    url: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: float = Field(0.0, ge=0.0, le=1.0)
    message: str = ""
    error: str | None = None
    clips: list[ClipInfo] = Field(default_factory=list)
    source_title: str | None = None
    source_duration: float | None = None
