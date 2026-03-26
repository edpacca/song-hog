import os
import re
from dataclasses import dataclass

import requests

from file_loader import _validation


@dataclass(frozen=True)
class ServiceConfig:
    """
    All service-specific constants needed to validate and download files.
    Frozen so instances behave as value objects and cannot be mutated.
    """
    input_url_base: str        # URL base shown to the user, e.g. "https://recorder.google.com/"
    expected_host: str         # host allowlist for input URLs, e.g. "recorder.google.com"
    scheme: str                # scheme allowlist, e.g. "https"
    download_url_base: str     # base for the constructed download URL
    file_id_re: re.Pattern     # strict character allowlist for extracted IDs
    download_url_re: re.Pattern  # expected shape of the full constructed download URL
    max_url_length: int = 2048


# Pre-configured instance for Google Recorder.
GOOGLE_RECORDER = ServiceConfig(
    input_url_base="https://recorder.google.com/",
    expected_host="recorder.google.com",
    scheme="https",
    download_url_base="https://pixelrecorder-pa.googleapis.com/download/playback/",
    file_id_re=re.compile(r"^[a-zA-Z0-9\-]+$"),
    download_url_re=re.compile(
        r"^https://pixelrecorder-pa\.googleapis\.com/download/playback/[a-zA-Z0-9\-]+$"
    ),
)

_REDIRECT_STATUS_CODES = (301, 302, 303, 307, 308)


class Downloader:
    """
    Generic resumable-download client configured for a specific service.

    Usage:
        google_recorder = Downloader(GOOGLE_RECORDER)
        path = google_recorder.download("https://recorder.google.com/<id>", "/tmp")
    """

    def __init__(self, config: ServiceConfig) -> None:
        self._config = config

    def validate_url(self, url: str) -> None:
        """Validate url against this service's rules. Raises ValueError on failure."""
        _validation.validate_url(self._config, url)

    def extract_id(self, url: str) -> str:
        """Extract and allowlist-validate the file ID from a service URL."""
        return _validation.extract_file_id(
            self._config.input_url_base,
            url,
            file_id_re=self._config.file_id_re,
        )

    def download(self, url: str, destination: str) -> str:
        """
        Download the file at url into the destination directory.
        Returns the full path of the saved file.
        Raises ValueError for invalid URLs, RuntimeError for download failures.
        """
        self.validate_url(url)
        file_id = self.extract_id(url)
        print(f"file id: {file_id}")

        download_url = self._build_download_url(file_id)

        session = requests.Session()
        # Redirects disabled — we only connect to the URL we explicitly constructed
        with self._make_streaming_get(session, download_url) as initial_response:
            file_name = self._parse_filename(initial_response)
            destination_path = f"{destination}/{file_name}"
            total_size = self._parse_total_size(initial_response)
            expected_size = int(initial_response.headers.get("Content-Length", 0))

        print(f"Total size: {total_size / 1024 / 1024:.1f} MB")

        self._stream_to_file(session, download_url, destination_path, total_size)
        self._verify_download(destination_path, expected_size)

        actual_size = os.path.getsize(destination_path)
        print(f"Saved to {destination_path} ({actual_size / 1024 / 1024:.1f} MB)")
        return destination_path

    # -- Private helpers ------------------------------------------------------

    def _build_download_url(self, file_id: str) -> str:
        """Construct the download URL and assert it matches the expected shape."""
        download_url = f"{self._config.download_url_base}{file_id}"
        if not self._config.download_url_re.match(download_url):
            raise ValueError(_validation._INVALID_URL_ERROR)
        return download_url

    def _make_streaming_get(
        self,
        session: requests.Session,
        url: str,
        headers: dict | None = None,
    ) -> requests.Response:
        """
        Issue a streaming GET with redirects disabled.
        Raises RuntimeError on any redirect, raises on non-2xx status.
        """
        response = session.get(
            url,
            headers=headers or {},
            stream=True,
            timeout=(10, 60),
            allow_redirects=False,
        )
        if response.is_redirect or response.status_code in _REDIRECT_STATUS_CODES:
            raise RuntimeError("Unexpected redirect from download server")
        response.raise_for_status()
        return response

    def _parse_filename(self, response: requests.Response) -> str:
        """Extract and sanitise the filename from the Content-Disposition header."""
        cd = response.headers.get("Content-Disposition", "")
        if "filename=" not in cd:
            raise RuntimeError("Server response missing Content-Disposition filename")
        raw_name = cd.split("filename=")[1].strip().strip('"')
        return _validation.sanitize_filename(raw_name)

    def _parse_total_size(self, response: requests.Response) -> int:
        """
        Resolve the total file size from the response headers.
        Prefers Content-Range (partial responses) over Content-Length.
        """
        content_range = response.headers.get("Content-Range", "")
        if "/" in content_range:
            return int(content_range.split("/")[1])
        return int(response.headers["Content-Length"])

    def _fetch_chunk(
        self,
        session: requests.Session,
        download_url: str,
        f,
        received: int,
        total_size: int,
    ) -> int:
        """
        Request bytes from `received` onwards, write each chunk to `f`.
        Returns the number of bytes written in this fetch.
        Raises RuntimeError if the server returns no data.
        """
        print(f"Fetching bytes {received}-{total_size - 1} ({received / total_size:.1%} done)...")
        response = self._make_streaming_get(
            session,
            download_url,
            headers={"Range": f"bytes={received}-"},
        )

        chunk_received = 0
        with response:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    chunk_received += len(chunk)

        if chunk_received == 0:
            raise RuntimeError(f"Server returned no data at offset {received}")

        return chunk_received

    def _stream_to_file(
        self,
        session: requests.Session,
        download_url: str,
        destination_path: str,
        total_size: int,
    ) -> None:
        """Drive the resumable download loop, writing all chunks to destination_path."""
        received = 0
        with open(destination_path, "wb") as f:
            while received < total_size:
                received += self._fetch_chunk(session, download_url, f, received, total_size)

    def _verify_download(self, destination_path: str, expected_size: int) -> None:
        """Raise RuntimeError if the saved file is smaller than expected_size."""
        if not expected_size:
            return
        actual_size = os.path.getsize(destination_path)
        if actual_size < expected_size:
            raise RuntimeError(
                f"Incomplete download: got {actual_size} of {expected_size} bytes "
                f"({actual_size / expected_size:.1%})"
            )


# Pre-built instance for convenience and backward compatibility.
google_recorder = Downloader(GOOGLE_RECORDER)
