import wave
import struct
import sys

file_path = "./media/szary_copy.wav"

def normalise_16bit(data):
    return [float(value) / pow(2, 15) for value in data]

def read_16bit_to_float(path):
    wave_read = wave.open(path)
    frames = wave_read.getnframes()
    chunks = wave_read.readframes(frames)
    channels = wave_read.getnchannels()
    return struct.unpack("%ih" % (frames * channels), chunks)

def main():
    data = read_16bit_to_float(file_path)
    print(normalise_16bit(data))

if __name__ == "__main__":
    main()
