from pathlib import Path

import debug_plot
import file_manager
import wav_parser

download_link = "https://recorder.google.com/ebef38e4-3d4d-468f-8db8-78bb124859ac"

def main():
    # file_path = file_manager.download_file(download_link, "./media")
    # file_name = file_path.split("/")[-1]
    file_name="6 Mar at 20-03 circle room c part 1"
    file_path=f"./media/{file_name}.m4a"
    # wav_path = wav_parser.convert_mp4_to_wav(file_path, file_name, "Media")
    wav_path = str(Path(__file__).parent / "media" / f"{file_name}.wav")
    data = wav_parser.read_16bit_to_float(wav_path)
    # normlised_data = wav_parser.normalise_16bit(data)
    debug_plot.plot_data(data, 16000)

if __name__ == "__main__":
    main()
