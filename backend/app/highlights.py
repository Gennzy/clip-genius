"""Heuristic highlight detection.

We score fixed-length sliding windows over the transcript using a blend of
signals and then run non-maximum suppression to pick the top ``n`` clips.

Signals:

* RMS audio energy within the window (louder = more engaging).
* Speech density (words per second, proxy for excitement).
* Discourse / hook markers in the spoken text ("listen", "imagine",
  "jokingly", laughter tokens, etc.) — both Russian and English.
* Question / exclamation punctuation in the underlying segment text.

The highlight selector also snaps window edges to sentence boundaries so we
don't start or end mid-word, and it respects a configurable minimum gap
between clips.
"""
from __future__ import annotations

import re
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .transcribe import Transcript, Word

# Discourse markers / hooks that usually precede a punchline or insight.
HOOK_WORDS: tuple[str, ...] = (
    # Russian
    "короче", "смотри", "слушай", "представь", "кстати", "внимание",
    "секрет", "прикинь", "жесть", "офигеть", "офигенно", "вау", "ого",
    "реально", "вообще", "серьёзно", "серьезно", "факт", "фишка", "прикол",
    # English
    "listen", "look", "imagine", "honestly", "seriously", "actually",
    "literally", "crazy", "insane", "secret", "trick", "hack", "wait",
    "nobody", "everyone", "remember",
)

# Laugh / emotional tokens that Whisper sometimes writes out.
LAUGH_PATTERNS: tuple[str, ...] = (
    "хаха", "хах", "ахах", "лол", "кек",
    "haha", "lol", "lmao", "rofl",
)

# Profanity / intensifier roots (soft signal — clip-worthy candid moments).
INTENSIFIER_PATTERNS: tuple[str, ...] = (
    "блин", "чёрт", "черт", "damn", "wow",
)

WORD_CHARS_RE = re.compile(r"[\w']+", re.UNICODE)


@dataclass
class Highlight:
    start: float
    end: float
    score: float
    title: str
    transcript: str
    words: list[Word]


