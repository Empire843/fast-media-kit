from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL

from app.settings import DOWNLOADS_DIR, PORTABLE_FFMPEG_BIN


BEST_WITH_FFMPEG_FORMAT = (
    "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b[ext=mp4][acodec!=none]/b[acodec!=none]"
)
BEST_SINGLE_FILE_FORMAT = "b"
QUALITY_FORMATS = {
    "best": BEST_WITH_FFMPEG_FORMAT,
    "1080p": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080][ext=mp4][acodec!=none]/b[height<=1080][acodec!=none]",
    "720p": "bv*[height<=720][ext=mp4]+ba[ext=m4a]/bv*[height<=720]+ba/b[height<=720][ext=mp4][acodec!=none]/b[height<=720][acodec!=none]",
    "480p": "bv*[height<=480][ext=mp4]+ba[ext=m4a]/bv*[height<=480]+ba/b[height<=480][ext=mp4][acodec!=none]/b[height<=480][acodec!=none]",
    "360p": "bv*[height<=360][ext=mp4]+ba[ext=m4a]/bv*[height<=360]+ba/b[height<=360][ext=mp4][acodec!=none]/b[height<=360][acodec!=none]",
    "audio": "ba[ext=m4a]/ba/bestaudio",
}


class ToolRunError(RuntimeError):
    def __init__(self, message: str, logs: list[str] | None = None):
        super().__init__(message)
        self.logs = logs or []


def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None or ffmpeg_location() is not None


def ffmpeg_location() -> Path | None:
    if shutil.which("ffmpeg"):
        return None
    portable = PORTABLE_FFMPEG_BIN / "ffmpeg.exe"
    if portable.exists():
        return PORTABLE_FFMPEG_BIN
    return None


def choose_format(custom_format: str | None = None, quality: str = "best") -> str:
    if custom_format:
        return custom_format
    if not has_ffmpeg():
        return BEST_SINGLE_FILE_FORMAT
    return QUALITY_FORMATS.get(quality, BEST_WITH_FFMPEG_FORMAT)


def safe_platform_name(platform: str) -> str:
    cleaned = "".join(char for char in platform.lower() if char.isalnum())
    return cleaned or "video"


def yt_dlp_command() -> list[str]:
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    return [sys.executable, "-m", "yt_dlp"]


def clean_network_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        env.pop(key, None)
    location = ffmpeg_location()
    if location:
        env["PATH"] = f"{location}{os.pathsep}{env.get('PATH', '')}"
    return env


def recover_intermediate_files(job_dir: Path) -> list[Path]:
    recovered: list[Path] = []
    for part_file in job_dir.glob("*.part"):
        final_path = part_file.with_suffix("")
        if not final_path.name:
            continue
        if final_path.exists():
            recovered.append(final_path)
            continue
        try:
            shutil.copyfile(part_file, final_path)
        except OSError:
            continue
        recovered.append(final_path)

    for temp_file in job_dir.glob("*.temp.*"):
        final_name = temp_file.name.replace(".temp.", ".", 1)
        final_path = temp_file.with_name(final_name)
        if final_path.exists():
            recovered.append(final_path)
            continue
        try:
            shutil.copyfile(temp_file, final_path)
        except OSError:
            continue
        recovered.append(final_path)
    return recovered


def collect_output_files(job_dir: Path, output_prefix: str) -> list[Path]:
    exact_outputs = []
    for path in job_dir.iterdir():
        if not path.is_file():
            continue
        if path.name.endswith(".part") or ".temp." in path.name:
            continue
        if path.stem == output_prefix:
            exact_outputs.append(path)

    if exact_outputs:
        return sorted(exact_outputs, key=lambda item: item.stat().st_mtime, reverse=True)

    return sorted(
        [
            path
            for path in job_dir.iterdir()
            if path.is_file() and not path.name.endswith(".part") and ".temp." not in path.name
        ],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )


