# AGENTS.md

## Critical: Python path

On Linux, use `.venv/bin/python`. CLAUDE.md incorrectly documents `.venv/Scripts/python` (that's Windows only).

```bash
.venv/bin/python -m unittest discover -s tests -v       # all tests
.venv/bin/python -m unittest tests.test_validation -v   # single file
.venv/bin/python -m unittest tests.test_validation.TestExtractFileId.test_extracts_id  # single case
```

## Tests

- Framework is `unittest`, not pytest — no `pytest` command, no `conftest.py`
- Test files live in `tests/` only (not root), named `test_*.py`
- `benchmark.py` / `benchmark_runner.py` exist at root — these are not unit tests

## Toolchain

- Package manager: `uv`. Run `uv sync` to install deps.
- Typecheck config: `pyproject.toml` uses pyright (`tool.pyright`). No mypy.
- Formatter: `black` is a dependency but no config beyond that.

## Architecture gotcha: file deletion side effects

`file_converter.py` deletes files as part of normal operation:
- WAV deleted after analysis
- Segment M4As deleted after MP3 conversion
- Original M4A deleted after all segments extracted

Do not add retry/idempotent logic assuming files persist across pipeline stages.

## API

- All endpoints require `X-API-Key` header (`SONG_HOG_API_KEY` env var)
- Jobs are enqueued as JSON files in `queue/pending/` — no in-process async worker
- `api_test.py` is a manual CLI test client, not an automated test

## Environment variables (`.env`)

Required: `SONG_HOG_API_KEY`, `MEDIA_DIR`, `QUEUE_DIR`  
Optional: `LOG_LEVEL`, `LOG_FILE`, `UVICORN_ACCESS_LOG_LEVEL`
