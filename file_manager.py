import requests
import ffmpeg
from pathlib import Path

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
    response = session.get(download_url, stream=True)

    response.raise_for_status()
    cd = response.headers.get("Content-Disposition", "")
    print(cd)
    file_name = cd.split("filename=")[1].replace("\"", "")
    destination_path = f"{destination}/{file_name}"
    with open(destination_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=32768):
            f.write(chunk)

    print(f"saved to {destination_path}")

def convert_mp4_to_wav(mp4_path, file_name, output_dir):
    input_path = Path(__file__).parent / mp4_path
    output_path = Path(__file__).parent / output_dir / f"{file_name}.wav"
    print(input_path)
    ffmpeg.input(str(input_path)).output(str(output_path), ac=1, ar=16000).run()

def main():
    pass

if __name__ == "__main__":
    main()
