from pathlib import Path
import wave
import struct

import ffmpeg

file_path = "./media/szary_copy.wav"

def normalise_16bit(data):
    return [ abs(float(value) / pow(2, 15)) for value in data ]

def read_16bit_to_float(path):
    wave_read = wave.open(path)
    frames = wave_read.getnframes()
    chunks = wave_read.readframes(frames)
    channels = wave_read.getnchannels()
    return struct.unpack("%ih" % (frames * channels), chunks)

def convert_mp4_to_wav(mp4_path, file_name, output_dir):
    input_path = Path(__file__).parent / mp4_path
    output_path = Path(__file__).parent / output_dir / f"{file_name}.wav"
    print(input_path)
    ffmpeg.input(str(input_path)).output(str(output_path), ac=1, ar=16000).run(quiet=True)
    return str(output_path)

def extract_m4a_segments(m4a_path, t_segments, output_dir):
    output_dir = Path(output_dir)
    paths = []
    for i, (start, end) in enumerate(t_segments):
        out_path = output_dir / f"segment_{i:03d}.m4a"
        ffmpeg.input(m4a_path, ss=start, to=end).output(str(out_path), c='copy').run(quiet=True)
        paths.append(str(out_path))
    return paths

def convert_m4as_to_mp3s(m4a_paths, output_dir, base_name):
    output_dir = Path(output_dir)
    paths = []
    for i, m4a_path in enumerate(m4a_paths):
        out_path = output_dir / f"{base_name}_segment_{i:02d}.mp3"
        ffmpeg.input(m4a_path).output(str(out_path)).run(quiet=True)
        Path(m4a_path).unlink()
        paths.append(str(out_path))
    return paths

def main():
    data = read_16bit_to_float(file_path)
    print(normalise_16bit(data))

if __name__ == "__main__":
    main()
