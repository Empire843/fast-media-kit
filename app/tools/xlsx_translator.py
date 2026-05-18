from __future__ import annotations

import io
import json
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from app.settings import PROCESSED_DIR


from app.constants import (
    DEFAULT_MODELS,
    LANGUAGES,
    PROVIDERS,
    DEFAULT_MAX_WORKERS,
    DEFAULT_MAX_ITEMS,
    DEFAULT_MAX_CHARS,
)


VIETNAMESE_DIACRITIC_RE = re.compile(
    r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡ"
    r"ùúụủũưừứựửữỳýỵỷỹđ]",
    re.IGNORECASE,
)

SCRIPT_RANGES = {
    "Japanese": re.compile(r"[\u3040-\u30ff\u3400-\u9fff]"),
    "Korean": re.compile(r"[\uac00-\ud7af]"),
    "Chinese Simplified": re.compile(r"[\u3400-\u9fff]"),
    "Thai": re.compile(r"[\u0e00-\u0e7f]"),
}

TARGET_LANGUAGE_MARKERS = {
    "Vietnamese": {
        "cua",
        "cho",
        "cac",
        "khong",
        "duoc",
        "trong",
        "voi",
        "hang",
        "san",
        "pham",
        "mo",
        "ta",
        "ten",
        "gia",
        "ban",
        "ngay",
        "thang",
    },
    "English": {
        "the",
        "and",
        "for",
        "with",
        "from",
        "this",
        "that",
        "product",
        "description",
        "name",
        "price",
        "size",
        "color",
    },
    "French": {
        "le",
        "la",
        "les",
        "des",
        "une",
        "pour",
        "avec",
        "dans",
        "produit",
        "description",
    },
    "Spanish": {
        "el",
        "la",
        "los",
        "las",
        "para",
        "con",
        "producto",
        "descripcion",
        "precio",
    },
}


class TranslationError(RuntimeError):
    pass


class ProviderRequestError(TranslationError):
    def __init__(self, status_code: int, detail: str):
        super().__init__(f"Provider request failed ({status_code}): {detail[:800]}")
        self.status_code = status_code
        self.detail = detail
        self.provider_code = extract_provider_error_code(detail)


def list_sheet_names(xlsx_bytes: bytes) -> list[str]:
    workbook = load_workbook(io.BytesIO(xlsx_bytes), read_only=True, data_only=False)
    try:
        return list(workbook.sheetnames)
    finally:
        workbook.close()


def translate_workbook(
    *,
    xlsx_bytes: bytes,
    original_name: str,
    selected_sheets: list[str],
    target_language: str,
    provider: str,
    model: str,
    api_key: str,
    base_url: str = "",
    max_workers: int = DEFAULT_MAX_WORKERS,
    max_items: int = DEFAULT_MAX_ITEMS,
) -> tuple[str, Path, list[str]]:
    if provider not in PROVIDERS:
        raise TranslationError(f"Unsupported provider: {provider}")
    if not api_key:
        raise TranslationError("Missing API key. Enter a key or configure the default key on the server.")

    import time
    system_start_time = time.time()
    
    logs = [
        f"Provider: {PROVIDERS[provider]}",
        f"Model: {model}",
        f"Target language: {target_language}",
    ]
    workbook = load_workbook(io.BytesIO(xlsx_bytes), data_only=False)
    try:
        sheet_names = set(workbook.sheetnames)
        targets = selected_sheets or list(workbook.sheetnames)
        missing = [name for name in targets if name not in sheet_names]
        if missing:
            raise TranslationError(f"Sheet not found: {', '.join(missing)}")

        cells: list[tuple[Any, str, str]] = []
        scanned_cells = 0
        candidate_cells = 0
        skipped_target_language = 0
        for sheet_name in targets:
            sheet = workbook[sheet_name]
            count_before = len(cells)
            skipped_before = skipped_target_language
            for row in sheet.iter_rows():
                for cell in row:
                    scanned_cells += 1
                    value = cell.value
                    if should_translate(value, cell.data_type):
                        candidate_cells += 1
                        original_text = value
                        normalized_text = normalize_text(value)
                        if is_likely_target_language(normalized_text, target_language):
                            skipped_target_language += 1
                            continue
                        cells.append((cell, original_text, normalized_text))
            logs.append(
                f"Sheet '{sheet_name}': queued {len(cells) - count_before} text cell(s); "
                f"skipped {skipped_target_language - skipped_before} likely already in {target_language}."
            )

        if not cells and not skipped_target_language:
            raise TranslationError("No translatable text cells found in the selected sheet(s).")

        unique_texts = list(dict.fromkeys(text for _, _, text in cells))
        duplicate_cells = len(cells) - len(unique_texts)
        logs.append(f"Scanned {scanned_cells} workbook cell(s).")
        logs.append(f"Found {candidate_cells} text cell(s) after base filters.")
        if skipped_target_language:
            logs.append(f"Skipped {skipped_target_language} cell(s) likely already in {target_language}.")
        logs.append(
            f"Deduplicated {len(cells)} queued cell(s) to {len(unique_texts)} unique text(s); "
            f"saved {duplicate_cells} duplicate translation(s)."
        )

        if not cells:
            job_id, output_path = save_workbook(workbook, original_name, target_language)
            logs.append("No cells were sent to the provider because all candidates looked already translated.")
            logs.append(f"Saved workbook without translation changes: {output_path.name}")
            system_elapsed = time.time() - system_start_time
            logs.append(f"✅ Total system execution time: {system_elapsed:.2f} seconds.")
            return job_id, output_path, logs

        translated = translate_texts(
            texts=unique_texts,
            target_language=target_language,
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            logs=logs,
            max_workers=max_workers,
            max_items=max_items,
        )
        translations_by_text = dict(zip(unique_texts, translated))

        for cell, original_text, normalized_text in cells:
            cell.value = preserve_wrapping(original_text, translations_by_text[normalized_text])

        job_id, output_path = save_workbook(workbook, original_name, target_language)
        logs.append(f"Saved translated workbook: {output_path.name}")
        
        system_elapsed = time.time() - system_start_time
        logs.append(f"✅ Total system execution time: {system_elapsed:.2f} seconds.")
        
        return job_id, output_path, logs
    finally:
        workbook.close()


