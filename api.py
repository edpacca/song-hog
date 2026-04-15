import json
import logging
import os
import uuid
import matplotlib
matplotlib.use("Agg")  # headless, no display required

from datetime import datetime, timezone
from pathlib import Path
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import file_converter
import plot
import process
from auth import get_api_key
from file_loader import downloader_from_env
from logging_config import configure_logging

configure_logging()
logger = logging.getLogger("song_hog.api")

MEDIA_DIR = Path(os.getenv("MEDIA_DIR", str(Path(__file__).parent / "media")))
QUEUE_DIR = Path(os.getenv("QUEUE_DIR", str(MEDIA_DIR.parent / "queue")))
SAMPLE_RATE = 16000

app = FastAPI(title="Song Hog API")

app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/static/index.html")


# Downloader instance — configure via DOWNLOADER_* env vars to target a different service
_downloader = downloader_from_env()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Unexpected server error: {type(exc).__name__}: {exc}"},
    )


@app.get("/health")
def health():
    _check_media_dir()
    return {"status": "ok", "media_dir": str(MEDIA_DIR), "queue_dir": str(QUEUE_DIR)}


class ProcessResponse(BaseModel):
    file_name: str
    segments: list[tuple[float, float]]
    segment_count: int


class UrlRequest(BaseModel):
    url: str


class IdRequest(BaseModel):
    file_id: str


def _check_media_dir() -> None:
    """Raise 503 if MEDIA_DIR is absent or not writable."""
    if not MEDIA_DIR.is_dir():
        raise HTTPException(status_code=503, detail="Media directory unavailable")
    probe = MEDIA_DIR / f".write_probe_{uuid.uuid4().hex}"
    try:
        probe.touch()
        probe.unlink()
    except OSError as exc:
        raise HTTPException(status_code=503, detail=f"Media directory not writable: {exc}")


def _enqueue(session_name: str, folder_path: Path) -> None:
    pending = QUEUE_DIR / "pending"
    pending.mkdir(parents=True, exist_ok=True)
    job = {
        "id": str(uuid.uuid4()),
        "session_name": session_name,
        "folder_path": str(folder_path),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    job_file = pending / f"{job['id']}.json"
    job_file.write_text(json.dumps(job, indent=2))
    logger.info("Enqueued job %s for session=%s", job["id"], session_name)


def _run_pipeline(m4a_path: Path, session_name: str) -> ProcessResponse:
    logger.info("Pipeline start: session=%s m4a=%s", session_name, m4a_path)
    outdir = MEDIA_DIR / session_name
    try:
        outdir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise HTTPException(status_code=503, detail=f"Cannot create session directory: {exc}")

    try:
        # output_dir is relative to the project root (file_converter prepends __file__.parent)
        wav_path = file_converter.convert_m4a_to_mono_wav(str(m4a_path), session_name, outdir)
        data = file_converter.read_16bit_to_float(str(wav_path))
        analysis = process.analyse(data, SAMPLE_RATE, process.params_from_env())
    except Exception as exc:
        logger.exception("Audio conversion failed: session=%s", session_name)
        raise HTTPException(status_code=500, detail=f"Audio conversion failed: {exc}")

    try:
        plot.plot_data(analysis, data, session_name, str(outdir), export=True, show=False)
        segments = analysis.segments
    except Exception as exc:
        logger.exception("Audio analysis/plotting failed: session=%s", session_name)
        raise HTTPException(status_code=500, detail=f"Audio analysis/plotting failed: {exc}")

    try:
        file_converter.extract_m4a_segments(str(m4a_path), segments, outdir)
    except Exception as exc:
        logger.exception("Segment extraction failed: session=%s", session_name)
        raise HTTPException(status_code=500, detail=f"Audio segment extraction failed: {exc}")

    try:
        _enqueue(session_name, outdir)
    except Exception as exc:
        logger.exception("Enqueue failed: session=%s", session_name)
        raise HTTPException(status_code=500, detail=f"Failed to enqueue job: {exc}")

    logger.info("Pipeline complete: session=%s segments=%d", session_name, len(segments))
    return ProcessResponse(
        file_name=session_name,
        segments=segments,
        segment_count=len(segments),
    )


def _download_and_pipeline(url: str) -> ProcessResponse:
    """Download an M4A from `url` into MEDIA_DIR and run the processing pipeline."""
    _check_media_dir()
    try:
        downloaded = _downloader.download(url, str(MEDIA_DIR))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Download failed: {exc}")

    m4a_path = Path(downloaded)
    session_name = m4a_path.stem.replace(" ", "_")
    return _run_pipeline(m4a_path, session_name)


@app.post("/process/url", response_model=ProcessResponse)
def process_url(body: UrlRequest, _: str = Depends(get_api_key)):
    """Download and process a recording by URL."""
    logger.info("POST /process/url url=%s", body.url)
    return _download_and_pipeline(body.url)


@app.post("/process/id", response_model=ProcessResponse)
def process_id(body: IdRequest, _: str = Depends(get_api_key)):
    """Download and process a recording by file ID."""
    logger.info("POST /process/id file_id=%s", body.file_id)
    url = f"{_downloader.input_url_base}{body.file_id}"
    return _download_and_pipeline(url)


@app.post("/process/upload", response_model=ProcessResponse)
async def process_upload(
    file: UploadFile = File(...),
    _: str = Depends(get_api_key),
):
    """Upload an M4A file directly and process it."""
    logger.info("POST /process/upload filename=%s", file.filename)
    if not file.filename or not file.filename.lower().endswith(".m4a"):
        raise HTTPException(status_code=400, detail="Only .m4a files are accepted")

    _check_media_dir()
    stem = Path(file.filename).stem.replace(" ", "_")
    m4a_path = MEDIA_DIR / f"{stem}_{uuid.uuid4().hex[:8]}.m4a"

    try:
        content = await file.read()
        m4a_path.write_bytes(content)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {exc}")

    return _run_pipeline(m4a_path, stem)
