import functools
import logging
import os
import threading
import time
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger("song_hog.benchmark")

def _is_enabled() -> bool:
    return os.getenv("BENCHMARK") == "1"

def _read_rss_kb() -> int:
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    return 0


class _MemoryPoller:
    def __init__(self, interval: float = 0.05):
        self.interval = interval
        self.peak_kb = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._poll, daemon=True)

    def start(self) -> "_MemoryPoller":
        self.peak_kb = _read_rss_kb()
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._thread.join()

    def _poll(self) -> None:
        while not self._stop.wait(self.interval):
            rss = _read_rss_kb()
            if rss > self.peak_kb:
                self.peak_kb = rss


def measure(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not _is_enabled():
            return func(*args, **kwargs)
        rss_before = _read_rss_kb()
        poller = _MemoryPoller()
        poller.start()
        t0 = time.perf_counter()
        try:
            result = func(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - t0
            poller.stop()
            rss_after = _read_rss_kb()

        peak_mb = poller.peak_kb / 1024
        before_mb = rss_before / 1024
        after_mb = rss_after / 1024
        delta_mb = after_mb - before_mb
        GREEN, RESET = "\033[92m", "\033[0m"
        logger.info(
            f"{GREEN}[benchmark] %s: time=%.2fs  peak=%.0fMB  before=%.0fMB  after=%.0fMB  delta=%+.0fMB{RESET}",
            func.__name__, elapsed, peak_mb, before_mb, after_mb, delta_mb,
        )
        return result

    return wrapper
