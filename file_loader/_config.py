import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceConfig:
    """
    All service-specific constants needed to validate and download files.
    Frozen so instances behave as value objects and cannot be mutated.
    """
    input_url_base: str          # URL base shown to the user, e.g. "https://recorder.google.com/"
    expected_host: str           # host allowlist for input URLs, e.g. "recorder.google.com"
    scheme: str                  # scheme allowlist, e.g. "https"
    download_url_base: str       # base for the constructed download URL
    file_id_re: re.Pattern[str]  # strict character allowlist for extracted IDs
    download_url_re: re.Pattern[str]  # expected shape of the full constructed download URL
    max_url_length: int = 2048
