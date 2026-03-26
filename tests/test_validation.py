import unittest
import unittest.mock
import socket
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from file_loader._validation import (
    _INVALID_URL_ERROR,
    _DEFAULT_FILE_ID_RE,
    _resolves_to_private_ip,
    extract_file_id,
    sanitize_filename,
    validate_url,
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


class TestResolvesToPrivateIp(unittest.TestCase):

    def _make_addrinfo(self, ip):
        # socket.getaddrinfo returns a list of 5-tuples; [4] is (address, port, ...)
        return [(None, None, None, None, (ip, 0))]

    def test_loopback_is_blocked(self):
        with unittest.mock.patch("socket.getaddrinfo", return_value=self._make_addrinfo("127.0.0.1")):
            self.assertTrue(_resolves_to_private_ip("localhost"))

    def test_private_range_is_blocked(self):
        with unittest.mock.patch("socket.getaddrinfo", return_value=self._make_addrinfo("192.168.1.1")):
            self.assertTrue(_resolves_to_private_ip("internal.host"))

    def test_link_local_is_blocked(self):
        with unittest.mock.patch("socket.getaddrinfo", return_value=self._make_addrinfo("169.254.169.254")):
            self.assertTrue(_resolves_to_private_ip("metadata.internal"))

    def test_public_ip_is_allowed(self):
        with unittest.mock.patch("socket.getaddrinfo", return_value=self._make_addrinfo("8.8.8.8")):
            self.assertFalse(_resolves_to_private_ip("dns.google"))

    def test_unresolvable_host_is_blocked(self):
        with unittest.mock.patch("socket.getaddrinfo", side_effect=socket.gaierror):
            self.assertTrue(_resolves_to_private_ip("this.does.not.exist"))


class TestValidateUrl(unittest.TestCase):
    """Direct unit tests for validate_url using GOOGLE_RECORDER as config."""

    def test_valid_url_does_not_raise(self):
        with unittest.mock.patch("file_loader._validation._resolves_to_private_ip", return_value=False):
            validate_url(GOOGLE_RECORDER, "https://recorder.google.com/abc123")

    def test_length_cap(self):
        long_url = "https://recorder.google.com/" + "a" * 2048
        with self.assertRaises(ValueError) as ctx:
            validate_url(GOOGLE_RECORDER, long_url)
        self.assertEqual(str(ctx.exception), _INVALID_URL_ERROR)

    def test_wrong_scheme(self):
        with self.assertRaises(ValueError):
            validate_url(GOOGLE_RECORDER, "http://recorder.google.com/abc123")

    def test_wrong_host(self):
        with self.assertRaises(ValueError):
            validate_url(GOOGLE_RECORDER, "https://evil.com/abc123")

    def test_directory_traversal_raw(self):
        with self.assertRaises(ValueError):
            validate_url(GOOGLE_RECORDER, "https://recorder.google.com/../etc/passwd")

    def test_directory_traversal_encoded(self):
        with self.assertRaises(ValueError):
            validate_url(GOOGLE_RECORDER, "https://recorder.google.com/..%2Fetc%2Fpasswd")

    def test_empty_path_raises(self):
        with self.assertRaises(ValueError):
            validate_url(GOOGLE_RECORDER, "https://recorder.google.com/")

    def test_ssrf_private_ip_raises(self):
        with unittest.mock.patch("file_loader._validation._resolves_to_private_ip", return_value=True):
            with self.assertRaises(ValueError):
                validate_url(GOOGLE_RECORDER, "https://recorder.google.com/abc123")


if __name__ == "__main__":
    unittest.main()
