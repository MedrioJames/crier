"""Text chunking and audio-splice helpers shared by every voice provider -
none of this is specific to any one TTS backend."""

import re

import numpy as np

_LINE_GAP_SECONDS = 0.9        # pause between lines/paragraphs (e.g. a title -> body)
_GROUP_GAP_SECONDS = 0.12      # small gap only where a long paragraph had to be split for streaming
_FADE_SECONDS = 0.02           # short edge fade on every chunk so splices don't click
_MAX_CHUNK_CHARS = 220         # group consecutive sentences up to roughly this size per chunk

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def split_into_chunks(text: str):
    """Break text into speakable chunks paired with the silence to insert
    after each one.

    Consecutive sentences within the same line are grouped together (up to
    ~_MAX_CHUNK_CHARS) rather than split one-per-chunk: handing a provider
    several sentences at once lets it carry natural connected prosody
    across them, whereas synthesizing every sentence in total isolation
    made each one sound like the start of a new paragraph - losing the
    actual distinction between "mid-paragraph" and "new paragraph". A
    run-on paragraph with no line breaks still gets cut into a few chunks
    (for a reasonably fast time-to-first-audio), just with a much smaller,
    near-inaudible gap between those pieces than the real pause used
    between lines/paragraphs.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    chunks = []
    for li, line in enumerate(lines):
        sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(line) if s.strip()] or [line]

        groups = []
        current, current_len = [], 0
        for sentence in sentences:
            if current and current_len + len(sentence) > _MAX_CHUNK_CHARS:
                groups.append(" ".join(current))
                current, current_len = [], 0
            current.append(sentence)
            current_len += len(sentence) + 1
        if current:
            groups.append(" ".join(current))

        last_line = li == len(lines) - 1
        for gi, group in enumerate(groups):
            last_group_in_line = gi == len(groups) - 1
            if last_group_in_line and last_line:
                pause = 0.0
            elif last_group_in_line:
                pause = _LINE_GAP_SECONDS
            else:
                pause = _GROUP_GAP_SECONDS
            chunks.append((group, pause))
    return chunks


def fade_edges(samples: np.ndarray, sr: int) -> np.ndarray:
    """A short linear ramp in/out at the very start/end of a chunk. Splicing
    raw neural-TTS output directly against silence (or another chunk) tends
    to click, since the waveform rarely crosses zero exactly at the cut."""
    n = int(_FADE_SECONDS * sr)
    if n <= 0 or len(samples) < 2 * n:
        return samples
    samples = samples.copy()
    ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
    samples[:n] *= ramp
    samples[-n:] *= ramp[::-1]
    return samples


def with_trailing_pause(samples: np.ndarray, sr: int, pause_after: float) -> np.ndarray:
    """Append pause_after seconds of silence, if any."""
    if pause_after <= 0:
        return samples
    gap = np.zeros(int(pause_after * sr), dtype=np.float32)
    return np.concatenate([samples, gap])
