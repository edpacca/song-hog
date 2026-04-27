import logging
from pathlib import Path

logger = logging.getLogger(__name__)
import wave
from typing import Sequence

import numpy as np
import ffmpeg


def read_wav_as_float(path: str) -> np.ndarray:
    """Read a 16-bit WAV file and return sample data as a float32 numpy array.

    Values are in the original int16 range (-32768 to 32767) to preserve
    the dB scale used by the analysis thresholds.
    """
    logger.info(f"Reading file: {path}")
    with wave.open(path) as wf:
        frames = wf.getnframes()
        channels = wf.getnchannels()
        raw = wf.readframes(frames)
    data = np.frombuffer(raw, dtype=np.int16)
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1).astype(np.int16)
    return data.astype(np.float32)


def convert_m4a_to_mono_wav(m4a_path: str, file_name: str, output_dir: str, sample_rate: int = 16000) -> str:
    """Convert an M4A file to a mono WAV file at the given sample rate.

    Args:
        m4a_path: Path to the source M4A file.
        file_name: Base name for the output WAV file (without extension).
        output_dir: Directory where the output WAV file will be written.
        sample_rate: Target sample rate in Hz. Defaults to 16000.

    Returns:
        Absolute path to the created WAV file.
    """
    output_path = Path(output_dir) / f"{file_name}.wav"
    logger.info(f"Converting {m4a_path} to mono WAV at {sample_rate}Hz -> {output_path}")
    ffmpeg.input(m4a_path).output(str(output_path), ac=1, ar=sample_rate).run()
    return str(output_path)


def extract_m4a_segments(m4a_path: str, t_segments: Sequence[tuple[float, float]], output_dir: str) -> list[str]:
    """Extract time-bounded segments from an M4A file into separate M4A files.

    Args:
        m4a_path: Path to the source M4A file.
        t_segments: Sequence of (start, end) time pairs in seconds.
        output_dir: Directory where segment files will be written.

    Returns:
        List of paths to the extracted segment files.
    """
    output_dir = Path(output_dir)
    paths = []
    for i, (start, end) in enumerate(t_segments):
        out_path = output_dir / f"segment_{i:02d}.m4a"
        logger.info(f"Extracting segment {i:02d}: {start}s -> {end}s to {out_path}")
        ffmpeg.input(m4a_path, ss=start, to=end).output(str(out_path), c='copy').run(quiet=True)
        paths.append(str(out_path))
    return paths


def convert_m4as_to_mp3s(m4a_paths: list[str], output_dir: str, base_name: str) -> list[str]:
    """Convert a list of M4A segment files to MP3 files, removing the originals.

    Args:
        m4a_paths: List of paths to M4A files to convert.
        output_dir: Directory where the output MP3 files will be written.
        base_name: Base name prefix used for all output MP3 files.

    Returns:
        List of paths to the created MP3 files.
    """
    output_dir = Path(output_dir)
    paths = []
    for i, m4a_path in enumerate(m4a_paths):
        out_path = output_dir / f"{base_name}_segment_{i:02d}.mp3"
        logger.info(f"Converting {m4a_path} to MP3 -> {out_path}")
        ffmpeg.input(m4a_path).output(str(out_path)).run(quiet=True)
        Path(m4a_path).unlink()
        logger.debug(f"Deleted source file: {m4a_path}")
        paths.append(str(out_path))
    return paths
