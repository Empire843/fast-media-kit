from __future__ import annotations

import io
import uuid
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageOps

from app.settings import PROCESSED_DIR


MODELS = [
    "isnet-general-use",
    "u2net",
    "u2netp",
    "u2net_human_seg",
    "silueta",
    "isnet-anime",
]


@lru_cache(maxsize=2)
def get_session(model: str):
    from rembg import new_session

    return new_session(model)


def remove_background(
    *,
    image_bytes: bytes,
    original_name: str,
    model: str,
    alpha_matting: bool = False,
    job_id: str | None = None,
) -> tuple[str, Path]:
    if model not in MODELS:
        raise ValueError(f"Unsupported model: {model}")

    job_id = job_id or uuid.uuid4().hex
    job_dir = PROCESSED_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    from rembg import remove

    with Image.open(io.BytesIO(image_bytes)) as image:
        image = ImageOps.exif_transpose(image).convert("RGBA")
        result = remove(
            image,
            session=get_session(model),
            alpha_matting=alpha_matting,
        )
        if not isinstance(result, Image.Image):
            result = Image.open(result).convert("RGBA")

    output_path = job_dir / f"{Path(original_name).stem}_no_bg.png"
    result.save(output_path, "PNG", optimize=True)
    return job_id, output_path
