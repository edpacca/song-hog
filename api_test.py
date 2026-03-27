#!/usr/bin/env python3
"""CLI tool for testing the song-hog API endpoints."""

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()


def print_response(resp: requests.Response) -> None:
    print(f"Status: {resp.status_code}")
    try:
        print(json.dumps(resp.json(), indent=2))
    except Exception:
        print(resp.text)


def cmd_health(args: argparse.Namespace) -> int:
    resp = requests.get(f"{args.host}/health")
    print_response(resp)
    return 0 if resp.ok else 1


def cmd_url(args: argparse.Namespace) -> int:
    resp = requests.post(
        f"{args.host}/process/url",
        json={"url": args.url},
        headers={"X-API-Key": args.api_key},
    )
    print_response(resp)
    return 0 if resp.ok else 1


def cmd_id(args: argparse.Namespace) -> int:
    resp = requests.post(
        f"{args.host}/process/id",
        json={"file_id": args.id},
        headers={"X-API-Key": args.api_key},
    )
    print_response(resp)
    return 0 if resp.ok else 1


def cmd_upload(args: argparse.Namespace) -> int:
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        return 1
    with open(file_path, "rb") as f:
        resp = requests.post(
            f"{args.host}/process/upload",
            files={"file": (file_path.name, f, "audio/mp4")},
            headers={"X-API-Key": args.api_key},
        )
    print_response(resp)
    return 0 if resp.ok else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="song-hog API test client")
    parser.add_argument(
        "--host",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("SONG_HOG_API_KEY"),
        help="API key (default: SONG_HOG_API_KEY from .env)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("health", help="GET /health")

    url_parser = subparsers.add_parser("url", help="POST /process/url")
    url_parser.add_argument("--url", required=True, help="Google Recorder URL")

    id_parser = subparsers.add_parser("id", help="POST /process/id")
    id_parser.add_argument("--id", required=True, help="Google Recorder file ID")

    upload_parser = subparsers.add_parser("upload", help="POST /process/upload")
    upload_parser.add_argument("--file", required=True, help="Path to .m4a file")

    args = parser.parse_args()

    commands = {
        "health": cmd_health,
        "url": cmd_url,
        "id": cmd_id,
        "upload": cmd_upload,
    }

    sys.exit(commands[args.command](args))


if __name__ == "__main__":
    main()
