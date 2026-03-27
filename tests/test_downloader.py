import re
import unittest
import unittest.mock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from file_loader._validation import _INVALID_URL_ERROR
from file_loader.downloader import downloader_from_env, google_recorder


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
        # These look like SSRF targets but are actually rejected by the host-match
        # check (step 4) before the DNS/SSRF guard (step 7) is ever reached.
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


class TestSsrfGuard(unittest.TestCase):
    """
    The SSRF DNS check (step 7 of validate_url) is only reached when the host
    already matches the allowlist.  These tests mock socket.getaddrinfo to
    simulate a valid hostname resolving to a private IP.
    """

    _PRIVATE_RESULT = [(None, None, None, None, ("127.0.0.1", 0))]
    _PUBLIC_RESULT  = [(None, None, None, None, ("1.2.3.4", 0))]

    def test_raises_when_valid_host_resolves_to_private_ip(self):
        with unittest.mock.patch("socket.getaddrinfo", return_value=self._PRIVATE_RESULT):
            with self.assertRaises(ValueError) as ctx:
                google_recorder.validate_url("https://recorder.google.com/abc123")
        self.assertEqual(str(ctx.exception), _INVALID_URL_ERROR)

    def test_passes_when_valid_host_resolves_to_public_ip(self):
        with unittest.mock.patch("socket.getaddrinfo", return_value=self._PUBLIC_RESULT):
            google_recorder.validate_url("https://recorder.google.com/abc123")  # should not raise

    def test_raises_when_hostname_is_unresolvable(self):
        import socket
        with unittest.mock.patch("socket.getaddrinfo", side_effect=socket.gaierror):
            with self.assertRaises(ValueError):
                google_recorder.validate_url("https://recorder.google.com/abc123")


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

    def test_fullwidth_unicode_normalises_to_ascii(self):
        # Fullwidth ASCII chars (e.g. ａｂｃ) NFKC-normalise to their ASCII equivalents
        # and should therefore pass the allowlist.
        result = google_recorder.extract_id("https://recorder.google.com/\uff41\uff42\uff43")
        self.assertEqual(result, "abc")

    def test_non_ascii_id_raises(self):
        with self.assertRaises(ValueError):
            google_recorder.extract_id("https://recorder.google.com/caf\u00e9")


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

    def test_empty_filename_returns_empty_string(self):
        response = self._make_response({"Content-Disposition": 'attachment; filename=""'})
        self.assertEqual(google_recorder._parse_filename(response), "")


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

    def test_raises_when_no_size_headers(self):
        # Code does headers["Content-Length"] (direct access), so missing header → KeyError
        response = self._make_response({})
        with self.assertRaises(KeyError):
            google_recorder._parse_total_size(response)


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

    def test_raises_on_redirect_status_code_when_is_redirect_false(self):
        # Covers the second branch: is_redirect=False but status_code in _REDIRECT_STATUS_CODES
        session = unittest.mock.MagicMock()
        response = unittest.mock.MagicMock()
        response.is_redirect = False
        response.status_code = 301
        session.get.return_value = response
        with self.assertRaises(RuntimeError):
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


class TestFetchChunk(unittest.TestCase):

    _URL = "https://pixelrecorder-pa.googleapis.com/download/playback/abc"

    def _make_response(self, chunks):
        response = unittest.mock.MagicMock()
        response.iter_content.return_value = iter(chunks)
        return response

    def test_raises_when_server_returns_no_data(self):
        response = self._make_response([])
        f = unittest.mock.MagicMock()
        with unittest.mock.patch.object(google_recorder, "_make_streaming_get", return_value=response):
            with self.assertRaises(RuntimeError):
                google_recorder._fetch_chunk(unittest.mock.MagicMock(), self._URL, f, 0, 1000)

    def test_returns_total_bytes_written(self):
        response = self._make_response([b"a" * 100, b"b" * 200])
        f = unittest.mock.MagicMock()
        with unittest.mock.patch.object(google_recorder, "_make_streaming_get", return_value=response):
            result = google_recorder._fetch_chunk(unittest.mock.MagicMock(), self._URL, f, 0, 1000)
        self.assertEqual(result, 300)

    def test_writes_chunks_to_file(self):
        chunks = [b"hello", b"world"]
        response = self._make_response(chunks)
        f = unittest.mock.MagicMock()
        with unittest.mock.patch.object(google_recorder, "_make_streaming_get", return_value=response):
            google_recorder._fetch_chunk(unittest.mock.MagicMock(), self._URL, f, 0, 1000)
        self.assertEqual(f.write.call_count, 2)

    def test_sends_range_header(self):
        response = self._make_response([b"x"])
        f = unittest.mock.MagicMock()
        with unittest.mock.patch.object(google_recorder, "_make_streaming_get", return_value=response) as mock_get:
            google_recorder._fetch_chunk(unittest.mock.MagicMock(), self._URL, f, 500, 1000)
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs.get("headers", {}).get("Range"), "bytes=500-")