def download_video(
    *,
    url: str,
    platform: str,
    custom_format: str | None = None,
    quality: str = "best",
    cookies_bytes: bytes | None = None,
    redownload: bool = False,
) -> tuple[str, list[Path], list[str]]:
    job_id = uuid.uuid4().hex
    job_dir = DOWNLOADS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    output_prefix = f"{safe_platform_name(platform)}_{job_id[:10]}"
    output_name = f"{output_prefix}.%(ext)s"
    logs = [
        f"Job: {job_id}",
        f"Platform: {platform}",
        f"Quality: {quality}",
        f"Output directory: {job_dir}",
    ]

    cmd = yt_dlp_command()
    cmd.extend(
        [
            "--no-config",
            "--no-playlist",
            "--no-part",
            "--restrict-filenames",
            "--windows-filenames",
            "--merge-output-format",
            "mp4",
            "--remux-video",
            "mp4",
            "-o",
            str(job_dir / output_name),
            "-f",
            choose_format(custom_format, quality),
        ]
    )

    location = ffmpeg_location()
    if location:
        cmd.extend(["--ffmpeg-location", str(location)])

    if not custom_format and not has_ffmpeg():
        cmd.extend(["--format-sort", "hasaud,ext:mp4,res,br"])

    if redownload:
        cmd.extend(["--force-overwrites", "--no-continue"])

    with tempfile.TemporaryDirectory() as tmpdir:
        if cookies_bytes:
            cookie_path = Path(tmpdir) / "cookies.txt"
            cookie_path.write_bytes(cookies_bytes)
            cmd.extend(["--cookies", str(cookie_path)])
            logs.append("Cookies: uploaded cookies.txt")

        cmd.append(url)
        safe_cmd = ["<cookies.txt>" if str(part).endswith("cookies.txt") else str(part) for part in cmd]
        logs.append("Command: " + shlex.join(safe_cmd))
        result = subprocess.run(
            cmd,
            cwd=job_dir,
            env=clean_network_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    if result.stdout.strip():
        logs.append("yt-dlp stdout:")
        logs.extend(result.stdout.strip().splitlines())
    if result.stderr.strip():
        logs.append("yt-dlp stderr:")
        logs.extend(result.stderr.strip().splitlines())

    if result.returncode != 0:
        recovered = recover_intermediate_files(job_dir)
        if recovered and "Access is denied" in (result.stderr or result.stdout):
            logs.append("Recovered output by copying locked intermediate file.")
            return job_id, sorted(recovered, key=lambda item: item.stat().st_mtime, reverse=True), logs

        message = (result.stderr or result.stdout or "yt-dlp failed").strip()
        raise ToolRunError(message, logs)

    recover_intermediate_files(job_dir)
    files = collect_output_files(job_dir, output_prefix)
    if not files:
        raise ToolRunError(f"{platform} downloader finished but no output file was created.", logs)

    logs.append(f"Done: {len(files)} output file(s).")
    return job_id, files, logs


def list_formats(url: str, cookies_bytes: bytes | None = None) -> list[dict[str, Any]]:
    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "proxy": "",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        if cookies_bytes:
            cookie_path = Path(tmpdir) / "cookies.txt"
            cookie_path.write_bytes(cookies_bytes)
            options["cookiefile"] = str(cookie_path)

        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)

    rows = []
    for item in info.get("formats", []):
        rows.append(
            {
                "format_id": item.get("format_id") or "",
                "ext": item.get("ext") or "",
                "resolution": item.get("resolution")
                or f"{item.get('width') or ''}x{item.get('height') or ''}".strip("x"),
                "fps": item.get("fps") or "",
                "vcodec": item.get("vcodec") or "",
                "acodec": item.get("acodec") or "",
                "size": round((item.get("filesize") or item.get("filesize_approx") or 0) / 1048576, 2),
                "note": item.get("format_note") or "",
            }
        )
    return rows
