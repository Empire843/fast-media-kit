# Quick Media Tools

Personal web app for fast creator utilities.

Current tools:

- Download video from Facebook, TikTok, YouTube, and other `yt-dlp` supported URLs
- Translate selected sheets in `.xlsx` workbooks while preserving workbook structure
- Remove background from multiple images in batch with real-time progress stream (SSE)

## Run Locally

```powershell
cd D:\tool\master_video\quick-media-tools
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Optional `.env` for default translation settings:

```powershell
Copy-Item .env.example .env
```

Then edit `.env`:

```text
AISHOP24H_API_KEY=your_key_here
AISHOP24H_MODEL=google/gemini-3-pro-preview
AISHOP24H_BASE_URL=https://aishop24h.com/v1

# Maximum threads/images processed in parallel for background removal (default: 3)
# Set to 1 on Render Free (512 MB RAM) to avoid memory overload (OOM)
MAX_BG_WORKERS=3
```

Open:

```text
http://localhost:8000
```

## Deploy

This project is designed for Docker/VPS, Render, Railway, Fly.io, or Google Cloud Run.

For a personal deployment, add a simple auth layer before exposing it publicly. The app writes generated files to `storage/`.

## Notes

- Install `ffmpeg` on the server for best video quality and audio/video merging. On local Windows, the app can also use a portable build at `vendor/ffmpeg-download/<build>/bin`.
- Use `cookies.txt` only for content you can access and are allowed to download.
- XLSX translation defaults to AIShop24H (`https://aishop24h.com/v1`) with `google/gemini-2.5-pro`, and can use a per-request API key/model, or server defaults from `AISHOP24H_API_KEY` and `AISHOP24H_MODEL`. Generic fallbacks are `TRANSLATION_API_KEY` and `TRANSLATION_MODEL`.
- **Background Removal Memory Optimization**: The background removal tool utilizes `rembg` (ONNX Runtime). Because machine learning models are heavy on RAM, it is highly recommended to configure `MAX_BG_WORKERS` appropriately. On Render Free (512 MB RAM limit), set `MAX_BG_WORKERS=1` in your environment variables to process images sequentially. The frontend will still display real-time stream updates smoothly as each image finishes.

