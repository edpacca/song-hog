# User Flow

## Ingestion
- User sends a Google recording link to an endpoint
- **Authorization:** User connects directly to the self-hosted server via Tailscale VPN
  - *Other options to explore:* proxy service with VPN access, API key + HTTPS, OAuth token exchange

## Download/Upload Service — Receive Link
- Downloads audio from Google Recorder
- Extracts filename (optionally parses a `bandname` keyword from it)
- Forwards file to Audio File Service

## Audio File Service — Receive M4A
- Converts M4A → WAV
- Saves WAV file
- Calls Audio Processing Service

## Audio Processing Service — Receive WAV
- Decodes WAV
- Transforms data & applies detection algorithm
- Extracts song regions
- Returns regions to Audio File Service
- Also sends visual plot to the download/upload service

## Audio File Service — Receive Regions
- Splits WAV into individual files per region
- Converts each to MP3
- Validates MP3s *(method TBD)*
- Sends MP3s to Download/Upload Service

## Download/Upload Service — Receive MP3s
- Uses `bandname` keyword to determine target folder
- Renames MP3 files
- Uploads to shared OneDrive folder under correct project (or fallback name)
- Moves originals to archive area *(auto-cleared every 24h)*