_FULL_ENV = {
    "DOWNLOADER_INPUT_URL_BASE":    "https://myservice.com/recordings/",
    "DOWNLOADER_EXPECTED_HOST":     "myservice.com",
    "DOWNLOADER_SCHEME":            "https",
    "DOWNLOADER_DOWNLOAD_URL_BASE": "https://api.myservice.com/download/",
    "DOWNLOADER_FILE_ID_RE":        r"^[a-zA-Z0-9\-]+$",
    "DOWNLOADER_DOWNLOAD_URL_RE":   r"^https://api\.myservice\.com/download/[a-zA-Z0-9\-]+$",
}


class TestDownloaderFromEnv(unittest.TestCase):

    def test_returns_default_when_no_env_vars_set(self):
        with unittest.mock.patch.dict(os.environ, {}, clear=True):
            result = downloader_from_env()
        self.assertIs(result, google_recorder)

    def test_returns_custom_downloader_when_all_vars_set(self):
        with unittest.mock.patch.dict(os.environ, _FULL_ENV, clear=True):
            result = downloader_from_env()
        self.assertIsNot(result, google_recorder)
        self.assertEqual(result.input_url_base, "https://myservice.com/recordings/")

    def test_config_fields_match_env_vars(self):
        with unittest.mock.patch.dict(os.environ, _FULL_ENV, clear=True):
            result = downloader_from_env()
        cfg = result._config
        self.assertEqual(cfg.expected_host, "myservice.com")
        self.assertEqual(cfg.scheme, "https")
        self.assertEqual(cfg.download_url_base, "https://api.myservice.com/download/")

    def test_regex_fields_are_compiled(self):
        with unittest.mock.patch.dict(os.environ, _FULL_ENV, clear=True):
            result = downloader_from_env()
        cfg = result._config
        self.assertIsInstance(cfg.file_id_re, re.Pattern)
        self.assertIsInstance(cfg.download_url_re, re.Pattern)

    def test_max_url_length_default(self):
        with unittest.mock.patch.dict(os.environ, _FULL_ENV, clear=True):
            result = downloader_from_env()
        self.assertEqual(result._config.max_url_length, 2048)

    def test_max_url_length_override(self):
        env = {**_FULL_ENV, "DOWNLOADER_MAX_URL_LENGTH": "1024"}
        with unittest.mock.patch.dict(os.environ, env, clear=True):
            result = downloader_from_env()
        self.assertEqual(result._config.max_url_length, 1024)

    def test_raises_when_some_required_vars_missing(self):
        partial_env = {"DOWNLOADER_INPUT_URL_BASE": "https://myservice.com/recordings/"}
        with unittest.mock.patch.dict(os.environ, partial_env, clear=True):
            with self.assertRaises(ValueError) as ctx:
                downloader_from_env()
        error = str(ctx.exception)
        self.assertIn("DOWNLOADER_INPUT_URL_BASE is set but missing", error)

    def test_raises_on_invalid_file_id_regex(self):
        env = {**_FULL_ENV, "DOWNLOADER_FILE_ID_RE": "[invalid"}
        with unittest.mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(re.error):
                downloader_from_env()

    def test_raises_on_non_numeric_max_url_length(self):
        env = {**_FULL_ENV, "DOWNLOADER_MAX_URL_LENGTH": "not_a_number"}
        with unittest.mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ValueError):
                downloader_from_env()

    def test_error_message_lists_missing_vars(self):
        partial_env = {
            "DOWNLOADER_INPUT_URL_BASE": "https://myservice.com/recordings/",
            "DOWNLOADER_EXPECTED_HOST":  "myservice.com",
        }
        with unittest.mock.patch.dict(os.environ, partial_env, clear=True):
            with self.assertRaises(ValueError) as ctx:
                downloader_from_env()
        error = str(ctx.exception)
        self.assertIn("DOWNLOADER_SCHEME", error)
        self.assertIn("DOWNLOADER_DOWNLOAD_URL_BASE", error)
        self.assertIn("DOWNLOADER_FILE_ID_RE", error)
        self.assertIn("DOWNLOADER_DOWNLOAD_URL_RE", error)
        self.assertNotIn("DOWNLOADER_EXPECTED_HOST", error)


if __name__ == "__main__":
    unittest.main()
