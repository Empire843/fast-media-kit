from __future__ import annotations

import zipfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.settings import (
    DEFAULT_AISHOP24H_API_KEY,
    BASE_DIR,
    DOWNLOADS_DIR,
    DEFAULT_GEMINI_API_KEY,
    DEFAULT_OPENAI_API_KEY,
    DEFAULT_TRANSLATION_API_KEY,
    DEFAULT_TRANSLATION_BASE_URL,
    DEFAULT_TRANSLATION_MODEL,
    DEFAULT_TRANSLATION_PROVIDER,
    PROCESSED_DIR,
    STORAGE_DIR,
)
from app.tools.background import MODELS, remove_background
from app.tools.downloader import ToolRunError, download_video, has_ffmpeg, list_formats
from app.constants import (
    DEFAULT_MODELS,
    LANGUAGES,
    PROVIDERS,
    DEFAULT_MAX_WORKERS,
    DEFAULT_MAX_ITEMS,
)
from app.tools.xlsx_translator import (
    TranslationError,
    convert_workbook_to_markdown_rag,
    download_google_sheet_as_xlsx,
    list_sheet_names,
    translate_workbook,
)


app = FastAPI(title="Quick Media Tools")
app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")


def render_partial(request: Request, template_name: str, context: dict) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        template_name,
        {
            **context,
            "ffmpeg_available": has_ffmpeg(),
            "background_models": MODELS,
            "translation_providers": PROVIDERS,
            "translation_languages": LANGUAGES,
            "translation_default_provider": DEFAULT_TRANSLATION_PROVIDER,
            "translation_default_model": DEFAULT_TRANSLATION_MODEL,
            "translation_default_base_url": DEFAULT_TRANSLATION_BASE_URL,
            "has_default_translation_key": has_default_translation_key(),
            "translation_default_max_workers": DEFAULT_MAX_WORKERS,
            "translation_default_max_items": DEFAULT_MAX_ITEMS,
        },
    )


def safe_file_response(kind: str, job_id: str, filename: str) -> FileResponse:
    base = {"downloads": DOWNLOADS_DIR, "processed": PROCESSED_DIR}.get(kind)
    if base is None:
        raise HTTPException(status_code=404, detail="Unknown file kind")

    target = (base / job_id / filename).resolve()
    try:
        target.relative_to((base / job_id).resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Invalid file path") from None
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(target, filename=target.name)


VALID_TOOLS = {"download", "translate", "xlsx-markdown"}


@app.get("/", response_class=HTMLResponse)
def dashboard_root(request: Request):
    return _render_dashboard(request, "download")


@app.get("/{tool}", response_class=HTMLResponse)
def dashboard_tool(request: Request, tool: str):
    if tool not in VALID_TOOLS:
        raise HTTPException(status_code=404, detail="Tool not found")
    return _render_dashboard(request, tool)


def _render_dashboard(request: Request, active_tool: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "active_tool": active_tool,
            "ffmpeg_available": has_ffmpeg(),
            "background_models": MODELS,
            "translation_providers": PROVIDERS,
            "translation_languages": LANGUAGES,
            "translation_default_provider": DEFAULT_TRANSLATION_PROVIDER,
            "translation_default_model": DEFAULT_TRANSLATION_MODEL,
            "translation_default_base_url": DEFAULT_TRANSLATION_BASE_URL,
            "has_default_translation_key": has_default_translation_key(),
            "translation_default_max_workers": DEFAULT_MAX_WORKERS,
            "translation_default_max_items": DEFAULT_MAX_ITEMS,
        },
    )


def has_default_translation_key() -> bool:
    return bool(
        DEFAULT_TRANSLATION_API_KEY
        or DEFAULT_AISHOP24H_API_KEY
        or DEFAULT_OPENAI_API_KEY
        or DEFAULT_GEMINI_API_KEY
    )


def get_default_translation_key(provider: str) -> str:
    if DEFAULT_TRANSLATION_API_KEY:
        return DEFAULT_TRANSLATION_API_KEY
    if provider == "aishop24h":
        return DEFAULT_AISHOP24H_API_KEY
    if provider == "gemini":
        return DEFAULT_GEMINI_API_KEY
    return DEFAULT_OPENAI_API_KEY


