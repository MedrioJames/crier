"""WSOLA (Waveform Similarity Overlap-Add) time-scale modification.

Changes playback duration without changing pitch, by re-arranging small
overlapping windows of the original waveform rather than resampling it
(resampling is what makes sped-up speech sound like a chipmunk and
slowed-down speech sound deep - it shifts pitch along with duration).

`WsolaStretcher` is incremental/stateful so it can run as a background
worker consuming audio as Kokoro produces it and re-target the speed at
any point, rather than needing the whole clip up front.
"""

import numpy as np

_EPS = 1e-9


class WsolaStretcher:
    def __init__(self, sample_rate: int, frame_ms: float = 40.0, overlap_ratio: float = 0.5,
                 search_ms: float = 8.0):
        self.frame_len = max(64, int(sample_rate * frame_ms / 1000))
        self.syn_hop = max(1, int(self.frame_len * (1 - overlap_ratio)))
        self.search_range = max(1, int(sample_rate * search_ms / 1000))
        self.window = np.hanning(self.frame_len).astype(np.float32)

        self._acc = np.zeros(0, dtype=np.float32)       # overlap-add accumulator
        self._acc_norm = np.zeros(0, dtype=np.float32)  # matching sum-of-window-weights
        self._acc_base = 0        # output-sample index that _acc[0] corresponds to
        self._syn_pos = 0         # next synthesis-write position (output-sample index)
        self._ana_pos = 0.0       # next (ideal) analysis read position (input-sample index)
        self._prev_seg = None     # last extracted, windowed frame - correlation reference

    def step(self, base: np.ndarray, speed: float):
        """Try to consume one more analysis frame from `base` at the given
        `speed` (>0; 2.0 = twice as fast). Returns finalized output samples
        (a possibly-empty array), or None if `base` doesn't have enough
        audio buffered yet for the next frame - caller should wait for more
        and retry."""
        speed = max(0.1, float(speed))
        # At speed>1, a fixed syn_hop makes ana_hop (= syn_hop*speed) exceed
        # frame_len - the gap between consecutive analysis frames then
        # skips a chunk of source audio outright (dropped phonemes, not
        # just distorted prosody). Shrinking the hop keeps every sample
        # covered by at least one frame regardless of speed; the OLA
        # accumulator already normalizes by actual window-sum, so a
        # variable hop reconstructs correctly.
        syn_hop = min(self.syn_hop, max(1, int(self.frame_len / speed))) if speed > 1.0 else self.syn_hop
        ana_hop = syn_hop * speed

        ideal = int(round(self._ana_pos))
        if ideal + self.frame_len + self.search_range > len(base):
            return None

        lo = max(0, ideal - self.search_range)
        hi = min(len(base) - self.frame_len, ideal + self.search_range)
        if hi < lo:
            hi = lo

        if self._prev_seg is None:
            best = ideal
        else:
            overlap_len = self.frame_len - syn_hop
            ref = self._prev_seg[-overlap_len:]
            n_cand = hi - lo + 1
            cand_source = base[lo: lo + n_cand + overlap_len - 1]
            cands = np.lib.stride_tricks.sliding_window_view(cand_source, overlap_len)
            dot = cands @ ref
            cand_norm = np.sqrt(np.einsum("ij,ij->i", cands, cands)) + _EPS
            ref_norm = np.sqrt(np.dot(ref, ref)) + _EPS
            scores = dot / (cand_norm * ref_norm)
            best = lo + int(np.argmax(scores))

        self.last_frame_start = best   # exposed for coverage testing/debugging
        frame = base[best: best + self.frame_len] * self.window
        self._prev_seg = frame

        rel = self._syn_pos - self._acc_base
        needed_len = rel + self.frame_len
        if needed_len > len(self._acc):
            grow = needed_len - len(self._acc)
            self._acc = np.concatenate([self._acc, np.zeros(grow, dtype=np.float32)])
            self._acc_norm = np.concatenate([self._acc_norm, np.zeros(grow, dtype=np.float32)])
        self._acc[rel:rel + self.frame_len] += frame
        self._acc_norm[rel:rel + self.frame_len] += self.window

        self._ana_pos += ana_hop
        self._syn_pos += syn_hop

        # Anything more than one frame behind the latest write can never be
        # touched by a future frame again - finalize (normalize) and emit it.
        finalize_until = max(0, (self._syn_pos - self._acc_base) - self.frame_len)
        if finalize_until <= 0:
            return np.zeros(0, dtype=np.float32)

        norm = self._acc_norm[:finalize_until].copy()
        norm[norm < 1e-6] = 1.0
        out = (self._acc[:finalize_until] / norm).astype(np.float32)
        self._acc = self._acc[finalize_until:]
        self._acc_norm = self._acc_norm[finalize_until:]
        self._acc_base += finalize_until
        return out

    def flush(self) -> np.ndarray:
        """Call once no more input audio is coming, to emit whatever is
        still sitting in the overlap-add accumulator."""
        norm = self._acc_norm.copy()
        norm[norm < 1e-6] = 1.0
        out = (self._acc / norm).astype(np.float32)
        self._acc = np.zeros(0, dtype=np.float32)
        self._acc_norm = np.zeros(0, dtype=np.float32)
        return out


def time_stretch(x: np.ndarray, speed: float, sample_rate: int) -> np.ndarray:
    """One-shot convenience wrapper over WsolaStretcher for a complete,
    already-fully-available signal."""
    x = np.asarray(x, dtype=np.float32).reshape(-1)
    if len(x) == 0:
        return x.copy()
    stretcher = WsolaStretcher(sample_rate)
    pieces = []
    while True:
        out = stretcher.step(x, speed)
        if out is None:
            break
        if len(out):
            pieces.append(out)
    pieces.append(stretcher.flush())
    return np.concatenate(pieces) if pieces else np.zeros(0, dtype=np.float32)
