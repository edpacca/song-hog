# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Song Hog identifies and extracts song segments from long audio recordings, primarily designed for extracting tracks from band rehearsal recordings. It analyses audio to detect segments above a threshold, then extracts and converts them to MP3s.

## Technology Stack

- **Language**: Python 3.14
- **Package Manager**: `uv` (modern Python package manager)
- **API Framework**: FastAPI + uvicorn
- **Audio Processing**: NumPy, Matplotlib, ffmpeg-python
- **Testing**: `unittest` (not pytest)

## Common Commands

### Dependencies
```bash
uv sync  # Install dependencies from uv.lock
```

### Testing
```bash
# Run all tests
.venv/Scripts/python -m unittest discover -s tests -v

# Run tests from a single file
.venv/Scripts/python -m unittest tests.test_validation -v

# Run a single test case
.venv/Scripts/python -m unittest tests.test_validation.TestExtractFileId.test_extracts_id
```

### Running the API
```bash
# Development mode (with auto-reload)
uvicorn api:app --reload

# Production mode
uvicorn api:app --host 0.0.0.0 --port 8000
```

### Running the CLI
```bash
# Execute main.py test functions (commented out by default)
.venv/Scripts/python main.py
```

## Architecture & Key Modules

### Core Processing Pipeline
The pipeline transforms audio files through these stages:

1. **File Input** (`file_converter.py`, `file_loader/`)
   - Download audio from Google Recorder or accept uploads
   - Convert M4A to mono 16-bit WAV at 16kHz sample rate
   - Read and normalize WAV data to floats

2. **Audio Analysis** (`process.py`)
   - **Spectrogram**: Compute STFT with configurable window (default 400)
   - **Intensity Detection**: Extract mean intensity across frequencies, convert to dB
   - **Smoothing**: Apply moving average with window size (AnalysisParams.window)
   - **Segmentation**: Find continuous regions above threshold, filter by min_duration, merge nearby segments (min_gap), optionally pad

3. **Visualization** (`plot.py`)
   - Plot spectrogram, intensity curve, smoothed signal, detected segments
   - Export as PNG

4. **Segment Extraction** (`file_converter.py`)
   - Delete the WAV file after analysis and plotting are complete
   - Extract M4A segments at detected time boundaries
   - Convert each segment M4A to MP3, deleting the intermediate M4A
   - Delete the original M4A after all segments are extracted

### API Endpoints (`api.py`)
- `POST /process/url` - Download from Google Recorder URL and process
- `POST /process/id` - Download using Google Recorder file ID and process
- `POST /process/upload` - Upload M4A file directly and process
- `GET /health` - Health check (verifies media directory)

All endpoints require `X-API-Key` header (checked against `SONG_HOG_API_KEY` env var).

### Key Data Structures

**AnalysisParams** (process.py)
- `window: int` - Smoothing window size (default 400)
- `threshold: float` - dB threshold for segment detection (default 35)
- `min_duration: float` - Minimum segment length in seconds (default 40)
- `min_gap: float` - Merge segments closer than this many seconds (default 20)
- `padding: float` - Add padding before/after segments in seconds (default 5)

**AudioAnalysis** (process.py)
- Contains spectrogram, frequencies, time array, intensity, smoothed signal
- `segments: List[Tuple[float, float]]` - Detected segment boundaries (start, end) in seconds

### File Organization

```
song-hog/
├── main.py                  # CLI interface with test functions
├── api.py                   # FastAPI REST API
├── api_test.py              # CLI client for manually testing API endpoints
├── process.py               # Core audio analysis (spectrogram, detection, smoothing, merging)
├── plot.py                  # Plotting and visualization
├── file_converter.py        # Audio conversion (M4A↔WAV↔MP3), segment extraction, cleanup
├── auth.py                  # API key authentication
├── colors.py                # Color utilities for plotting
├── logging_config.py        # Logging setup (level, file rotation, uvicorn access log)
├── Dockerfile               # Container image definition
├── file_loader/             # Module for downloading files
│   ├── downloader.py        # HTTP download logic
│   ├── _validation.py       # URL validation, filename sanitization, IP allowlist
│   ├── _config.py           # ServiceConfig dataclass (URL bases, regex patterns)
│   └── __init__.py
├── static/
│   └── index.html           # Web UI served at /
├── tests/                   # Unit tests
│   ├── test_validation.py   # File ID extraction, URL validation, filename sanitization
│   ├── test_downloader.py   # Download logic, HTTP handling
│   ├── test_process.py      # Audio analysis and segmentation logic
│   └── test_api.py          # API endpoint integration tests
├── media/                   # Input audio files (git-ignored)
├── queue/                   # Job queue for async processing
└── pyproject.toml           # Project metadata
```

## Important Notes

### Always use `.venv/Scripts/python`
All Python commands must use the venv interpreter to access project dependencies. System Python will not have required packages installed.

### Tests use unittest, not pytest
The project uses Python's built-in `unittest` framework. No pytest configuration exists.

### Environment Variables
Required for API operation (set in `.env`):
- `SONG_HOG_API_KEY` - API authentication key
- `MEDIA_DIR` - Directory for media files (default: `media/`)
- `QUEUE_DIR` - Directory for job queue (default: `queue/`)

Optional:
- `DOWNLOAD_LINK` - Base URL for downloads in main.py tests
- `TEST_FILE_NAME` - Test file name in main.py tests
- `LOG_LEVEL` - App log level (default: `INFO`; set `DEBUG` for verbose output)
- `LOG_FILE` - Path to a rotating log file; if unset, stdout only
- `UVICORN_ACCESS_LOG_LEVEL` - Uvicorn access log level (default: `INFO`; set `WARNING` to silence when behind a reverse proxy)

### Queuing System
The API enqueues processed jobs as JSON files in `queue/pending/` for async handling by external workers.

### Configuration Patterns
Analysis parameters are configurable via `AnalysisParams` dataclass. Different parameter sets produce different segmentation results. The `main.py` contains experimental functions for comparing parameter effects.

