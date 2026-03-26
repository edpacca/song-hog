import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from file_loader._validation import _INVALID_URL_ERROR
from file_loader.downloader import google_recorder


class TestValidateGoogleRecorderUrl(unittest.TestCase):

    def test_valid_url(self):
        # Should not raise
        google_recorder.validate_url("https://recorder.google.com/abc123")

    def test_valid_url_with_query_params(self):
        google_recorder.validate_url("https://recorder.google.com/abc123?authuser=1")

    # Scheme allowlist
    def test_http_scheme_raises(self):
        with self.assertRaises(ValueError):
            google_recorder.validate_url("http://recorder.google.com/abc123")

    def test_file_scheme_raises(self):
        with self.assertRaises(ValueError):
            google_recorder.validate_url("file:///etc/passwd")

    def test_ftp_scheme_raises(self):
        with self.assertRaises(ValueError):
            google_recorder.validate_url("ftp://recorder.google.com/abc123")

    def test_javascript_scheme_raises(self):
        with self.assertRaises(ValueError):
            google_recorder.validate_url("javascript://recorder.google.com/abc123")

    # Host checks
    def test_wrong_host_raises(self):
        with self.assertRaises(ValueError):
            google_recorder.validate_url("https://evil.com/abc123")

    def test_subdomain_raises(self):
        with self.assertRaises(ValueError):
            google_recorder.validate_url("https://evil.recorder.google.com/abc123")

    def test_no_file_id_raises(self):
        with self.assertRaises(ValueError):
            google_recorder.validate_url("https://recorder.google.com/")

    # Length cap
    def test_url_exceeding_max_length_raises(self):
        long_url = "https://recorder.google.com/" + "a" * 2048
        with self.assertRaises(ValueError):
            google_recorder.validate_url(long_url)

    # Directory traversal
    def test_path_traversal_raw_raises(self):
        with self.assertRaises(ValueError):
            google_recorder.validate_url("https://recorder.google.com/../etc/passwd")

    def test_path_traversal_encoded_raises(self):
        with self.assertRaises(ValueError):
            google_recorder.validate_url("https://recorder.google.com/..%2Fetc%2Fpasswd")

    def test_path_traversal_double_encoded_raises(self):
        with self.assertRaises(ValueError):
            google_recorder.validate_url("https://recorder.google.com/..%252Fetc%252Fpasswd")

    # SSRF — private IP ranges
    def test_localhost_raises(self):
        with self.assertRaises(ValueError):
            google_recorder.validate_url("https://localhost/abc123")

    def test_loopback_ip_raises(self):
        with self.assertRaises(ValueError):
            google_recorder.validate_url("https://127.0.0.1/abc123")

    def test_metadata_endpoint_raises(self):
        with self.assertRaises(ValueError):
            google_recorder.validate_url("https://169.254.169.254/latest/meta-data")

    # Generic error message — no internal detail leaked
    def test_error_message_is_generic(self):
        with self.assertRaises(ValueError) as ctx:
            google_recorder.validate_url("https://evil.com/abc123")
        self.assertEqual(str(ctx.exception), _INVALID_URL_ERROR)


if __name__ == "__main__":
    unittest.main()
