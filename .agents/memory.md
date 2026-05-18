# Fast Media Kit Agent Memory

## Project Purpose

This repo is a small personal FastAPI web app named **Quick Media Tools**. It provides creator utilities through a single dashboard UI:

- Download videos from URLs supported by `yt-dlp`.
- List available `yt-dlp` formats for a video URL.
- Translate selected sheets in `.xlsx` workbooks while preserving workbook structure.
- Remove image backgrounds with `rembg`; backend route exists, but the current sidebar marks the UI item as upcoming.

The app is not a public SaaS product. Keep changes pragmatic, local, and oriented around personal/VPS deployment.

## Runtime Stack

- Python 3.11 in Docker.
- FastAPI + Jinja2 templates for server-rendered HTML.
- Plain CSS and vanilla JavaScript in `app/static`.
- `yt-dlp` for video downloads.
- `openpyxl` for workbook parsing/saving.
- OpenAI-compatible chat completions, Gemini REST, or AIShop24H for translation.
- `rembg`, Pillow, and ONNX Runtime for background removal.

Run locally:

```bash
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Docker:

```bash
docker build -t quick-media-tools .
docker run -p 8000:8000 quick-media-tools
```

## Important Paths

- `app/main.py`: FastAPI app, routes, template context, file download guard.
- `app/settings.py`: env loading, base paths, storage paths, default translation provider/model/base URL/API keys.
- `app/constants.py`: provider labels, language list, default models, batching defaults.
- `app/tools/downloader.py`: `yt-dlp` command construction, ffmpeg detection, format listing, output recovery.
- `app/tools/xlsx_translator.py`: workbook sheet listing, text-cell filtering, batching, provider calls, JSON parsing.
- `app/tools/background.py`: cached `rembg` sessions and PNG output generation.
- `app/templates/index.html`: dashboard UI for download and XLSX translation.
- `app/templates/partials/*.html`: partial snippets returned by async tool routes.
- `app/static/app.js`: navigation, async forms, drag/drop, sheet loader, provider default switching.
- `app/static/styles.css`: full UI styling.
- `storage/downloads/`: generated video files, ignored except `.gitkeep`.
- `storage/processed/`: generated XLSX/images/ZIP files, ignored except `.gitkeep`.

## Environment And Defaults

`app/settings.py` manually loads `.env` from repo root without overriding existing environment variables.

Translation env vars:

- `TRANSLATION_PROVIDER`, default `aishop24h`.
- `TRANSLATION_MODEL`; fallback `AISHOP24H_MODEL`; final default `google/gemini-2.5-pro`.
- `TRANSLATION_BASE_URL`; fallback `AISHOP24H_BASE_URL`; final default `https://aishop24h.com/v1`.
- `TRANSLATION_API_KEY`, generic override used before provider-specific keys.
- `AISHOP24H_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`.

The README and `.env.example` mention `google/gemini-3-pro-preview`; code defaults are split between `settings.py`, `constants.py`, and `app.js`. Keep these in sync when changing defaults.

## Route Map

Main pages:

- `GET /`: renders dashboard with active `download`.
- `GET /download`: renders dashboard with active `download`.
- `GET /translate`: renders dashboard with active `translate`.
- `GET /{tool}` only accepts `download` and `translate`.

Tool routes returning HTML partials:

- `POST /tools/download-video`: accepts URL/platform/quality/custom format/cookies/redownload, returns `download_result.html` or `error.html`.
- `POST /tools/list-formats`: accepts URL/cookies, returns `formats_result.html` or `error.html`.
- `POST /tools/remove-background`: accepts uploaded images/model/alpha matting, returns `background_result.html` or `error.html`.
- `POST /tools/xlsx-sheets`: accepts workbook upload, returns checkboxes in `xlsx_sheets.html`.
- `POST /tools/translate-xlsx`: accepts workbook, selected sheets, language, provider, model, API key, base URL, worker and batch settings.
- `GET /files/{kind}/{job_id}/{filename}`: downloads generated files from `storage/downloads` or `storage/processed`.

File serving uses `safe_file_response()` with `Path.resolve()` and `relative_to()` to block path traversal. Preserve this pattern.

## UI Flow

The frontend is intentionally simple:

- Sidebar buttons with `data-tool` toggle `.workspace.active`; no full page navigation after initial render.
- Forms marked `data-async-form` are intercepted by `app/static/app.js` and posted with `fetch()`.
- The server returns HTML partials, and JS injects them into the configured target.
- XLSX upload uses `data-sheet-loader` to call `/tools/xlsx-sheets` immediately after file selection.
- Drag/drop file UI stores selected file names in `.drop-zone-file`.

When adding new tools, follow this pattern:

1. Add backend route in `app/main.py`.
2. Add tool logic under `app/tools/`.
3. Add a workspace section to `app/templates/index.html`.
4. Add a sidebar button with `data-tool`.
5. Return a partial under `app/templates/partials/`.

## Downloader Details

`download_video()`:

- Creates a random `job_id` and writes to `storage/downloads/{job_id}`.
- Uses `yt-dlp` CLI when available, otherwise `python -m yt_dlp`.
- Disables proxy env vars in `clean_network_env()`.
- Uses portable Windows ffmpeg from `vendor/ffmpeg-download/.../bin` if system ffmpeg is missing.
- Uses combined best video/audio format when ffmpeg is present; falls back to single-file `b` when not.
- Supports cookies by writing uploaded bytes to a temporary `cookies.txt`.
- Sanitizes log command by replacing the cookies path with `<cookies.txt>`.
- Attempts to recover `.part` and `.temp.*` files on failure, especially for Windows locked-file behavior.

`list_formats()` uses the Python `YoutubeDL` API and returns rows used directly by `formats_result.html`.

## XLSX Translation Details

`translate_workbook()`:

- First tries an XLSX ZIP/XML fast path that patches `sharedStrings.xml` and simple `inlineStr` values without loading/saving the full workbook through `openpyxl`.
- Falls back to `openpyxl.load_workbook(..., data_only=False)` for unsupported targeted rich text or unusual XLSX structures.
- Translates all sheets if `selected_sheets` is empty.
- Queues only string cells passing `should_translate()`.
- Skips formulas, blank/one-character strings, numeric-like strings, URLs, and emails.
- Skips cells that are likely already in the target language using conservative local heuristics before calling the provider.
- Deduplicates queued text before translation, then maps each unique translation back to every matching cell.
- Uses a persistent SQLite cache at `storage/translation_cache.sqlite` keyed by provider, base URL hash, model, target language, and source text hash.
- If every candidate cell looks already translated, saves the workbook unchanged instead of calling the provider.
- Writes translated strings back into the same cells and saves a new workbook in `storage/processed/{job_id}`.

Batching/concurrency:

- `DEFAULT_MAX_WORKERS = 7`, `DEFAULT_MAX_ITEMS = 100`, `DEFAULT_MAX_CHARS = 30000`.
- `translate_texts()` submits batches in a `ThreadPoolExecutor`, then restores original order with `results_by_index`.
- Provider calls use `httpx.Client` connection pooling inside a translation run.
- Timeout-like translation errors trigger recursive split retry.
- HTTP 429 triggers up to two retries with 25 seconds sleep each.

Provider calls:

- `openai`, `aishop24h`, and `openai_compatible` use `/chat/completions`.
- `gemini` uses Google Generative Language `generateContent`.
- OpenAI-compatible responses are expected as JSON object: `{"translations": [...]}`.
- AIShop24H model-not-available/model-not-found errors trigger `/models` lookup and fallback selection.

Critical invariant: provider output count must match input count. The only special case merges fragments when a one-cell batch returns multiple strings.

## Background Removal Details

`remove_background()`:

- Allows only models listed in `MODELS`.
- Reuses/remembers up to four `rembg` sessions with `lru_cache`.
- Corrects EXIF orientation, converts image to RGBA, and saves `{original_stem}_no_bg.png`.
- Multi-file route zips outputs as `background_removed.zip`.

The backend and partial exist, but the current image sidebar button is marked `upcoming` and has no active workspace section in `index.html`.

## Known Gaps And Risks

- No automated tests are present.
- No auth is implemented; README explicitly says to add auth before public exposure.
- Generated storage is ignored but not cleaned up automatically.
- Network-dependent features may fail in restricted environments.
- `requirements.txt` pins `yt-dlp>=2026.1.1`, which may not exist on older package indexes.
- Some UI text/logs are Vietnamese without accents (`Khong tai duoc...`), while much of the UI is English. Preserve local style unless intentionally cleaning copy.
- Provider defaults are duplicated in backend constants/settings and frontend JS; update all relevant places together.
- `remove-background` route is reachable even though UI navigation marks it upcoming.

## Development Rules For Future Agents

- Prefer small, route/tool-specific changes.
- Keep generated files under `storage/` and do not commit real outputs.
- Do not commit `.env`, API keys, cookies, downloaded videos, processed workbooks, or model/vendor downloads.
- Preserve path traversal checks in `/files`.
- Keep blocking/heavy work in `app/tools`, not in templates or JS.
- For frontend changes, keep the current server-rendered partial + vanilla JS model unless there is a strong reason to change architecture.
- If adding external downloads or package installs, expect network approval to be required.
