import os
import unittest
import process
from file_converter import read_16bit_to_float

TEST_WAVE = os.path.join(
    os.path.dirname(__file__), "..", "static", "test_wave_LISTENING_NOT_RECOMMENDED.wav"
)

FLAT_PARAMETERS = process.AnalysisParams(1, 35, 0, 0, 0)

# Test WAV has alternating 2.0s segments of loud noise and quiet.
# Expected segment boundaries reflect two STFT artefacts:
#
# 1. Start offset (+0.032s on first segment only):
#    mlab_specgram returns bin centres, so t[0] = NFFT/2 / sample_rate
#    = 512 / 16000 = 0.032s. The first detectable bin is already half
#    a window into the file, so segment detection can never report t=0.
#
# 2. End offset (+0.016s on every segment):
#    Bin spacing = hop / sample_rate = 512 / 16000 = 0.032s.
#    Each true boundary (2s, 6s, …) falls exactly midway between two bins
#    (e.g. 2.000 / 0.032 = 62.5). detect_segments records t[i] where i is
#    the first *silent* bin, which is centred 0.016s (half a bin) past the
#    true boundary.
EXPECTED_SEGMENTS_SECONDS = [
    (0.032, 2.016),
    (4.000, 6.016),
    (8.000, 10.016),
    (12.000, 14.016),
    (16.000, 18.016),
]


class TestanalyseWithTestWave(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = read_16bit_to_float(TEST_WAVE)
        cls.sample_rate = 16000

    def test_segment_count(self):
        result = process.analyse(self.data, self.sample_rate, FLAT_PARAMETERS)
        self.assertEqual(len(result.segments), len(EXPECTED_SEGMENTS_SECONDS))

    def test_segment_boundaries(self):
        result = process.analyse(self.data, self.sample_rate, FLAT_PARAMETERS)
        for i, (start, end) in enumerate(result.segments):
            exp_start, exp_end = EXPECTED_SEGMENTS_SECONDS[i]
            self.assertEqual(start, exp_start)
            self.assertEqual(end, exp_end)
