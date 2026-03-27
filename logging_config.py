import logging
import logging.handlers
import os
import sys


def configure_logging() -> None:
    """Configure application logging from environment variables.

    Environment variables:
        LOG_LEVEL: App log level (default INFO). Set DEBUG for verbose output.
        LOG_FILE: Optional path to a rotating log file. If unset, stdout only.
        UVICORN_ACCESS_LOG_LEVEL: Uvicorn access log level (default INFO).
            Set WARNING to silence access logs when behind a reverse proxy.
    """
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_file = os.getenv("LOG_FILE")

    fmt = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt=datefmt)

    handlers: list[logging.Handler] = []

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    handlers.append(stdout_handler)

    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    app_logger = logging.getLogger("song_hog")
    app_logger.setLevel(log_level)
    for h in handlers:
        app_logger.addHandler(h)

    access_level = os.getenv("UVICORN_ACCESS_LOG_LEVEL", "INFO").upper()
    logging.getLogger("uvicorn.access").setLevel(access_level)
