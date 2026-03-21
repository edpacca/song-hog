import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from file_manager import extract_file_id, google_url_base


class TestExtractFileId(unittest.TestCase):

    def test_basic_url(self):
        url = "https://recorder.google.com/abc123"
        self.assertEqual(extract_file_id(google_url_base, url), "abc123")

    def test_url_with_query_param(self):
        url = "https://recorder.google.com/abc123?authuser=1"
        self.assertEqual(extract_file_id(google_url_base, url), "abc123")

    def test_url_with_multiple_query_params(self):
        url = "https://recorder.google.com/abc123?authuser=1&foo=bar"
        self.assertEqual(extract_file_id(google_url_base, url), "abc123")

    def test_real_looking_uuid(self):
        url = "https://recorder.google.com/66bab67a-62193-4368-1031j-3d91717acaa3"
        self.assertEqual(
            extract_file_id(google_url_base, url),
            "66bab67a-62193-4368-1031j-3d91717acaa3",
        )

    def test_url_missing_base_returns_none(self):
        url = "https://example.com/somefile"
        result = extract_file_id(google_url_base, url)
        self.assertIsNone(result)

    def test_empty_string_returns_none(self):
        result = extract_file_id(google_url_base, "")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
