# api/routers/manju/images.py
# -*- coding: utf-8 -*-
"""Manju-specific image generation helpers: URL attachment, image download/decode,
HTTP payload building, OpenAI image params, prompt item collection, prompt resolution."""

import base64
import json
import os
import re
from typing import Any

import requests
from fastapi import HTTPException

from api.image_service import image_response_payload
from api.schemas import ManjuImageGenerateRequest

from .parser import (
    _load_characters_structured,
    _load_storyboard_rows,
    _work_dir,
)
from .prompts import (
    _build_character_image_prompt,
    _build_storyboard_image_prompt,
)


# ---------------------------------------------------------------------------
# Images dir
# ---------------------------------------------------------------------------

def _images_dir(filepath: str) -> str:
    from api.security import safe_join
    path = safe_join(_work_dir(filepath), "images")
    os.makedirs(path, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Image URL attachment
# ---------------------------------------------------------------------------

def _attach_image_urls(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for row in rows:
        item = dict(row)
        if item.get("image_path"):
            payload = image_response_payload(str(item["image_path"]), "", "")
            item.setdefault("image_url", payload["url"])
            item.setdefault("image_download_url", payload["download_url"])
        enriched.append(item)
    return enriched


# ---------------------------------------------------------------------------
# Image download / decode helpers
# ---------------------------------------------------------------------------

def _download_image_url(url: str) -> bytes | None:
    if not url or not re.match(r"^https?://", url, re.IGNORECASE):
        return None
    res = requests.get(url, timeout=120)
    res.raise_for_status()
    return res.content or None


def _decode_image_base64(value: Any) -> bytes | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.startswith("data:image/") and "," in text:
        text = text.split(",", 1)[1]
    compact = re.sub(r"\s+", "", text)
    if len(compact) < 80:
        return None
    try:
        return base64.b64decode(compact, validate=True)
    except Exception:
        try:
            return base64.b64decode(compact)
        except Exception:
            return None


def _extract_image_bytes(payload: Any) -> bytes | None:
    """兼容 OpenAI Images 接口常见返回结构。"""
    if isinstance(payload, dict):
        for key in ("b64_json", "image_base64", "base64", "image", "binary_data_base64"):
            image_bytes = _decode_image_base64(payload.get(key))
            if image_bytes:
                return image_bytes
        for key in ("url", "image_url", "image_urls"):
            value = payload.get(key)
            if isinstance(value, list):
                for item in value:
                    image_bytes = _extract_image_bytes(item)
                    if image_bytes:
                        return image_bytes
            elif isinstance(value, dict):
                image_bytes = _extract_image_bytes(value)
                if image_bytes:
                    return image_bytes
            elif isinstance(value, str):
                image_bytes = _download_image_url(value)
                if image_bytes:
                    return image_bytes
        for value in payload.values():
            image_bytes = _extract_image_bytes(value)
            if image_bytes:
                return image_bytes
    elif isinstance(payload, list):
        for item in payload:
            image_bytes = _extract_image_bytes(item)
            if image_bytes:
                return image_bytes
    elif isinstance(payload, str):
        image_bytes = _decode_image_base64(payload)
        if image_bytes:
            return image_bytes
        return _download_image_url(payload)
    return None


# ---------------------------------------------------------------------------
# HTTP payload / OpenAI image params
# ---------------------------------------------------------------------------

def _http_payload_from_template(template: str, prompt: str) -> Any:
    template = template or '{"prompt": "{prompt}"}'
    escaped_prompt = json.dumps(prompt, ensure_ascii=False)[1:-1]
    payload_text = template.replace("{prompt}", escaped_prompt)
    try:
        return json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"HTTP payload template 不是合法 JSON：{exc.msg}") from exc


def _openai_image_params(config: dict[str, Any], prompt: str) -> dict[str, Any]:
    model = config.get("model") or "gpt-image-1"
    output_format = (config.get("output_format") or "png").lower().lstrip(".")
    params: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "size": config.get("size") or "1024x1536",
        "n": 1,
    }
    if model.startswith("gpt-image"):
        quality = config.get("quality") or "medium"
        if quality:
            params["quality"] = quality
        if output_format in {"png", "jpeg", "webp"}:
            params["output_format"] = output_format
    elif model == "dall-e-3":
        quality = config.get("quality") or "standard"
        params["quality"] = quality if quality in {"standard", "hd"} else "standard"
        params["response_format"] = "b64_json"
    else:
        params["response_format"] = "b64_json"
    return params


