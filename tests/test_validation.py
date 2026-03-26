import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from file_loader._validation import (
    _INVALID_URL_ERROR,
    _DEFAULT_FILE_ID_RE,
    extract_file_id,
    sanitize_filename,
)
from file_loader.downloader import GOOGLE_RECORDER

_BASE = GOOGLE_RECORDER.input_url_base


class TestExtractFileId(unittest.TestCase):

    _VALID_CASES = [
        ("https://recorder.google.com/abc123", "abc123"),
        ("https://recorder.google.com/abc123?authuser=1", "abc123"),
        ("https://recorder.google.com/abc123?authuser=1&foo=bar", "abc123"),
        ("https://recorder.google.com/66bab67a-62193-4368-1031a-3d91717acaa3",
         "66bab67a-62193-4368-1031a-3d91717acaa3"),
    ]

    _INVALID_URLS = [
        # Wrong base
        "https://example.com/somefile",
        "",
        # ID allowlist enforcement
        "https://recorder.google.com/abc%2Fdef",   # percent-encoded slash
        "https://recorder.google.com/abc%252Fdef",  # double-encoded slash
        "https://recorder.google.com/abc.def",      # dot
        "https://recorder.google.com/abc def",      # space
    ]

    def test_extracts_id(self):
        for url, expected in self._VALID_CASES:
            with self.subTest(url=url):
                self.assertEqual(extract_file_id(_BASE, url), expected)

    def test_invalid_urls_raise(self):
        for url in self._INVALID_URLS:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    extract_file_id(_BASE, url)

    def test_error_message_is_generic(self):
        with self.assertRaises(ValueError) as ctx:
            extract_file_id(_BASE, "https://example.com/somefile")
        self.assertEqual(str(ctx.exception), _INVALID_URL_ERROR)


class TestSanitizeFilename(unittest.TestCase):

    _EXACT_TRANSFORMS = [
        ("my_recording.m4a", "my_recording.m4a"),   # clean name unchanged
        ("my recording.m4a", "my_recording.m4a"),   # spaces replaced
        ("../../evil.m4a", "evil.m4a"),              # path traversal stripped
        ("my-recording.m4a", "my-recording.m4a"),   # hyphens preserved
    ]

    def test_exact_transforms(self):
        for name, expected in self._EXACT_TRANSFORMS:
            with self.subTest(name=name):
                self.assertEqual(sanitize_filename(name), expected)

    def test_special_chars_replaced(self):
        result = sanitize_filename("band rehearsal (2024).m4a")
        self.assertNotIn("(", result)
        self.assertNotIn(")", result)

    def test_unicode_replaced(self):
        result = sanitize_filename("café.m4a")
        self.assertRegex(result, r"^[\w\-._]+$")


if __name__ == "__main__":
    unittest.main()
