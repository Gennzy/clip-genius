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

# yt-dlp authentication for sites that gate downloads behind a login
# (e.g. YouTube's "Sign in to confirm you're not a bot" challenge).
# Point this at a Netscape-format cookies.txt exported from a logged-in browser.
YT_DLP_COOKIES_FILE = os.environ.get("CLIPGENIUS_YT_DLP_COOKIES_FILE") or None
# Alternative: pull cookies directly from an installed browser profile.
# Format: "<browser>" or "<browser>:<profile_dir>" (e.g. "chrome", "firefox:default",
# "chrome:/home/me/.config/google-chrome").
YT_DLP_COOKIES_FROM_BROWSER = os.environ.get("CLIPGENIUS_YT_DLP_COOKIES_FROM_BROWSER") or None
# Extra extractor-args (passed verbatim to yt-dlp `--extractor-args`).
# Default rotates through a handful of YouTube player clients, which survives
# most region / bot checks even without cookies.
YT_DLP_EXTRACTOR_ARGS = os.environ.get(
    "CLIPGENIUS_YT_DLP_EXTRACTOR_ARGS",
    "youtube:player_client=default,tv_simply,web_safari;formats=missing_pot",
)
