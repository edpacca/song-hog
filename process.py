from typing import List, Tuple

import numpy as np

def smooth_signal(intensity_db, window):
    return np.convolve(intensity_db, np.ones(window)/window, mode='same')

def detect_segments(smoothed, t, threshold, min_duration, min_gap, padding=0):
    dt = t[1] - t[0]
    min_bins = int(min_duration / dt)
    is_music = smoothed > threshold

    segments = []
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

def pad_segments(segments, padding, max_time):
    return [
        (max(0, start - padding), min(max_time, end + padding))
        for start, end in segments
    ]

def merge_segments(segments, min_gap) -> List[Tuple[int, int]]:
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