def should_translate(value: object, data_type: str) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or text.startswith("="):
        return False
    if data_type == "f":
        return False
    if len(text) < 2:
        return False
    if re.fullmatch(r"[\d\s.,:%()+\-_/\\]+", text):
        return False
    if re.fullmatch(r"https?://\S+|\S+@\S+\.\S+", text, flags=re.IGNORECASE):
        return False
    return any(char.isalpha() for char in text)


def save_workbook(workbook: Any, original_name: str, target_language: str) -> tuple[str, Path]:
    job_id = uuid.uuid4().hex
    job_dir = PROCESSED_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    output_name = f"{Path(original_name).stem}_{slugify(target_language)}.xlsx"
    output_path = job_dir / output_name
    workbook.save(output_path)
    return job_id, output_path


def is_likely_target_language(text: str, target_language: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 4:
        return False

    script_re = SCRIPT_RANGES.get(target_language)
    if script_re and script_re.search(stripped):
        return True

    if target_language == "Vietnamese" and VIETNAMESE_DIACRITIC_RE.search(stripped):
        return True

    lower_text = strip_accents(stripped.lower())
    words = re.findall(r"[a-zA-Z]+", lower_text)
    if len(words) < 2:
        return False

    markers = TARGET_LANGUAGE_MARKERS.get(target_language)
    if not markers:
        return False

    marker_hits = sum(1 for word in words if word in markers)
    return marker_hits >= 2


def strip_accents(value: str) -> str:
    value = value.replace("đ", "d").replace("Đ", "D")
    normalized = unicodedata.normalize("NFD", value)
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def normalize_text(value: str) -> str:
    return value.replace("\r\n", "\n")


def preserve_wrapping(original: str, translated: str) -> str:
    if "\r\n" in original:
        return translated.replace("\n", "\r\n")
    return translated


def translate_texts(
    *,
    texts: list[str],
    target_language: str,
    provider: str,
    model: str,
    api_key: str,
    base_url: str,
    logs: list[str],
    max_workers: int = DEFAULT_MAX_WORKERS,
    max_items: int = DEFAULT_MAX_ITEMS,
) -> list[str]:
    translations: list[str] = []
    batches = list(batch_texts(texts, max_items=max_items, max_chars=max_items * 150))
    total_batches = len(batches)
    
    # Pre-allocate to maintain the original order since futures complete out of order
    results_by_index: list[list[str] | None] = [None] * total_batches
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {}
        for i, batch in enumerate(batches):
            batch_index = i + 1
            logs.append(f"Queuing batch {batch_index}/{total_batches}: {len(batch)} cell(s).")
            future = executor.submit(
                translate_batch_with_split_retry,
                batch=batch,
                target_language=target_language,
                provider=provider,
                model=model,
                api_key=api_key,
                base_url=base_url,
                logs=logs,
            )
            future_to_index[future] = (i, batch_index, batch)
            
        for future in as_completed(future_to_index):
            i, batch_index, batch = future_to_index[future]
            try:
                result = future.result()
            except Exception as exc:
                if isinstance(exc, TranslationError):
                    raise
                raise TranslationError(f"Error in batch {batch_index}: {exc}") from exc
                
            if len(result) != len(batch):
                if len(batch) == 1 and len(result) > 1:
                    logs.append(
                        f"Provider returned {len(result)} fragments for one cell in batch {batch_index}; merging them."
                    )
                    result = ["\n".join(part.strip() for part in result if part.strip())]
                else:
                    raise TranslationError(
                        f"Translation count mismatch in batch {batch_index}: expected {len(batch)}, got {len(result)}."
                    )
            if len(result) != len(batch):
                raise TranslationError(
                    f"Translation count mismatch in batch {batch_index}: expected {len(batch)}, got {len(result)}."
                )
            results_by_index[i] = result
            logs.append(f"Completed batch {batch_index}/{total_batches}.")

    for result in results_by_index:
        if result is not None:
            translations.extend(result)
            
    logs.append(f"Translated {len(translations)} cell(s).")
    return translations


def translate_batch_with_split_retry(
    *,
    batch: list[str],
    target_language: str,
    provider: str,
    model: str,
    api_key: str,
    base_url: str,
    logs: list[str],
) -> list[str]:
    import time
    for attempt in range(3):
        try:
            req_start_time = time.time()
            if provider == "gemini":
                result = call_gemini(batch, target_language, model, api_key)
            else:
                result = call_openai_chat(batch, target_language, provider, model, api_key, base_url, logs)
            
            req_elapsed = time.time() - req_start_time
            logs.append(f"Provider responded in {req_elapsed:.2f}s for {len(batch)} cell(s).")
            return result
        except ProviderRequestError as exc:
            if exc.status_code == 429 and attempt < 2:
                logs.append(f"Rate limit (429) on {len(batch)} cells. Sleeping 25s before retry {attempt+1}/3...")
                import time
                time.sleep(25)
                continue
            raise
        except TranslationError as exc:
            if not is_timeout_error(exc) or len(batch) == 1:
                raise
            break

    midpoint = len(batch) // 2
    logs.append(f"Provider timed out on {len(batch)} cell(s). Retrying as {midpoint} + {len(batch) - midpoint}.")
    first = translate_batch_with_split_retry(
        batch=batch[:midpoint],
        target_language=target_language,
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        logs=logs,
    )
    second = translate_batch_with_split_retry(
        batch=batch[midpoint:],
        target_language=target_language,
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        logs=logs,
    )
    return first + second


def is_timeout_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "timeout" in message or "took too long" in message or "timed out" in message


def batch_texts(texts: list[str], *, max_items: int = DEFAULT_MAX_ITEMS, max_chars: int = DEFAULT_MAX_CHARS) -> list[list[str]]:
    batches: list[list[str]] = []
    current: list[str] = []
    current_chars = 0
    for text in texts:
        item_chars = len(text)
        if current and (len(current) >= max_items or current_chars + item_chars > max_chars):
            batches.append(current)
            current = []
            current_chars = 0
        current.append(text)
        current_chars += item_chars
    if current:
        batches.append(current)
    return batches


def call_openai_chat(
    texts: list[str],
    target_language: str,
    provider: str,
    model: str,
    api_key: str,
    base_url: str,
    logs: list[str],
) -> list[str]:
    chat_url = "https://api.openai.com/v1/chat/completions"
    models_url = "https://api.openai.com/v1/models"
    if provider == "aishop24h":
        chat_url = "https://aishop24h.com/v1/chat/completions"
        models_url = "https://aishop24h.com/v1/models"
        if base_url.strip():
            chat_url = f"{base_url.rstrip('/')}/chat/completions"
            models_url = f"{base_url.rstrip('/')}/models"
    elif provider == "openai_compatible":
        if not base_url.strip():
            raise TranslationError("Base URL is required for OpenAI-compatible providers.")
        chat_url = f"{base_url.rstrip('/')}/chat/completions"
        models_url = f"{base_url.rstrip('/')}/models"

    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You translate spreadsheet cell text. Preserve meaning, numbers, placeholders, URLs, "
                    "line breaks, punctuation style, and do not add explanations."
                ),
            },
            {"role": "user", "content": build_prompt(texts, target_language)},
        ],
    }
    try:
        data = post_json(chat_url, payload, api_key)
    except ProviderRequestError as exc:
        if provider != "aishop24h" or exc.provider_code not in {"model_not_available", "model_not_found"}:
            raise
        available_models = list_openai_compatible_models(models_url, api_key)
        fallback_model = pick_fallback_model(available_models)
        if not fallback_model:
            raise TranslationError(
                f"{exc}. Could not find a fallback model from the provider's /models response."
            ) from exc
        logs.append(f"Model '{model}' is not available. Retrying with '{fallback_model}'.")
        payload["model"] = fallback_model
        data = post_json(chat_url, payload, api_key)
    content = extract_completion_text(data)
    return parse_translations(content)


