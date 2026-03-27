# Song Hog
Song hog snuffles through recordings to find the bits that matter.
An algorithm to identify and chop songs out from long recordings. Designed to help with extracting and reviewing demos from long recordings of band rehearsals.
The API harness is fairly specifically tailored to my use-case with Ggl recordings, but it could easily be adapted or just run locally.

## How it works
- Convert audio file to a mono 16bit wave and extract the amplitude data.
    - The quality doesn't matter too much as we chop up the original anyway
- Create a spectrogram via a fourier transform, sampling a sensible window
- Get the mean intensities as function of time
- Smooth out the line to your taste
- Find segments of audio above a particular threshold, over a particular amount of time
- Merge segemnets that are really close together
- Chop up the original recording

## API Test Client

`api_test.py` is a CLI tool for hitting the API endpoints from the terminal. It loads credentials from `.env` by default.

```bash
# Health check (no auth)
.venv/Scripts/python api_test.py health

# Process by Google Recorder URL
.venv/Scripts/python api_test.py url --url "https://recorder.google.com/share/..."

# Process by Google Recorder file ID
.venv/Scripts/python api_test.py id --id "abc456"

# Upload a local .m4a file
.venv/Scripts/python api_test.py upload --file media/session.m4a
```

### Global flags

| Flag | Description | Default |
|------|-------------|---------|
| `--api-key` | Override the API key | `SONG_HOG_API_KEY` from `.env` |
| `--host` | Override the base URL | `http://localhost:8000` |

```bash
# Custom key or host (flags go before the subcommand)
.venv/Scripts/python api_test.py --api-key mykey123 id --id "abc456"
.venv/Scripts/python api_test.py --host http://myserver:8000 upload --file media/session.m4a
```
