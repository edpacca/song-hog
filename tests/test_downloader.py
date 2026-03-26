import unittest
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


if __name__ == "__main__":
    unittest.main()
