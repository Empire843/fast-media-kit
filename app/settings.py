from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
DOWNLOADS_DIR = STORAGE_DIR / "downloads"
PROCESSED_DIR = STORAGE_DIR / "processed"
VENDOR_DIR = BASE_DIR / "vendor"
PORTABLE_FFMPEG_BIN = VENDOR_DIR / "ffmpeg-download" / "ffmpeg-8.1.1-essentials_build" / "bin"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_env_file(BASE_DIR / ".env")

DEFAULT_TRANSLATION_PROVIDER = os.getenv("TRANSLATION_PROVIDER", "aishop24h")
DEFAULT_TRANSLATION_MODEL = (
    os.getenv("TRANSLATION_MODEL")
    or os.getenv("AISHOP24H_MODEL")
    or "google/gemini-2.5-pro"
)
DEFAULT_TRANSLATION_BASE_URL = (
    os.getenv("TRANSLATION_BASE_URL")
    or os.getenv("AISHOP24H_BASE_URL")
    or "https://aishop24h.com/v1"
)
DEFAULT_TRANSLATION_API_KEY = os.getenv("TRANSLATION_API_KEY", "")
DEFAULT_AISHOP24H_API_KEY = os.getenv("AISHOP24H_API_KEY", "")
DEFAULT_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

for directory in (DOWNLOADS_DIR, PROCESSED_DIR):
    directory.mkdir(parents=True, exist_ok=True)
