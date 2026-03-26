"""
file_loader — download audio files from cloud recording services.

Public API
----------
New callers should use the pre-configured ``google_recorder`` Downloader
instance, or construct their own with a custom ``ServiceConfig``:

    from file_loader import google_recorder
    path = google_recorder.download(url, destination)

    from file_loader import Downloader, ServiceConfig
    my_service = Downloader(ServiceConfig(...))

Backward compatibility
----------------------
The module-level names used by existing code are re-exported here unchanged:

    file_loader.google_url_base
    file_loader.download_file(url, destination)
    file_loader.validate_google_recorder_url(url)
    file_loader.extract_file_id(base_url, url)
    file_loader.sanitize_filename(name)
    file_loader._INVALID_URL_ERROR
"""

from file_loader._validation import (
    _INVALID_URL_ERROR,
    extract_file_id,
    sanitize_filename,
)
from file_loader.downloader import (
    GOOGLE_RECORDER,
    Downloader,
    ServiceConfig,
    google_recorder,
)

# Backward-compat scalar
google_url_base: str = GOOGLE_RECORDER.input_url_base


# Backward-compat function wrappers
def validate_google_recorder_url(url: str) -> None:
    google_recorder.validate_url(url)


def download_file(url: str, destination: str) -> str:
    return google_recorder.download(url, destination)


__all__ = [
    # New API
    "ServiceConfig",
    "Downloader",
    "GOOGLE_RECORDER",
    "google_recorder",
    # Backward compat
    "google_url_base",
    "download_file",
    "validate_google_recorder_url",
    "extract_file_id",
    "sanitize_filename",
    "_INVALID_URL_ERROR",
]
