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

        download_url = f"{self._config.download_url_base}{file_id}"

        # Assert the constructed URL matches the expected shape before making any request
        if not self._config.download_url_re.match(download_url):
            raise ValueError(_validation._INVALID_URL_ERROR)

        print(f"file id: {file_id}")

        # Redirects disabled — we only connect to the URL we explicitly constructed
        session = requests.Session()
        response = session.get(
            download_url,
            stream=True,
            timeout=(10, 60),
            allow_redirects=False,
        )
        if response.is_redirect or response.status_code in (301, 302, 303, 307, 308):
            raise RuntimeError("Unexpected redirect from download server")
        response.raise_for_status()

        cd = response.headers.get("Content-Disposition", "")
        if "filename=" not in cd:
            raise RuntimeError("Server response missing Content-Disposition filename")
        raw_name = cd.split("filename=")[1].strip().strip('"')
        file_name = _validation.sanitize_filename(raw_name)
        destination_path = f"{destination}/{file_name}"

        content_range = response.headers.get("Content-Range", "")
        total_size = (
            int(content_range.split("/")[1])
            if "/" in content_range
            else int(response.headers["Content-Length"])
        )

        print(f"Total size: {total_size / 1024 / 1024:.1f} MB")

        expected_size = int(response.headers.get("Content-Length", 0))
        received = 0

        with open(destination_path, "wb") as f:
            while received < total_size:
                print(f"Fetching bytes {received}-{total_size - 1} ({received / total_size:.1%} done)...")
                response = session.get(
                    download_url,
                    headers={"Range": f"bytes={received}-"},
                    stream=True,
                    timeout=(10, 60),
                    allow_redirects=False,
                )
                if response.is_redirect or response.status_code in (301, 302, 303, 307, 308):
                    raise RuntimeError("Unexpected redirect during chunked download")
                response.raise_for_status()

                chunk_received = 0
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        received += len(chunk)
                        chunk_received += len(chunk)

                if chunk_received == 0:
                    raise RuntimeError(f"Server returned no data at offset {received}")

        actual_size = os.path.getsize(destination_path)
        if expected_size and actual_size < expected_size:
            raise RuntimeError(
                f"Incomplete download: got {actual_size} of {expected_size} bytes "
                f"({actual_size / expected_size:.1%})"
            )

        print(f"Saved to {destination_path} ({actual_size / 1024 / 1024:.1f} MB)")
        return destination_path


# Pre-built instance for convenience and backward compatibility.
google_recorder = Downloader(GOOGLE_RECORDER)
