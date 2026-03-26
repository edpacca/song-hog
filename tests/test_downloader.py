import unittest
import unittest.mock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from file_loader._validation import _INVALID_URL_ERROR
from file_loader.downloader import google_recorder


class TestValidateGoogleRecorderUrl(unittest.TestCase):

    _VALID_URLS = [
        "https://recorder.google.com/abc123",
        "https://recorder.google.com/abc123?authuser=1",
    ]

    _INVALID_URLS = [
        # Scheme allowlist
        "http://recorder.google.com/abc123",
        "file:///etc/passwd",
        "ftp://recorder.google.com/abc123",
        "javascript://recorder.google.com/abc123",
        # Host checks
        "https://evil.com/abc123",
        "https://evil.recorder.google.com/abc123",
        "https://recorder.google.com/",
        # Length cap
        "https://recorder.google.com/" + "a" * 2048,
        # Directory traversal
        "https://recorder.google.com/../etc/passwd",
        "https://recorder.google.com/..%2Fetc%2Fpasswd",
        "https://recorder.google.com/..%252Fetc%252Fpasswd",
        # SSRF — private IP ranges
        "https://localhost/abc123",
        "https://127.0.0.1/abc123",
        "https://169.254.169.254/latest/meta-data",
    ]

    def test_valid_urls_do_not_raise(self):
        for url in self._VALID_URLS:
            with self.subTest(url=url):
                google_recorder.validate_url(url)

    def test_invalid_urls_raise(self):
        for url in self._INVALID_URLS:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    google_recorder.validate_url(url)

    def test_error_message_is_generic(self):
        with self.assertRaises(ValueError) as ctx:
            google_recorder.validate_url("https://evil.com/abc123")
        self.assertEqual(str(ctx.exception), _INVALID_URL_ERROR)


class TestExtractId(unittest.TestCase):

    def test_extracts_valid_id(self):
        self.assertEqual(google_recorder.extract_id("https://recorder.google.com/abc-123"), "abc-123")

    def test_strips_query_string(self):
        self.assertEqual(google_recorder.extract_id("https://recorder.google.com/abc123?authuser=1"), "abc123")

    def test_invalid_id_characters_raise(self):
        with self.assertRaises(ValueError):
            google_recorder.extract_id("https://recorder.google.com/../etc/passwd")

    def test_missing_id_raises(self):
        with self.assertRaises(ValueError):
            google_recorder.extract_id("https://recorder.google.com/")


class TestBuildDownloadUrl(unittest.TestCase):

    def test_builds_valid_url(self):
        url = google_recorder._build_download_url("abc-123")
        self.assertEqual(url, "https://pixelrecorder-pa.googleapis.com/download/playback/abc-123")

    def test_invalid_id_raises(self):
        with self.assertRaises(ValueError):
            google_recorder._build_download_url("bad/id")


class TestParseFilename(unittest.TestCase):

    def _make_response(self, headers):
        response = unittest.mock.MagicMock()
        response.headers = headers
        return response

    def test_extracts_filename(self):
        response = self._make_response({"Content-Disposition": 'attachment; filename="my_recording.m4a"'})
        self.assertEqual(google_recorder._parse_filename(response), "my_recording.m4a")

    def test_missing_header_raises(self):
        response = self._make_response({"Content-Disposition": ""})
        with self.assertRaises(RuntimeError):
            google_recorder._parse_filename(response)

    def test_sanitizes_filename(self):
        response = self._make_response({"Content-Disposition": 'attachment; filename="../../evil.m4a"'})
        self.assertEqual(google_recorder._parse_filename(response), "evil.m4a")


class TestParseTotalSize(unittest.TestCase):

    def _make_response(self, headers):
        response = unittest.mock.MagicMock()
        response.headers = headers
        return response

    def test_uses_content_range_when_present(self):
        response = self._make_response({"Content-Range": "bytes 0-999/5000", "Content-Length": "1000"})
        self.assertEqual(google_recorder._parse_total_size(response), 5000)

    def test_falls_back_to_content_length(self):
        response = self._make_response({"Content-Range": "", "Content-Length": "1234"})
        self.assertEqual(google_recorder._parse_total_size(response), 1234)


class TestVerifyDownload(unittest.TestCase):

    def test_passes_when_size_matches(self):
        with unittest.mock.patch("os.path.getsize", return_value=1000):
            google_recorder._verify_download("/tmp/file.m4a", 1000)  # should not raise

    def test_raises_when_incomplete(self):
        with unittest.mock.patch("os.path.getsize", return_value=500):
            with self.assertRaises(RuntimeError):
                google_recorder._verify_download("/tmp/file.m4a", 1000)

    def test_skips_check_when_expected_size_zero(self):
        google_recorder._verify_download("/tmp/file.m4a", 0)  # should not raise


class TestMakeStreamingGet(unittest.TestCase):

    def test_raises_on_redirect(self):
        session = unittest.mock.MagicMock()
        response = unittest.mock.MagicMock()
        response.is_redirect = True
        response.status_code = 301
        session.get.return_value = response
        with self.assertRaises(RuntimeError, msg="Unexpected redirect from download server"):
            google_recorder._make_streaming_get(session, "https://pixelrecorder-pa.googleapis.com/download/playback/abc")

    def test_raises_on_non_2xx(self):
        session = unittest.mock.MagicMock()
        response = unittest.mock.MagicMock()
        response.is_redirect = False
        response.status_code = 200
        response.raise_for_status.side_effect = Exception("403")
        session.get.return_value = response
        with self.assertRaises(Exception):
            google_recorder._make_streaming_get(session, "https://pixelrecorder-pa.googleapis.com/download/playback/abc")

    def test_returns_response_on_success(self):
        session = unittest.mock.MagicMock()
        response = unittest.mock.MagicMock()
        response.is_redirect = False
        response.status_code = 200
        response.raise_for_status.return_value = None
        session.get.return_value = response
        result = google_recorder._make_streaming_get(session, "https://pixelrecorder-pa.googleapis.com/download/playback/abc")
        self.assertEqual(result, response)


if __name__ == "__main__":
    unittest.main()
