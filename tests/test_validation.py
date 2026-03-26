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


class TestExtractFileId(unittest.TestCase):

    def test_basic_url(self):
        url = "https://recorder.google.com/abc123"
        self.assertEqual(extract_file_id(GOOGLE_RECORDER.input_url_base, url), "abc123")

    def test_url_with_query_param(self):
        url = "https://recorder.google.com/abc123?authuser=1"
        self.assertEqual(extract_file_id(GOOGLE_RECORDER.input_url_base, url), "abc123")

    def test_url_with_multiple_query_params(self):
        url = "https://recorder.google.com/abc123?authuser=1&foo=bar"
        self.assertEqual(extract_file_id(GOOGLE_RECORDER.input_url_base, url), "abc123")

    def test_real_looking_uuid(self):
        url = "https://recorder.google.com/66bab67a-62193-4368-1031a-3d91717acaa3"
        self.assertEqual(
            extract_file_id(GOOGLE_RECORDER.input_url_base, url),
            "66bab67a-62193-4368-1031a-3d91717acaa3",
        )

    def test_url_missing_base_raises(self):
        with self.assertRaises(ValueError) as ctx:
            extract_file_id(GOOGLE_RECORDER.input_url_base, "https://example.com/somefile")
        self.assertEqual(str(ctx.exception), _INVALID_URL_ERROR)

    def test_empty_string_raises(self):
        with self.assertRaises(ValueError):
            extract_file_id(GOOGLE_RECORDER.input_url_base, "")

    # ID allowlist enforcement
    def test_percent_encoded_slash_rejected(self):
        url = "https://recorder.google.com/abc%2Fdef"
        with self.assertRaises(ValueError):
            extract_file_id(GOOGLE_RECORDER.input_url_base, url)

    def test_double_encoded_slash_rejected(self):
        url = "https://recorder.google.com/abc%252Fdef"
        with self.assertRaises(ValueError):
            extract_file_id(GOOGLE_RECORDER.input_url_base, url)

    def test_dot_in_id_rejected(self):
        url = "https://recorder.google.com/abc.def"
        with self.assertRaises(ValueError):
            extract_file_id(GOOGLE_RECORDER.input_url_base, url)

    def test_space_in_id_rejected(self):
        url = "https://recorder.google.com/abc def"
        with self.assertRaises(ValueError):
            extract_file_id(GOOGLE_RECORDER.input_url_base, url)


class TestSanitizeFilename(unittest.TestCase):

    def test_clean_name_unchanged(self):
        self.assertEqual(sanitize_filename("my_recording.m4a"), "my_recording.m4a")

    def test_spaces_replaced(self):
        self.assertEqual(sanitize_filename("my recording.m4a"), "my_recording.m4a")

    def test_path_traversal_stripped(self):
        self.assertEqual(sanitize_filename("../../evil.m4a"), "evil.m4a")

    def test_special_chars_replaced(self):
        result = sanitize_filename("band rehearsal (2024).m4a")
        self.assertNotIn("(", result)
        self.assertNotIn(")", result)

    def test_hyphens_preserved(self):
        self.assertEqual(sanitize_filename("my-recording.m4a"), "my-recording.m4a")

    def test_unicode_replaced(self):
        result = sanitize_filename("café.m4a")
        self.assertRegex(result, r"^[\w\-._]+$")


if __name__ == "__main__":
    unittest.main()