def get_default_translation_model(provider: str) -> str:
    if provider == DEFAULT_TRANSLATION_PROVIDER:
        return DEFAULT_TRANSLATION_MODEL
    return DEFAULT_MODELS.get(provider, DEFAULT_TRANSLATION_MODEL)


@app.post("/tools/download-video", response_class=HTMLResponse)
async def download_video_tool(
    request: Request,
    url: str = Form(...),
    platform: str = Form("Other"),
    quality: str = Form("best"),
    custom_format: str = Form(""),
    redownload: bool = Form(False),
    cookies: UploadFile | None = File(None),
):
    try:
        cookies_bytes = await cookies.read() if cookies and cookies.filename else None
        job_id, files, logs = download_video(
            url=url.strip(),
            platform=platform,
            quality=quality,
            custom_format=custom_format.strip() or None,
            cookies_bytes=cookies_bytes,
            redownload=redownload,
        )
    except ToolRunError as exc:
        return render_partial(
            request,
            "partials/error.html",
            {"message": f"Khong tai duoc video: {exc}", "logs": exc.logs},
        )
    except Exception as exc:
        return render_partial(
            request,
            "partials/error.html",
            {"message": f"Khong tai duoc video: {exc}", "logs": []},
        )

    return render_partial(
        request,
        "partials/download_result.html",
        {"job_id": job_id, "files": files, "logs": logs},
    )


@app.post("/tools/list-formats", response_class=HTMLResponse)
async def list_video_formats(
    request: Request,
    url: str = Form(...),
    cookies: UploadFile | None = File(None),
):
    try:
        cookies_bytes = await cookies.read() if cookies and cookies.filename else None
        formats = list_formats(url.strip(), cookies_bytes=cookies_bytes)
    except Exception as exc:
        return render_partial(
            request,
            "partials/error.html",
            {"message": f"Khong lay duoc danh sach format: {exc}"},
        )

    return render_partial(
        request,
        "partials/formats_result.html",
        {"formats": formats},
    )


@app.post("/tools/remove-background", response_class=HTMLResponse)
async def remove_background_tool(
    request: Request,
    images: list[UploadFile] = File(...),
    model: str = Form("isnet-general-use"),
    alpha_matting: bool = Form(False),
):
    outputs: list[Path] = []
    job_id: str | None = None
    logs = [
        f"Model: {model}",
        f"Alpha matting: {'on' if alpha_matting else 'off'}",
        f"Input files: {len(images)}",
    ]
    try:
        for index, image in enumerate(images, start=1):
            if not image.filename:
                continue
            logs.append(f"[{index}/{len(images)}] Processing {image.filename}")
            job_id, output_path = remove_background(
                image_bytes=await image.read(),
                original_name=image.filename,
                model=model,
                alpha_matting=alpha_matting,
                job_id=job_id,
            )
            outputs.append(output_path)
            logs.append(f"[{index}/{len(images)}] Saved {output_path.name}")
    except Exception as exc:
        logs.append(f"Error: {exc}")
        return render_partial(
            request,
            "partials/error.html",
            {"message": f"Khong xoa duoc nen anh: {exc}", "logs": logs},
        )

    if not job_id or not outputs:
        return render_partial(
            request,
            "partials/error.html",
            {"message": "Chua co anh hop le de xu ly.", "logs": logs},
        )

    zip_path = None
    if len(outputs) > 1:
        zip_path = PROCESSED_DIR / job_id / "background_removed.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for output in outputs:
                archive.write(output, arcname=output.name)
        logs.append(f"Created ZIP: {zip_path.name}")

    logs.append(f"Done: {len(outputs)} image(s).")

    return render_partial(
        request,
        "partials/background_result.html",
        {"job_id": job_id, "files": outputs, "zip_path": zip_path, "logs": logs},
    )


@app.post("/tools/xlsx-sheets", response_class=HTMLResponse)
async def xlsx_sheets(request: Request, workbook: UploadFile = File(...)):
    logs = []
    try:
        if not workbook.filename:
            raise TranslationError("Upload an XLSX file first.")
        sheets = list_sheet_names(await workbook.read())
        logs.append(f"Found {len(sheets)} sheet(s) in {workbook.filename}.")
    except Exception as exc:
        return render_partial(
            request,
            "partials/error.html",
            {"message": f"Khong doc duoc danh sach sheet: {exc}", "logs": logs},
        )

    return render_partial(
        request,
        "partials/xlsx_sheets.html",
        {"sheets": sheets, "logs": logs},
    )


