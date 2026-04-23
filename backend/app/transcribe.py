"""Word-level transcription using faster-whisper.

The model is loaded lazily on first call and cached for the process lifetime.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from .config import WHISPER_COMPUTE_TYPE, WHISPER_DEVICE, WHISPER_MODEL


@dataclass
class Word:
    start: float
    end: float
    text: str


@dataclass
class Segment:
    start: float
    end: float
    text: str
    words: list[Word]


@dataclass
class Transcript:
    language: str
    duration: float
    segments: list[Segment]

    @property
    def words(self) -> list[Word]:
        out: list[Word] = []
        for s in self.segments:
            out.extend(s.words)
        return out


_MODEL = None
_MODEL_LOCK = Lock()


def _get_model():
    global _MODEL
    if _MODEL is None:
        with _MODEL_LOCK:
            if _MODEL is None:
                from faster_whisper import WhisperModel  # heavy import

                _MODEL = WhisperModel(
                    WHISPER_MODEL,
                    device=WHISPER_DEVICE,
                    compute_type=WHISPER_COMPUTE_TYPE,
                )
    return _MODEL


def transcribe(audio_path: Path, *, language: str | None = None) -> Transcript:
    """Run faster-whisper with word-level timestamps."""
    model = _get_model()
    segments_iter, info = model.transcribe(
        str(audio_path),
        language=language,
        vad_filter=True,
        word_timestamps=True,
        beam_size=1,
    )
    segments: list[Segment] = []
    for seg in segments_iter:
        words = [
            Word(start=float(w.start or seg.start), end=float(w.end or seg.end), text=w.word.strip())
            for w in (seg.words or [])
            if w.word and w.word.strip()
        ]
        segments.append(
            Segment(
                start=float(seg.start),
                end=float(seg.end),
                text=seg.text.strip(),
                words=words,
            )
        )
    return Transcript(
        language=info.language,
        duration=float(info.duration),
        segments=segments,
    )
