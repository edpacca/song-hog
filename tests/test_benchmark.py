import logging
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import benchmark
from benchmark import _MemoryPoller, _read_rss_kb, measure
import process
from file_converter import read_wav_as_float

TEST_WAVE = os.path.join(
    os.path.dirname(__file__), "..", "static", "test_wave_LISTENING_NOT_RECOMMENDED.wav"
)

FLAT_PARAMETERS = process.AnalysisParams(1, 35, 0, 0, 0)

MEMORY_CEILING_MB = 200


def setUpModule():
    logging.disable(logging.CRITICAL)


def tearDownModule():
    logging.disable(logging.NOTSET)

"""
Note these tests will fail if not run on a linux system.
They read /proc/self/status for RAM consumption metrics which will not be available on another OS.
"""
class TestMeasureDecorator(unittest.TestCase):

    def setUp(self):
        self._orig = os.environ.pop("BENCHMARK", None)

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("BENCHMARK", None)
        else:
            os.environ["BENCHMARK"] = self._orig

    def test_passthrough_when_disabled(self):
        @measure
        def add(a, b):
            return a + b

        self.assertEqual(add(2, 3), 5)

    def test_returns_correct_result_when_enabled(self):
        os.environ["BENCHMARK"] = "1"

        @measure
        def add(a, b):
            return a + b

        self.assertEqual(add(2, 3), 5)

    def test_logs_benchmark_info_when_enabled(self):
        os.environ["BENCHMARK"] = "1"

        @measure
        def my_func():
            return 42

        with patch.object(benchmark.logger, "info") as mock_info:
            my_func()

        mock_info.assert_called_once()
        self.assertIn("my_func", mock_info.call_args[0])


class TestPipelineSanity(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ["BENCHMARK"] = "1"
        cls.data = read_wav_as_float(TEST_WAVE)
        cls.sample_rate = 16000

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("BENCHMARK", None)

    def test_read_wav_completes(self):
        data = read_wav_as_float(TEST_WAVE)
        self.assertEqual(data.dtype.name, "float32")
        self.assertGreater(len(data), 0)

    def test_analyse_completes_with_segments(self):
        result = process.analyse(self.data, self.sample_rate, FLAT_PARAMETERS)
        self.assertGreaterEqual(len(result.segments), 1)

    def test_analyse_memory_within_bounds(self):
        rss_before = _read_rss_kb()
        poller = _MemoryPoller()
        poller.start()
        process.analyse(self.data, self.sample_rate, FLAT_PARAMETERS)
        poller.stop()
        peak_growth_mb = (poller.peak_kb - rss_before) / 1024
        self.assertLess(peak_growth_mb, MEMORY_CEILING_MB)


if __name__ == "__main__":
    unittest.main()