@app.post("/tools/translate-xlsx", response_class=HTMLResponse)
async def translate_xlsx_tool(
    request: Request,
    workbook: UploadFile = File(...),
    selected_sheets: list[str] | None = Form(default=None),
    target_language: str = Form("Vietnamese"),
    provider: str = Form(DEFAULT_TRANSLATION_PROVIDER),
    model: str = Form(""),
    api_key: str = Form(""),
    base_url: str = Form(DEFAULT_TRANSLATION_BASE_URL),
    max_workers: int = Form(DEFAULT_MAX_WORKERS),
    max_items: int = Form(DEFAULT_MAX_ITEMS),
):
    logs = []
    try:
        if not workbook.filename:
            raise TranslationError("Upload an XLSX file first.")
        effective_model = model.strip() or get_default_translation_model(provider)
        effective_key = api_key.strip() or get_default_translation_key(provider)
        job_id, output_path, logs = translate_workbook(
            xlsx_bytes=await workbook.read(),
            original_name=workbook.filename,
            selected_sheets=selected_sheets or [],
            target_language=target_language,
            provider=provider,
            model=effective_model,
            api_key=effective_key,
            base_url=base_url.strip(),
            max_workers=max_workers,
            max_items=max_items,
        )
    except Exception as exc:
        return render_partial(
            request,
            "partials/error.html",
            {"message": f"Khong dich duoc file XLSX: {exc}", "logs": logs},
        )

    return render_partial(
        request,
        "partials/xlsx_result.html",
        {"job_id": job_id, "file": output_path, "logs": logs},
    )


@app.post("/tools/xlsx-to-markdown", response_class=HTMLResponse)
async def xlsx_to_markdown_tool(
    request: Request,
    workbook: UploadFile | None = File(None),
    google_sheet_url: str = Form(""),
    selected_sheets: list[str] | None = Form(default=None),
    convert_mode: str = Form("fast"),
    provider: str = Form(DEFAULT_TRANSLATION_PROVIDER),
    model: str = Form(""),
    api_key: str = Form(""),
    base_url: str = Form(DEFAULT_TRANSLATION_BASE_URL),
    max_workers: int = Form(DEFAULT_MAX_WORKERS),
):
    logs = []
    try:
        effective_model = model.strip() or get_default_translation_model(provider)
        effective_key = api_key.strip() or get_default_translation_key(provider)
        url = google_sheet_url.strip()
        if url:
            xlsx_bytes, original_name = download_google_sheet_as_xlsx(url)
            logs.append("Source: Google Sheet URL export.")
            selected = []
        elif workbook and workbook.filename:
            xlsx_bytes = await workbook.read()
            original_name = workbook.filename
            logs.append(f"Source: uploaded XLSX file ({workbook.filename}).")
            selected = selected_sheets or []
        else:
            raise TranslationError("Upload file XLSX hoac nhap URL Google Sheet.")

        job_id, files, zip_path, processed_sheets, convert_logs = convert_workbook_to_markdown_rag(
            xlsx_bytes=xlsx_bytes,
            original_name=original_name,
            selected_sheets=selected,
            convert_mode=convert_mode,
            provider=provider,
            model=effective_model,
            api_key=effective_key,
            base_url=base_url.strip(),
            max_workers=max_workers,
        )
        logs.extend(convert_logs)
    except Exception as exc:
        return render_partial(
            request,
            "partials/error.html",
            {"message": f"Khong convert duoc XLSX sang Markdown: {exc}", "logs": logs},
        )

    return render_partial(
        request,
        "partials/xlsx_markdown_result.html",
        {
            "job_id": job_id,
            "files": files,
            "zip_path": zip_path,
            "processed_sheets": processed_sheets,
            "logs": logs,
        },
    )


@app.get("/files/{kind}/{job_id}/{filename}")
def files(kind: str, job_id: str, filename: str):
    return safe_file_response(kind, job_id, filename)
