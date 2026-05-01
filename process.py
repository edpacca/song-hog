import logging
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from benchmark import measure

logger = logging.getLogger("song_hog.process")


@dataclass
class AnalysisParams:
    window: int = 400
    threshold: float = 35
    min_duration: float = 40
    min_gap: float = 20
    padding: float = 5
    def __repr__(self) -> str:
        return f"w={self.window}__th={self.threshold}__md={self.min_duration}__mg={self.min_gap}__p={self.padding}"

    def __str__(self) -> str:
        return f"window={self.window} threshold={self.threshold}db min_duration={self.min_duration}s min_gap={self.min_gap}s padding={self.padding}s"


@dataclass
class AudioAnalysis:
    spectrum: Optional[np.ndarray]  # linear power, shape (freqs, time_bins), or None when plotting disabled
    freqs: np.ndarray
    t: np.ndarray
    intensity_db: np.ndarray  # avg, log-transformed, clamped
    smoothed: np.ndarray
    segments: List[Tuple[float, float]]
    sample_rate: int
    params: AnalysisParams


def params_from_env() -> AnalysisParams:
    defaults = AnalysisParams()
    return AnalysisParams(
        window=int(os.getenv("ANALYSIS_WINDOW", defaults.window)),
        threshold=float(os.getenv("ANALYSIS_THRESHOLD", defaults.threshold)),
        min_duration=float(os.getenv("ANALYSIS_MIN_DURATION", defaults.min_duration)),
        min_gap=float(os.getenv("ANALYSIS_MIN_GAP", defaults.min_gap)),
        padding=float(os.getenv("ANALYSIS_PADDING", defaults.padding)),
    )


@measure
def compute_mean_intensity(
    data: np.ndarray,
    sample_rate: int,
    NFFT: int = 1024,
    noverlap: int = 512,
    include_spectrum: bool = False,
) -> Tuple[np.ndarray, Optional[np.ndarray], np.ndarray, np.ndarray]:
    """Streaming Short Time Fourier Transform (STFT): computes mean power per time bin without loading the full 2D spectrum into memory.

    Matches mlab_specgram normalization: Hanning window, PSD scaling
    (Fs * sum(w²)), one-sided doubling for non-DC/Nyquist bins.
    """
    hop = NFFT - noverlap
    hann = np.hanning(NFFT)
    norm = sample_rate * float(np.dot(hann, hann))

    n_windows = (len(data) - noverlap) // hop
    freqs = np.fft.rfftfreq(NFFT, 1.0 / sample_rate)
    t = (np.arange(n_windows) * hop + NFFT // 2) / sample_rate

    spectrum = np.empty((len(freqs), n_windows)) if include_spectrum else None
    avg_intensity = np.empty(n_windows)

    for i in range(n_windows):
        start = i * hop
        power = np.abs(np.fft.rfft(data[start:start + NFFT] * hann, n=NFFT)) ** 2 / norm
        power[1:-1] *= 2
        if include_spectrum:
            spectrum[:, i] = power
        avg_intensity[i] = power.mean()

    return avg_intensity, spectrum, freqs, t


@measure
def analyse(
    data: np.ndarray,
    sample_rate: int,
    params: AnalysisParams,
    include_spectrum: bool = False,
) -> AudioAnalysis:
    logger.info(f"Analysing  window={params.window}  threshold={params.threshold}dB  min_duration={params.min_duration}s  min_gap={params.min_gap}s  padding={params.padding}s")
    avg_intensity, spectrum, freqs, t = compute_mean_intensity(
        data, sample_rate, include_spectrum=include_spectrum
    )

    avg_intensity[avg_intensity == 0] = 1e-10
    avg_intensity_db = 10 * np.log10(avg_intensity)
    avg_intensity_db[avg_intensity_db < 0] = 0

    smoothed = smooth_signal(avg_intensity_db, params.window)
    segments = detect_segments(smoothed, t, params.threshold, params.min_duration, params.min_gap, params.padding)

    logger.info(f"Analysis complete — {len(segments)} segment(s) found")
    for i, (start, end) in enumerate(segments):
        logger.info(f"Segment {i:02d}: {start}s -> {end}s")
    return AudioAnalysis(
        spectrum=spectrum,
        freqs=freqs,
        t=t,
        intensity_db=avg_intensity_db,
        smoothed=smoothed,
        segments=segments,
        sample_rate=sample_rate,
        params=params,
    )


def smooth_signal(intensity_db: np.ndarray, window: int) -> np.ndarray:
    return np.convolve(intensity_db, np.ones(window) / window, mode="same")


def detect_segments(
    smoothed: np.ndarray,
    t: np.ndarray,
    threshold: float,
    min_duration: float,
    min_gap: float,
    padding: float = 0,
) -> List[Tuple[float, float]]:
    dt = t[1] - t[0]
    min_bins = int(min_duration / dt)
    is_music = smoothed > threshold

    segments: List[Tuple[float, float]] = []
    in_segment = False
    start = 0

    for i, val in enumerate(is_music):
        if val and not in_segment:
            start = i
            in_segment = True
        elif not val and in_segment:
            in_segment = False
            if (i - start) >= min_bins:
                segments.append((t[start], t[i]))
    if in_segment and (len(is_music) - start) >= min_bins:
        segments.append((t[start], t[-1]))

    if padding > 0:
        segments = pad_segments(segments, padding, t[-1])

    return merge_segments(segments, min_gap)


def pad_segments(
    segments: List[Tuple[float, float]],
    padding: float,
    max_time: float,
) -> List[Tuple[float, float]]:
    return [
        (max(0, start - padding), min(max_time, end + padding))
        for start, end in segments
    ]


def merge_segments(
    segments: List[Tuple[float, float]],
    min_gap: float,
) -> List[Tuple[float, float]]:
    if not segments:
        return []

    merged = [segments[0]]
    for start, end in segments[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end + min_gap:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    return merged
