"""Runtime configuration for ClipGenius backend."""
from __future__ import annotations

import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("CLIPGENIUS_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
JOBS_DIR = DATA_DIR / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)

# faster-whisper model size: tiny | base | small | medium | large-v3
WHISPER_MODEL = os.environ.get("CLIPGENIUS_WHISPER_MODEL", "base")
# CPU-friendly compute type
WHISPER_COMPUTE_TYPE = os.environ.get("CLIPGENIUS_WHISPER_COMPUTE", "int8")
WHISPER_DEVICE = os.environ.get("CLIPGENIUS_WHISPER_DEVICE", "cpu")

# Number of highlight clips to produce
DEFAULT_NUM_CLIPS = int(os.environ.get("CLIPGENIUS_NUM_CLIPS", "10"))
# Target clip duration bounds (seconds)
MIN_CLIP_SEC = float(os.environ.get("CLIPGENIUS_MIN_CLIP", "20"))
MAX_CLIP_SEC = float(os.environ.get("CLIPGENIUS_MAX_CLIP", "55"))
TARGET_CLIP_SEC = float(os.environ.get("CLIPGENIUS_TARGET_CLIP", "35"))

# Watermark text shown on every free clip
WATERMARK_TEXT = os.environ.get("CLIPGENIUS_WATERMARK", "Clip Genius")

# CORS origins for local dev
CORS_ORIGINS = os.environ.get(
    "CLIPGENIUS_CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")
