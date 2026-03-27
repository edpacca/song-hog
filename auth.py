import os
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_api_key(api_key: str = Security(_API_KEY_HEADER)) -> str:
    expected = os.getenv("SONG_HOG_API_KEY")
    if not expected:
        raise RuntimeError("SONG_HOG_API_KEY environment variable is not set")
    if not api_key or api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key
