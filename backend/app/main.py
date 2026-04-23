"""FastAPI entrypoint for the ClipGenius backend."""
from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import CORS_ORIGINS, DEFAULT_NUM_CLIPS
from .jobs import create_job, get_job
from .models import JobCreateResponse, JobStatusResponse
from .pipeline import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(title="ClipGenius API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/jobs", response_model=JobCreateResponse)
async def create_job_endpoint(
    background_tasks: BackgroundTasks,
    url: str | None = Form(default=None),
    num_clips: int = Form(default=DEFAULT_NUM_CLIPS),
    file: UploadFile | None = File(default=None),
) -> JobCreateResponse:
    if not url and file is None:
        raise HTTPException(status_code=400, detail="Provide either `url` or `file`")
    if url and file is not None:
        raise HTTPException(status_code=400, detail="Provide only one of `url` or `file`")

    job = create_job()

    upload_path: Path | None = None
    upload_name: str | None = None
    if file is not None:
        upload_name = file.filename or "upload.mp4"
        tmp = tempfile.NamedTemporaryFile(delete=False, dir=str(job.workdir), suffix=Path(upload_name).suffix)
        try:
            shutil.copyfileobj(file.file, tmp)
        finally:
            tmp.close()
        upload_path = Path(tmp.name)

    background_tasks.add_task(
        run_pipeline,
        job,
        url=url,
        upload_path=upload_path,
        upload_name=upload_name,
        num_clips=max(1, min(20, int(num_clips))),
    )
    return JobCreateResponse(job_id=job.id)


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def job_status(job_id: str) -> JobStatusResponse:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        message=job.message,
        error=job.error,
        clips=job.clips,
        source_title=job.source_title,
        source_duration=job.source_duration,
    )


@app.get("/jobs/{job_id}/files/{path:path}")
def job_file(job_id: str, path: str) -> FileResponse:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    target = (job.workdir / path).resolve()
    try:
        target.relative_to(job.workdir.resolve())
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Invalid path") from err
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(target))
