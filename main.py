from pathlib import Path

import plot
import file_converter

download_link = "https://recorder.google.com/ebef38e4-3d4d-468f-8db8-78bb124859ac"
sample_rate = 16000

def main():
    # file_path = file_manager.download_file(download_link, "./media")
    # file_name = file_path.split("/")[-1]
    file_name="6 Mar at 20-03 circle room c part 1"
    file_name_underscored = file_name.replace(" ", "_")
    media_dir = "media"
    session_dir = file_name_underscored
    outdir = str(Path(__file__).parent / media_dir / session_dir)
    Path(outdir).mkdir(parents=True, exist_ok=True)
    file_path=f"./media/{file_name}.m4a"

    # wav_path = file_converter.convert_mp4_to_wav(file_path, file_name, "media")
    wav_path = str(Path(__file__).parent / "media" / f"{file_name}.wav")
    m4a_path = str(Path(__file__).parent / "media" / f"{file_name}.m4a")

    data = file_converter.read_16bit_to_float(wav_path)


    # normlised_data = wav_parser.normalise_16bit(data)
    segments = plot.plot_data(data, sample_rate, file_name_underscored, outdir)
    # m4a_segment_paths = file_converter.extract_m4a_segments(m4a_path, segments, outdir)
    # file_converter.convert_m4as_to_mp3s(m4a_segment_paths, outdir, file_name_underscored)

if __name__ == "__main__":
    main()
