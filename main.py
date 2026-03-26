from dataclasses import dataclass
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

import file_loader
import plot
import process
import file_converter


@dataclass
class FileSessionData:
    init_m4a_file_path: str
    wav_path: str
    init_file_name: str
    file_name: str
    session_dir: str


def test_get_file_paths(media_dir, download: False):
    if download:
        init_m4a_file_path, init_file_name = test_download(media_dir)
        wav_path = file_converter.convert_m4a_to_wav(init_m4a_file_path, media_dir)
    else:
        init_file_name = os.getenv("TEST_FILE_NAME")
        init_m4a_file_path = str(
            Path(__file__).parent / media_dir / f"{init_file_name}.m4a"
        )
        wav_path = str(Path(__file__).parent / media_dir / f"{init_file_name}.wav")

    file_name = init_file_name.replace(" ", "_")
    session_dir = str(Path(__file__).parent / media_dir / file_name)

    return FileSessionData(
        init_m4a_file_path, wav_path, init_file_name, file_name, session_dir
    )


def test_download(media_dir):
    download_link = os.getenv("DOWNLOAD_LINK")
    return download_file(download_link, media_dir)


def test_analysis(file_session_data: FileSessionData, sample_rate):
    return analyse(
        file_session_data.wav_path,
        sample_rate,
        file_session_data.file_name,
        file_session_data.session_dir,
    )


def test_process_segments(file_session_data: FileSessionData):
    analysis = test_analysis(file_session_data)
    process_segments(
        file_session_data.init_m4a_file_path,
        analysis,
        file_session_data.session_dir,
        file_session_data.file_name,
    )


def download_file(download_link, media_dir):
    file_path = file_loader.download_file(download_link, media_dir)
    file_name = file_path.split("/")[-1]
    return file_path, file_name


def analyse(wav_path, sample_rate, file_name, session_dir, **kwargs):
    data = file_converter.read_16bit_to_float(wav_path)
    analysis = process.analyze(data, sample_rate, **kwargs)
    plot.plot_data(analysis, data, file_name, session_dir)
    return analysis


def process_segments(input_m4a_file_path, analysis, out_dir, out_file_name):
    segments = analysis.segments
    m4a_segment_paths = file_converter.extract_m4a_segments(
        input_m4a_file_path, segments, out_dir
    )
    file_converter.convert_m4as_to_mp3s(m4a_segment_paths, out_dir, out_file_name)


def test_compare_window_values(file_session_data, sample_rate):
    analyses = []
    data = file_converter.read_16bit_to_float(file_session_data.wav_path)

    windows = [1, 100, 200, 400, 600, 800, 1200]
    for window in windows:
        analysis = process.analyze(data, sample_rate, window=window)
        analyses.append(analysis)
    figure = plot.experimental_plots_compare_smoothed_and_segments(analyses, "window")
    expt_file_name = f"{file_session_data.file_name}_compare_window"
    plot.save_figure(figure, file_session_data.session_dir, expt_file_name)


def main():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S"
    )
    media_dir = "media"
    sample_rate = 16000
    file_session_data = test_get_file_paths(media_dir, download=False)
    Path(file_session_data.session_dir).mkdir(parents=True, exist_ok=True)
    # test_analysis(file_session_data, sample_rate)
    # test_process_segments(file_session_data)

    test_compare_window_values(file_session_data, sample_rate)


if __name__ == "__main__":
    main()