# ---------------------------------------------------------------------------
# Manju prompt items (for import to image queue)
# ---------------------------------------------------------------------------

def _manju_prompt_items(filepath: str, kind: str, shot_ids: list[str] | None = None) -> list[dict[str, Any]]:
    from .export import _collect_markdown_prompt_items
    from .parser import _read_text

    if kind == "characters":
        items = []
        for idx, card in enumerate(_load_characters_structured(filepath), 1):
            prompt, negative = _build_character_image_prompt(filepath, card)
            if not prompt:
                continue
            items.append({
                "id": card.get("id") or card.get("name") or f"character_{idx}",
                "title": f"角色卡｜{card.get('name') or idx}",
                "prompt": prompt,
                "negative_prompt": negative,
                "source_type": "manju_character",
                "source_id": str(card.get("id") or card.get("name") or idx),
                "source_label": "角色卡",
            })
        return items
    if kind == "scenes":
        path = os.path.join(_work_dir(filepath), "scenes.md")
        return _collect_markdown_prompt_items(_read_text(path) if os.path.exists(path) else "", "manju_scene", "场景图")
    if kind == "storyboards":
        rows = _load_storyboard_rows(filepath)
        if rows:
            id_filter = {str(sid) for sid in (shot_ids or []) if sid}
            items = []
            for idx, row in enumerate(rows, 1):
                row_id = str(row.get("id") or f"shot_{idx}")
                if id_filter and row_id not in id_filter:
                    continue
                prompt, negative = _build_storyboard_image_prompt(filepath, row)
                if not prompt:
                    continue
                items.append({
                    "id": row.get("id") or f"shot_{idx}",
                    "title": f"分镜图｜第{row.get('chapter_num')}章｜镜{row.get('shot_no')}",
                    "prompt": prompt,
                    "negative_prompt": negative,
                    "source_type": "manju_storyboard",
                    "source_id": str(row.get("id") or idx),
                    "source_label": "分镜图",
                })
            return items
        path = os.path.join(_work_dir(filepath), "storyboards.md")
        return _collect_markdown_prompt_items(_read_text(path) if os.path.exists(path) else "", "manju_storyboard", "分镜图")
    if kind == "all":
        items: list[dict[str, Any]] = []
        for item_kind in ("characters", "scenes", "storyboards"):
            items.extend(_manju_prompt_items(filepath, item_kind, shot_ids if item_kind == "storyboards" else None))
        return items
    raise HTTPException(status_code=400, detail="kind 只能是 characters/scenes/storyboards/all")


# ---------------------------------------------------------------------------
# Resolve image prompt
# ---------------------------------------------------------------------------

def _resolve_image_prompt(body: ManjuImageGenerateRequest) -> str:
    if body.prompt.strip():
        return body.prompt.strip()
    if body.source_type == "character":
        for card in _load_characters_structured(body.filepath):
            if card.get("id") == body.source_id or card.get("name") == body.source_id:
                prompt, negative = _build_character_image_prompt(body.filepath, card)
                return f"{prompt}\nNegative prompt: {negative}".strip()
    if body.source_type == "shot":
        for row in _load_storyboard_rows(body.filepath):
            if row.get("id") == body.source_id:
                prompt, negative = _build_storyboard_image_prompt(body.filepath, row)
                return f"{prompt}\nNegative prompt: {negative}".strip()
    if body.source_type == "scene":
        from .parser import _load_scenes_structured
        for sc in _load_scenes_structured(body.filepath):
            if sc.get("id") == body.source_id or sc.get("name") == body.source_id:
                positive = str(sc.get("prompt_positive") or "").strip()
                if positive:
                    negative = str(sc.get("prompt_negative") or "").strip()
                    return (f"{positive}\nNegative prompt: {negative}".strip()
                            if negative else positive)
    raise HTTPException(status_code=400, detail="未找到可用于生成图片的提示词")