def call_gemini(texts: list[str], target_language: str, model: str, api_key: str) -> list[str]:
    encoded_model = urllib.parse.quote(model, safe="")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{encoded_model}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            "Translate spreadsheet cell text. Return JSON only.\n\n"
                            + build_prompt(texts, target_language)
                        )
                    }
                ],
            }
        ],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }
    data = post_json(url, payload, None)
    content = data["candidates"][0]["content"]["parts"][0]["text"]
    return parse_translations(content)


def build_prompt(texts: list[str], target_language: str) -> str:
    return json.dumps(
        {
            "instruction": (
                f"Translate each input item to {target_language}. Return exactly one output string per input item. "
                "Do not split one input item into multiple translations. Keep the same array length and order."
            ),
            "output_schema": {"translations": ["translated string"]},
            "expected_count": len(texts),
            "texts": texts,
        },
        ensure_ascii=False,
    )


def post_json(url: str, payload: dict[str, Any], api_key: str | None) -> dict[str, Any]:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "QuickMediaTools/1.0 (+https://localhost)",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ProviderRequestError(exc.code, detail) from exc
    except urllib.error.URLError as exc:
        raise TranslationError(f"Provider request failed: {exc}") from exc


def get_json(url: str, api_key: str | None) -> dict[str, Any]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "QuickMediaTools/1.0 (+https://localhost)",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ProviderRequestError(exc.code, detail) from exc
    except urllib.error.URLError as exc:
        raise TranslationError(f"Provider request failed: {exc}") from exc


