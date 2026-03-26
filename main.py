from pathlib import Path

import file_loader
import plot
import file_converter

download_link = ""
sample_rate = 16000

def main():
    file_path = file_loader.download_file(download_link, "./media")
    file_name = file_path.split("/")[-1]
    file_name_underscored = file_name.replace(" ", "_")
    media_dir = "media"
    session_dir = file_name_underscored
    outdir = str(Path(__file__).parent / media_dir / session_dir)
    Path(outdir).mkdir(parents=True, exist_ok=True)
    file_path=f"./media/{file_name}.m4a"

    wav_path = file_converter.convert_mp4_to_wav(file_path, file_name, "media")

    data = file_converter.read_16bit_to_float(wav_path)

    segments = plot.plot_data(data, sample_rate, file_name_underscored, outdir)
    m4a_segment_paths = file_converter.extract_m4a_segments(file_path, segments, outdir)
    file_converter.convert_m4as_to_mp3s(m4a_segment_paths, outdir, file_name_underscored)

if __name__ == "__main__":
    main()
