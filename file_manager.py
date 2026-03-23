import requests
import os

google_url_base = "https://recorder.google.com/"
download_url_base = "https://pixelrecorder-pa.googleapis.com/download/playback/"

def extract_file_id(base_url: str, url: str):
    try:
        url_tail = url.split(google_url_base)[1]
        file_id = url_tail.split("?")[0]
        return file_id
    except Exception:
        print("unable to get file id")

def download_file(url: str, destination: str):
    file_id = extract_file_id(google_url_base, url)
    print(f"file id: {file_id}")
    download_url = f"{download_url_base}{file_id}"

    session = requests.Session()
    response = session.get(
        download_url,
        stream=True,
        timeout=(10, 60)
    )

    response.raise_for_status()
    cd = response.headers.get("Content-Disposition", "")
    file_name = cd.split("filename=")[1].replace("\"", "")
    destination_path = f"{destination}/{file_name}"

    content_range = response.headers.get("Content-Range", "")
    total_size = (
        int(content_range.split("/")[1])
        if "/" in content_range
        else int(response.headers["Content-Length"])
    )

    print(total_size)

    expected_size = int(response.headers.get("Content-Length", 0))
    received = 0

    with open(destination_path, "wb") as f:
        while received < total_size:
            print(f"Fetching bytes {received}-{total_size - 1} ({received / total_size:.1%} done)...")
            response = session.get(
                download_url,
                headers={"Range": f"bytes={received}-"},
                stream=True,
                timeout=(10, 60),
            )
            response.raise_for_status()

            chunk_received = 0
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    received += len(chunk)
                    chunk_received += len(chunk)

            if chunk_received == 0:
                raise RuntimeError(f"Server returned no data at offset {received}")

    actual_size = os.path.getsize(destination_path)
    if expected_size and actual_size < expected_size:
        raise RuntimeError(
            f"Incomplete download: got {actual_size} of {expected_size} bytes "
            f"({actual_size / expected_size:.1%})"
        )

    print(f"Saved to {destination_path} ({actual_size / 1024 / 1024:.1f} MB)")
    return destination_path

def main():
    pass

if __name__ == "__main__":
    main()
