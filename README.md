# Clip Genius

AI highlight clipper for streams, podcasts, and webinars. Paste a URL (YouTube,
Twitch VOD, direct MP4, …) or upload a file — Clip Genius transcribes it,
scores engaging moments with a speech-aware heuristic, and renders up to 20
vertical 9:16 clips with burned-in subtitles and a watermark.

> **MVP status.** This repo is a working end-to-end prototype. It runs fully
> locally using `faster-whisper` for transcription and a heuristic
> highlight-scorer — no OpenAI key required.

## What it does

```
URL / upload  →  yt-dlp       →  ffmpeg (mono 16kHz WAV)
                                       │
                                       ▼
                                faster-whisper (word-level timestamps)
                                       │
                                       ▼
                highlight scorer (RMS energy + speech density + hook words)
                                       │
                                       ▼
                     ffmpeg (9:16 crop + ASS subtitles + watermark)
                                       │
                                       ▼
                                10 vertical MP4 clips
```

Highlight signals:

- **Audio energy (RMS)** — louder segments are usually more engaging.
- **Speech density** — words per second spikes around punchlines.
- **Hook words** — discourse markers like *«короче», «смотри», «представь»,
  «listen», «imagine», «seriously»*, plus laugh and intensifier tokens.
- **Questions / exclamations** — punctuation from the transcript.

Clips are de-overlapped with non-maximum suppression and snapped to nearby
sentence boundaries so they never start or end mid-word.

## Repo layout

```
clip-genius/
├── backend/             FastAPI backend (ingest → transcribe → clip)
│   ├── app/
│   │   ├── main.py          FastAPI routes (POST /jobs, GET /jobs/{id})
│   │   ├── pipeline.py      Orchestration
│   │   ├── ingest.py        yt-dlp + ffmpeg audio extraction
│   │   ├── transcribe.py    faster-whisper wrapper
│   │   ├── highlights.py    Heuristic scorer + NMS selector
│   │   ├── clipper.py       ffmpeg render + ASS subtitles + watermark
│   │   ├── jobs.py          In-memory job registry
│   │   └── ...
│   └── pyproject.toml
└── frontend/            Vite + React single-page UI
    └── src/
        ├── App.tsx          URL/upload form, progress, clip gallery
        └── api.ts
```

## System prerequisites

- **Python ≥ 3.10**
- **Node ≥ 18**
- **ffmpeg** and **ffprobe** on `PATH`
- A Cyrillic-capable font (e.g. `fonts-dejavu-core`) if you plan to process
  Russian-language streams — the ASS style uses `DejaVu Sans`.

On Ubuntu:

```bash
sudo apt-get install -y ffmpeg fonts-dejavu-core
```

## Running the backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 8000
```

The first request downloads the `faster-whisper base` model (~140 MB) into
`~/.cache/huggingface`. Override the model via environment variables:

| Variable                        | Default            | Notes                                   |
| ------------------------------- | ------------------ | --------------------------------------- |
| `CLIPGENIUS_WHISPER_MODEL`      | `base`             | `tiny`, `base`, `small`, `medium`, `large-v3` |
| `CLIPGENIUS_WHISPER_DEVICE`     | `cpu`              | `cuda` if you have a GPU                |
| `CLIPGENIUS_WHISPER_COMPUTE`    | `int8`             | `float16` on GPU                        |
| `CLIPGENIUS_NUM_CLIPS`          | `10`               | Default number of clips                 |
| `CLIPGENIUS_MIN_CLIP` / `_MAX_CLIP` / `_TARGET_CLIP` | `20` / `55` / `35` | Clip duration bounds (seconds) |
| `CLIPGENIUS_WATERMARK`          | `Clip Genius`      | Watermark text                          |
| `CLIPGENIUS_CORS_ORIGINS`       | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated |

## Running the frontend

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The Vite dev server proxies `/jobs` and
`/health` to the FastAPI backend on port 8000.

## API

| Method | Path                              | Description                         |
| ------ | --------------------------------- | ----------------------------------- |
| `POST` | `/jobs`                           | Create a job (`url` OR `file` form field) |
| `GET`  | `/jobs/{job_id}`                  | Poll job status + clip list         |
| `GET`  | `/jobs/{job_id}/files/{path}`     | Download a generated clip           |
| `GET`  | `/health`                         | Liveness probe                      |

Example:

```bash
curl -F 'url=https://www.youtube.com/watch?v=dQw4w9WgXcQ' \
     -F 'num_clips=5' \
     http://localhost:8000/jobs
# → {"job_id":"a1b2c3d4e5f6"}

curl http://localhost:8000/jobs/a1b2c3d4e5f6
```

## Roadmap (paid tier hooks)

The watermark, HD toggle, custom subtitle templates, and auto-posting are all
currently single code paths — the obvious next steps are:

- Replace the watermark style block in `app/clipper.py` with a user-selected
  template.
- Gate the `libx264 -crf 22` preset behind a "HD" flag and downgrade free
  renders to 720p.
- Add an `/autopost` endpoint that pushes finished clips to TikTok / Reels
  via their APIs.
- Swap the heuristic scorer for an LLM-based moment picker (feed the
  transcript, ask for JSON `[{start, end, reason}]`) when an `OPENAI_API_KEY`
  is present.

## License

MIT.
