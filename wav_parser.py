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

def main():
    data = read_16bit_to_float(file_path)
    print(normalise_16bit(data))

if __name__ == "__main__":
    main()
