import json
import os
import re
import uuid
import matplotlib
matplotlib.use("Agg")  # headless, no display required

import numpy as np
from datetime import datetime, timezone
from pathlib import Path
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

import file_converter
import file_loader
import plot
from auth import get_api_key

MEDIA_DIR = Path(os.getenv("MEDIA_DIR", str(Path(__file__).parent / "media")))
QUEUE_DIR = Path(os.getenv("QUEUE_DIR", str(MEDIA_DIR.parent / "queue")))
SAMPLE_RATE = 16000

app = FastAPI(title="Song Hog API")


@app.get("/health")
def health():
    if not MEDIA_DIR.exists():
        raise HTTPException(status_code=503, detail="Media directory unavailable")
    return {"status": "ok", "media_dir": str(MEDIA_DIR), "queue_dir": str(QUEUE_DIR)}


class ProcessResponse(BaseModel):
    file_name: str
    segments: list[tuple[float, float]]
    segment_count: int


class UrlRequest(BaseModel):
    url: str


class IdRequest(BaseModel):
    file_id: str


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


def _run_pipeline(m4a_path: Path, session_name: str) -> ProcessResponse:
    outdir = MEDIA_DIR / session_name
    outdir.mkdir(parents=True, exist_ok=True)

    # output_dir is relative to the project root (file_converter prepends __file__.parent)
    file_converter.convert_m4a_to_mono_wav(str(m4a_path), session_name, f"media/{session_name}")
    wav_path = outdir / f"{session_name}.wav"

    data = file_converter.read_16bit_to_float(str(wav_path))
    segments = plot.plot_data(data, SAMPLE_RATE, session_name, str(outdir))

    _enqueue(session_name, outdir)

    return ProcessResponse(
        file_name=session_name,
        segments=segments,
        segment_count=len(segments),
    )


@app.post("/process/url", response_model=ProcessResponse)
def process_url(body: UrlRequest, _: str = Depends(get_api_key)):
    """Download and process a recording by Google Recorder URL."""
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        downloaded = file_loader.download_file(body.url, str(MEDIA_DIR))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Download failed: {exc}")

    m4a_path = Path(downloaded)
    session_name = m4a_path.stem.replace(" ", "_")
    return _run_pipeline(m4a_path, session_name)


@app.post("/process/id", response_model=ProcessResponse)
def process_id(body: IdRequest, _: str = Depends(get_api_key)):
    """Download and process a recording by Google Recorder file ID."""
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    google_url = f"{file_loader.google_url_base}{body.file_id}"
    try:
        downloaded = file_loader.download_file(google_url, str(MEDIA_DIR))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Download failed: {exc}")

    m4a_path = Path(downloaded)
    session_name = m4a_path.stem.replace(" ", "_")
    return _run_pipeline(m4a_path, session_name)


@app.post("/process/upload", response_model=ProcessResponse)
async def process_upload(
    file: UploadFile = File(...),
    _: str = Depends(get_api_key),
):
    """Upload an M4A file directly and process it."""
    if not file.filename or not file.filename.lower().endswith(".m4a"):
        raise HTTPException(status_code=400, detail="Only .m4a files are accepted")

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    stem = Path(file.filename).stem.replace(" ", "_")
    m4a_path = MEDIA_DIR / f"{stem}_{uuid.uuid4().hex[:8]}.m4a"

    content = await file.read()
    m4a_path.write_bytes(content)

    return _run_pipeline(m4a_path, stem)
