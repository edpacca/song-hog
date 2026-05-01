"""Run the full audio processing pipeline on a single M4A file for benchmarking.

Usage:
    python benchmark_runner.py path/to/recording.m4a [output_dir]
    /usr/bin/time -v python benchmark_runner.py path/to/recording.m4a

The original M4A is never deleted, so the same file can be reused across runs.
Output goes to <output_dir> (default: benchmark_out/ next to the input file).
"""
import logging
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import file_converter
import plot
import process
from logging_config import configure_logging

configure_logging()
logger = logging.getLogger("song_hog.benchmark_runner")

SAMPLE_RATE = 16000


def run(m4a_path: str, output_dir: str) -> None:
    m4a = Path(m4a_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    session_name = m4a.stem

    ENABLE_PLOT = os.getenv("ENABLE_PLOT", "0") == "1"
    KEEP_BENCHMARK_OUTPUT_FILES = os.getenv("KEEP_BENCHMARK_OUTPUT_FILES", "0") == "1"
    os.environ["BENCHMARK"] = "1"

    logger.info("=== benchmark start: %s ===", m4a.name)

    wav_path = file_converter.convert_m4a_to_mono_wav(str(m4a), session_name, str(out), SAMPLE_RATE)
    data = file_converter.read_wav_as_float(wav_path)
    analysis = process.analyse(data, SAMPLE_RATE, process.params_from_env(), include_spectrum=ENABLE_PLOT)
    if ENABLE_PLOT:
        plot.plot_data(analysis, data, session_name, str(out), export=True, show=False)
    Path(wav_path).unlink()

    segment_paths = file_converter.extract_m4a_segments(str(m4a), analysis.segments, str(out))
    output_paths = file_converter.convert_m4as_to_mp3s(segment_paths, str(out), session_name)

    if not KEEP_BENCHMARK_OUTPUT_FILES:
        for path in output_paths:
            Path(path).unlink()

    logger.info("=== benchmark complete: %d segment(s) -> %s ===", len(analysis.segments), out)



if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <m4a_path> [output_dir]", file=sys.stderr)
        sys.exit(1)

    m4a_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else str(Path(m4a_path).parent / "benchmark_out")

    run(m4a_path, output_dir)