def list_openai_compatible_models(url: str, api_key: str) -> list[str]:
    data = get_json(url, api_key)
    models = data.get("data", [])
    ids = []
    for model in models:
        if isinstance(model, dict) and isinstance(model.get("id"), str):
            ids.append(model["id"])
    return ids


def pick_fallback_model(models: list[str]) -> str | None:
    preferred_exact = [
        "google/gemini-3-pro-preview",
        "google/gemini-3-flash-preview",
        "google/gemini-2.5-pro",
        "anthropic/claude-sonnet-4.6",
        "anthropic/claude-sonnet-4.5",
        "anthropic/claude-haiku-4.5",
    ]
    for model in preferred_exact:
        if model in models:
            return model

    preferred_terms = ("gemini", "claude", "gpt")
    for term in preferred_terms:
        for model in models:
            if term in model.lower() and "image" not in model.lower():
                return model
    return models[0] if models else None


def extract_provider_error_code(detail: str) -> str:
    try:
        data = json.loads(detail)
    except json.JSONDecodeError:
        return ""
    error = data.get("error")
    if isinstance(error, dict) and isinstance(error.get("code"), str):
        return error["code"]
    return ""


def parse_translations(content: str) -> list[str]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    data = json.loads(cleaned)
    translations = data.get("translations")
    if not isinstance(translations, list) or not all(isinstance(item, str) for item in translations):
        raise TranslationError("Provider returned invalid translation JSON.")
    return translations


def extract_completion_text(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    return content
            text = first.get("text")
            if isinstance(text, str):
                return text

    candidates = data.get("candidates")
    if isinstance(candidates, list) and candidates:
        first = candidates[0]
        if isinstance(first, dict):
            content = first.get("content")
            if isinstance(content, dict):
                parts = content.get("parts")
                if isinstance(parts, list):
                    text = "".join(
                        part.get("text", "")
                        for part in parts
                        if isinstance(part, dict) and isinstance(part.get("text"), str)
                    )
                    if text:
                        return text

    error = data.get("error")
    if isinstance(error, dict):
        message = error.get("message") or json.dumps(error, ensure_ascii=False)
        raise TranslationError(f"Provider returned an error response: {message}")

    raise TranslationError(
        "Provider response did not contain translated text. "
        f"Response keys: {', '.join(data.keys()) or 'none'}; sample: {json.dumps(data, ensure_ascii=False)[:800]}"
    )


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "translated"
