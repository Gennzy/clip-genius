"""In-memory job registry with lightweight progress tracking."""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .config import JOBS_DIR
from .models import ClipInfo, JobStatus


@dataclass
class Job:
    id: str
    workdir: Path
    status: JobStatus = "queued"
    progress: float = 0.0
    message: str = ""
    error: str | None = None
    clips: list[ClipInfo] = field(default_factory=list)
    source_title: str | None = None
    source_duration: float | None = None


_REGISTRY: dict[str, Job] = {}
_LOCK = threading.Lock()


def create_job() -> Job:
    job_id = uuid.uuid4().hex[:12]
    workdir = JOBS_DIR / job_id
    workdir.mkdir(parents=True, exist_ok=True)
    job = Job(id=job_id, workdir=workdir)
    with _LOCK:
        _REGISTRY[job_id] = job
    return job


def get_job(job_id: str) -> Job | None:
    with _LOCK:
        return _REGISTRY.get(job_id)


def update(job: Job, **fields) -> None:
    with _LOCK:
        for k, v in fields.items():
            setattr(job, k, v)
