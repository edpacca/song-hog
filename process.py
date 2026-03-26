import logging
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
from matplotlib.mlab import specgram as mlab_specgram

logger = logging.getLogger(__name__)


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
    spectrum: np.ndarray  # linear power, shape (freqs, time_bins)
    freqs: np.ndarray
    t: np.ndarray
    intensity_db: np.ndarray  # avg, log-transformed, clamped
    smoothed: np.ndarray
    segments: List[Tuple[float, float]]
    sample_rate: int
    params: AnalysisParams


def compute_spectrogram(
    data: np.ndarray,
    sample_rate: int,
    NFFT: int = 1024,
    noverlap: int = 512,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    spectrum, freqs, t = mlab_specgram(
        data, Fs=sample_rate, NFFT=NFFT, noverlap=noverlap
    )
    return spectrum, freqs, t


def analyze(
    data: np.ndarray,
    sample_rate: int,
    params: AnalysisParams = None,
) -> AudioAnalysis:
    if params is None:
        params = AnalysisParams()
    logger.info(f"Analysing  window={params.window}  threshold={params.threshold}dB  min_duration={params.min_duration}s  min_gap={params.min_gap}s  padding={params.padding}s")
    spectrum, freqs, t = compute_spectrogram(data, sample_rate)

    avg_intensity = spectrum.mean(axis=0)
    avg_intensity[avg_intensity == 0] = 1e-10
    avg_intensity_db = 10 * np.log10(avg_intensity)
    avg_intensity_db[avg_intensity_db < 0] = 0

    smoothed = smooth_signal(avg_intensity_db, params.window)
    segments = detect_segments(smoothed, t, params.threshold, params.min_duration, params.min_gap, params.padding)

    logger.info(f"Analysis complete — {len(segments)} segment(s) found")
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