def _load_wav_mono(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wf:
        if wf.getnchannels() != 1:
            raise ValueError("Expected mono WAV")
        if wf.getsampwidth() != 2:
            raise ValueError("Expected 16-bit WAV")
        sr = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return samples, sr


def _rms_envelope(samples: np.ndarray, sr: int, hop_sec: float = 0.5) -> tuple[np.ndarray, float]:
    """Return an RMS energy value per ``hop_sec`` window."""
    hop = max(1, int(sr * hop_sec))
    # Pad so len is divisible by hop.
    pad = (-len(samples)) % hop
    if pad:
        samples = np.concatenate([samples, np.zeros(pad, dtype=np.float32)])
    frames = samples.reshape(-1, hop)
    rms = np.sqrt((frames**2).mean(axis=1) + 1e-9)
    return rms, hop_sec


def _window_rms(env: np.ndarray, hop_sec: float, start: float, end: float) -> float:
    i0 = max(0, int(start / hop_sec))
    i1 = min(len(env), int(end / hop_sec))
    if i1 <= i0:
        return 0.0
    return float(env[i0:i1].mean())


def _hook_score(text: str) -> float:
    lower = text.lower()
    tokens = WORD_CHARS_RE.findall(lower)
    if not tokens:
        return 0.0
    tokenset = set(tokens)
    hooks = sum(1 for t in tokenset if t in HOOK_WORDS)
    laughs = sum(1 for t in tokens if any(p in t for p in LAUGH_PATTERNS))
    intens = sum(1 for t in tokens if any(p in t for p in INTENSIFIER_PATTERNS))
    questions = lower.count("?")
    excls = lower.count("!")
    # Weighted sum, then squashed so a few strong hits dominate but not linearly.
    raw = 1.2 * hooks + 1.8 * laughs + 0.6 * intens + 0.8 * questions + 0.6 * excls
    return float(np.tanh(raw / 3.0))


def _speech_density(words: list[Word], start: float, end: float) -> float:
    dur = max(0.001, end - start)
    count = sum(1 for w in words if w.start >= start and w.end <= end)
    # Typical conversational rate is ~2.5 words/sec; cap at 4 for scoring.
    return float(min(count / dur, 4.0) / 4.0)


def _window_text(words: list[Word], start: float, end: float) -> tuple[str, list[Word]]:
    picked = [w for w in words if w.start >= start and w.end <= end]
    return " ".join(w.text for w in picked), picked


def _snap_to_sentence(transcript: Transcript, start: float, end: float,
                     min_sec: float, max_sec: float) -> tuple[float, float]:
    """Extend/shrink the window to nearby sentence boundaries."""
    segs = transcript.segments
    if not segs:
        return start, end
    # Find segment containing start
    s_idx = 0
    for i, s in enumerate(segs):
        if s.start <= start <= s.end:
            s_idx = i
            break
        if s.start > start:
            s_idx = max(0, i - 1)
            break
    e_idx = s_idx
    for i in range(s_idx, len(segs)):
        if segs[i].end >= end:
            e_idx = i
            break
    new_start = max(0.0, segs[s_idx].start)
    new_end = segs[e_idx].end
    # Extend forward to reach min duration
    while (new_end - new_start) < min_sec and e_idx + 1 < len(segs):
        e_idx += 1
        new_end = segs[e_idx].end
    # Shrink back if beyond max
    while (new_end - new_start) > max_sec and e_idx > s_idx:
        e_idx -= 1
        new_end = segs[e_idx].end
    return new_start, new_end


def _make_title(text: str, max_len: int = 60) -> str:
    text = text.strip().replace("\n", " ")
    if not text:
        return "Highlight"
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    # Try to break on a space
    sp = cut.rfind(" ")
    if sp > max_len * 0.5:
        cut = cut[:sp]
    return cut.rstrip(",.;:—- ") + "…"


def select_highlights(
    transcript: Transcript,
    audio_path: Path,
    *,
    n: int,
    min_sec: float,
    max_sec: float,
    target_sec: float,
    min_gap: float = 8.0,
) -> list[Highlight]:
    """Score candidate windows and return the top ``n`` non-overlapping highlights."""
    samples, sr = _load_wav_mono(audio_path)
    env, hop = _rms_envelope(samples, sr)
    total_dur = max(transcript.duration, len(samples) / sr)
    words = transcript.words
    if not words:
        return []

    # Global RMS normaliser.
    rms_mean = float(env.mean()) + 1e-6
    rms_std = float(env.std()) + 1e-6

    # Sliding window over the transcript timeline.
    step = max(2.0, target_sec / 4.0)
    candidates: list[Highlight] = []
    t = 0.0
    while t + min_sec <= total_dur:
        start = t
        end = min(total_dur, t + target_sec)
        if end - start < min_sec:
            break
        text, picked = _window_text(words, start, end)
        if not picked:
            t += step
            continue

        rms_val = _window_rms(env, hop, start, end)
        rms_score = float(np.tanh((rms_val - rms_mean) / rms_std))
        # Keep in [0, 1]
        rms_score = (rms_score + 1.0) / 2.0

        dens_score = _speech_density(words, start, end)
        hook_score = _hook_score(text)

        score = 0.35 * rms_score + 0.25 * dens_score + 0.40 * hook_score
        candidates.append(
            Highlight(
                start=start,
                end=end,
                score=score,
                title=_make_title(text),
                transcript=text,
                words=picked,
            )
        )
        t += step

    if not candidates:
        return []

    # Non-maximum suppression: keep top-scoring candidates that don't overlap
    # within ``min_gap`` seconds of an already chosen clip.
    candidates.sort(key=lambda h: h.score, reverse=True)
    selected: list[Highlight] = []
    for cand in candidates:
        if len(selected) >= n:
            break
        conflict = False
        for sel in selected:
            if not (cand.end + min_gap <= sel.start or cand.start >= sel.end + min_gap):
                conflict = True
                break
        if conflict:
            continue
        # Snap to sentence boundaries, then recompute text.
        s, e = _snap_to_sentence(transcript, cand.start, cand.end, min_sec, max_sec)
        text, picked = _window_text(words, s, e)
        if not picked:
            continue
        selected.append(
            Highlight(
                start=s,
                end=e,
                score=cand.score,
                title=_make_title(text),
                transcript=text,
                words=picked,
            )
        )
    # Return in chronological order for nicer UX.
    selected.sort(key=lambda h: h.start)
    return selected
