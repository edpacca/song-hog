import logging
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
from matplotlib.mlab import specgram as mlab_specgram

logger = logging.getLogger(__name__)


@dataclass
class AudioAnalysis:
    spectrum: np.ndarray  # linear power, shape (freqs, time_bins)
    freqs: np.ndarray
    t: np.ndarray
    intensity_db: np.ndarray  # avg, log-transformed, clamped
    smoothed: np.ndarray
    segments: List[Tuple[float, float]]
    sample_rate: int
    params_str: str
    params_full_str: str

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
    window: int = 400,
    threshold: float = 35,
    min_duration: float = 40,
    min_gap: float = 20,
    padding: float = 5,
) -> AudioAnalysis:
    logger.info(f"Analysing  window={window}  threshold={threshold}dB  min_duration={min_duration}s  min_gap={min_gap}s  padding={padding}s")
    spectrum, freqs, t = compute_spectrogram(data, sample_rate)

    avg_intensity = spectrum.mean(axis=0)
    avg_intensity[avg_intensity == 0] = 1e-10
    avg_intensity_db = 10 * np.log10(avg_intensity)
    avg_intensity_db[avg_intensity_db < 0] = 0

    smoothed = smooth_signal(avg_intensity_db, window)
    segments = detect_segments(smoothed, t, threshold, min_duration, min_gap, padding)

    logger.info(f"Analysis complete — {len(segments)} segment(s) found")
    return AudioAnalysis(
        spectrum=spectrum,
        freqs=freqs,
        t=t,
        intensity_db=avg_intensity_db,
        smoothed=smoothed,
        segments=segments,
        sample_rate=sample_rate,
        params_str=f"w={window}__th={threshold}__md={min_duration}__mg={min_gap}__p={padding}",
        params_full_str=f"window={window} threshold={threshold}db min_duration={min_duration}s min_gap={min_gap}s padding={padding}s"
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
