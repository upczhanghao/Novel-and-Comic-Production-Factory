# api/image_service.py
# -*- coding: utf-8 -*-
"""图片生成配置、调用与文件访问工具。"""

from __future__ import annotations

import base64
import json
import os
import re
from datetime import datetime
from typing import Any
from urllib.parse import quote

import requests
from fastapi import HTTPException

from api.security import normalize_project_path, safe_join

MIRRORSTAGES_OPENAI_BASE_URL = "https://api.mirrorstages.com/openai/v1"


def safe_image_config(config: dict[str, Any]) -> dict[str, Any]:
    return {**config, "api_key": "***"} if config.get("api_key") else dict(config)


def normalize_mirrorstages_base_url(base_url: str) -> str:
    normalized = (base_url or "").strip().rstrip("/")
    if normalized == "https://api.mirrorstages.com/v1":
        return MIRRORSTAGES_OPENAI_BASE_URL
    return normalized


def normalize_image_config(config: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    from api.image_params import (
        ASPECT_RATIOS,
        RESOLUTIONS,
        derive_size_quality,
        infer_aspect_resolution,
    )

    existing = existing or {}
    provider = (config.get("provider") or "openai").strip().lower()
    default_base_url = MIRRORSTAGES_OPENAI_BASE_URL if provider == "mirrorstages" else "https://api.openai.com/v1"
    base_url = normalize_mirrorstages_base_url(config.get("base_url") or default_base_url) if provider == "mirrorstages" else (config.get("base_url") or default_base_url)

    # F1: aspect_ratio + resolution 是新主字段；size / quality 派生写回保持向后兼容。
    aspect_ratio = str(config.get("aspect_ratio") or "").strip()
    resolution = str(config.get("resolution") or "").strip()
    if not aspect_ratio or not resolution:
        # 旧配置回填：从已存的 size/quality 反推
        legacy_size = str(config.get("size") or existing.get("size") or "1024x1536")
        legacy_quality = str(config.get("quality") or existing.get("quality") or "medium")
        inferred_aspect, inferred_res = infer_aspect_resolution(legacy_size, legacy_quality)
        aspect_ratio = aspect_ratio or inferred_aspect
        resolution = resolution or inferred_res
    if aspect_ratio not in ASPECT_RATIOS:
        raise HTTPException(status_code=400, detail=f"aspect_ratio 只能是 {','.join(ASPECT_RATIOS)}")
    if resolution not in RESOLUTIONS:
        raise HTTPException(status_code=400, detail=f"resolution 只能是 {','.join(RESOLUTIONS)}")

    pre_derive = {
        "provider": provider,
        "model": config.get("model") or "gpt-image-1",
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
    }
    derived_size, derived_quality = derive_size_quality(pre_derive)

    normalized = {
        "provider": provider,
        "api_key": config.get("api_key", ""),
        "base_url": base_url,
        "model": config.get("model") or "gpt-image-1",
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "size": derived_size,
        "quality": derived_quality,
        "output_format": (config.get("output_format") or "png").strip().lower().lstrip("."),
    }
    if not normalized["api_key"] or normalized["api_key"] == "***":
        normalized["api_key"] = existing.get("api_key", "")
    if normalized["provider"] not in {"openai", "mirrorstages"}:
        raise HTTPException(status_code=400, detail="provider 只能是 openai/mirrorstages")
    if normalized["output_format"] not in {"png", "jpeg", "jpg", "webp"}:
        raise HTTPException(status_code=400, detail="output_format 只能是 png/jpeg/webp")
    if normalized["output_format"] == "jpg":
        normalized["output_format"] = "jpeg"
    return normalized


def _project_image_folder_name(filepath: str) -> str:
    normalized = os.path.normpath(filepath or "./output")
    name = os.path.basename(normalized)
    return re.sub(r'[\\/:*?"<>|]+', "_", name).strip("._ ") or "default"


def images_dir(filepath: str, group_by_project: bool = True) -> str:
    filepath = normalize_project_path(filepath or "./output", allow_blank=False)
    base = safe_join(filepath, "images")
    path = safe_join(base, _project_image_folder_name(filepath)) if group_by_project else base
    os.makedirs(path, exist_ok=True)
    return path


def image_prompt_queue_path(filepath: str) -> str:
    return os.path.join(images_dir(filepath), "prompt_queue.json")


def image_records_path(filepath: str) -> str:
    return os.path.join(images_dir(filepath), "generated_records.json")


def image_prompt_queue_legacy_path(filepath: str) -> str:
    filepath = normalize_project_path(filepath or "./output", allow_blank=False)
    return safe_join(filepath, "images", "prompt_queue.json")


def _read_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_prompt_item(item: dict[str, Any], index: int) -> dict[str, Any] | None:
    prompt = str(item.get("prompt") or item.get("prompt_positive") or "").strip()
    prompt = re.sub(r"^\*+\s*", "", prompt).strip()
    if not prompt:
        return None
    source_type = str(item.get("source_type") or "custom").strip() or "custom"
    source_id = str(item.get("source_id") or item.get("id") or f"prompt_{index}").strip() or f"prompt_{index}"
    title = str(item.get("title") or item.get("name") or source_id).strip() or source_id
    return {
        "id": f"{source_type}_{source_id}",
        "title": title,
        "prompt": prompt,
        "negative_prompt": re.sub(r"^\*+\s*", "", str(item.get("negative_prompt") or item.get("prompt_negative") or "").strip()).strip(),
        "source_type": source_type,
        "source_id": source_id,
        "source_label": str(item.get("source_label") or "").strip(),
        "status": str(item.get("status") or "pending").strip() or "pending",
    }


def list_image_prompt_queue(filepath: str) -> list[dict[str, Any]]:
    path = image_prompt_queue_path(filepath)
    legacy_path = image_prompt_queue_legacy_path(filepath)
    data = _read_json(path, [])
    if not data and legacy_path != path and os.path.exists(legacy_path):
        data = _read_json(legacy_path, [])
        if isinstance(data, list):
            _write_json(path, data)
    return data if isinstance(data, list) else []


def add_image_prompt_items(filepath: str, items: list[dict[str, Any]], replace: bool = False) -> list[dict[str, Any]]:
    existing = [] if replace else list_image_prompt_queue(filepath)
    by_id = {str(item.get("id")): item for item in existing if item.get("id")}
    for idx, item in enumerate(items, 1):
        normalized = normalize_prompt_item(item, idx)
        if not normalized:
            continue
        unique_id = normalized["id"]
        if unique_id in by_id:
            by_id[unique_id].update(normalized)
        else:
            by_id[unique_id] = normalized
    rows = list(by_id.values())
    _write_json(image_prompt_queue_path(filepath), rows)
    return rows


def delete_image_prompt_item(filepath: str, item_id: str) -> list[dict[str, Any]]:
    rows = list_image_prompt_queue(filepath)
    next_rows = [item for item in rows if str(item.get("id")) != item_id]
    if len(next_rows) == len(rows):
        raise HTTPException(status_code=404, detail="未找到待生成提示词")
    _write_json(image_prompt_queue_path(filepath), next_rows)
    return next_rows


def list_image_records(filepath: str) -> list[dict[str, Any]]:
    rows = _read_json(image_records_path(filepath), [])
    return rows if isinstance(rows, list) else []


def add_image_record(filepath: str, item: dict[str, Any]) -> list[dict[str, Any]]:
    rows = list_image_records(filepath)
    record = dict(item)
    record["id"] = record.get("id") or os.path.splitext(os.path.basename(str(record.get("path") or "")))[0]
    record["created_at"] = record.get("created_at") or datetime.now().isoformat(timespec="seconds")
    by_id = {str(row.get("id")): row for row in rows if row.get("id")}
    by_id[str(record["id"])] = record
    next_rows = sorted(by_id.values(), key=lambda row: str(row.get("created_at", "")), reverse=True)
    _write_json(image_records_path(filepath), next_rows)
    return next_rows


def delete_image_record(filepath: str, record_id: str = "", path: str = "", delete_file: bool = True) -> list[dict[str, Any]]:
    rows = list_image_records(filepath)
    root = os.path.abspath(images_dir(filepath))
    target_path = os.path.abspath(path) if path else ""
    if record_id and not target_path:
        for row in rows:
            if str(row.get("id")) == record_id:
                target_path = os.path.abspath(str(row.get("path") or ""))
                break
    next_rows = [
        row for row in rows
        if str(row.get("id")) != record_id and (not target_path or os.path.abspath(str(row.get("path") or "")) != target_path)
    ]
    if len(next_rows) == len(rows) and not target_path:
        raise HTTPException(status_code=404, detail="未找到生成记录")
    if delete_file and target_path:
        if os.path.commonpath([root, target_path]) != root:
            raise HTTPException(status_code=403, detail="不允许删除项目图片目录外的文件")
        if os.path.exists(target_path):
            os.remove(target_path)
    _write_json(image_records_path(filepath), next_rows)
    return next_rows


def image_file_url(path: str, download: bool = False) -> str:
    return f"/api/images/file?path={quote(path)}&download={'1' if download else '0'}"


def image_response_payload(path: str, prompt: str, config_name: str = "", config: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "path": path,
        "filename": os.path.basename(path),
        "url": image_file_url(path),
        "download_url": image_file_url(path, download=True),
        "prompt": prompt,
        "config_name": config_name,
    }
    if isinstance(config, dict):
        payload["model"] = config.get("model") or ""
        payload["size"] = config.get("size") or ""
        payload["provider"] = config.get("provider") or ""
    return payload


def safe_served_image_path(path: str) -> str:
    abs_path = os.path.abspath(path)
    root = os.path.abspath(os.getcwd())
    if os.path.commonpath([root, abs_path]) != root:
        raise HTTPException(status_code=403, detail="不允许访问项目目录外的图片")
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="图片不存在")
    if os.path.splitext(abs_path)[1].lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=400, detail="只支持预览 png/jpg/webp 图片")
    return abs_path


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


def extract_image_bytes(payload: Any) -> bytes | None:
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
                    image_bytes = extract_image_bytes(item)
                    if image_bytes:
                        return image_bytes
            elif isinstance(value, dict):
                image_bytes = extract_image_bytes(value)
                if image_bytes:
                    return image_bytes
            elif isinstance(value, str):
                image_bytes = _download_image_url(value)
                if image_bytes:
                    return image_bytes
        for value in payload.values():
            image_bytes = extract_image_bytes(value)
            if image_bytes:
                return image_bytes
    elif isinstance(payload, list):
        for item in payload:
            image_bytes = extract_image_bytes(item)
            if image_bytes:
                return image_bytes
    elif isinstance(payload, str):
        image_bytes = _decode_image_base64(payload)
        if image_bytes:
            return image_bytes
        return _download_image_url(payload)
    return None


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


def generate_image_bytes(config: dict[str, Any], prompt: str) -> bytes:
    provider = (config.get("provider") or "openai").strip().lower()
    if provider in {"openai", "mirrorstages"}:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise HTTPException(status_code=500, detail="缺少 openai 依赖，请先安装 requirements.txt") from exc

        api_key = config.get("api_key", "")
        if not api_key:
            raise HTTPException(status_code=400, detail="图片接口缺少 API Key")
        default_base_url = MIRRORSTAGES_OPENAI_BASE_URL if provider == "mirrorstages" else "https://api.openai.com/v1"
        base_url = normalize_mirrorstages_base_url(config.get("base_url") or default_base_url) if provider == "mirrorstages" else (config.get("base_url") or default_base_url)
        client = OpenAI(api_key=api_key, base_url=base_url)
        import time as _time
        _start = _time.time()
        try:
            response = client.images.generate(**_openai_image_params(config, prompt))
        except Exception as exc:
            provider_name = "MirrorStages" if provider == "mirrorstages" else "OpenAI"
            raise HTTPException(status_code=502, detail=f"{provider_name} 图片生成失败：{exc}") from exc
        payload = response.model_dump() if hasattr(response, "model_dump") else response
        _record_image_usage(provider, config, "generate", payload, _time.time() - _start)
        image_bytes = extract_image_bytes(payload)
        if not image_bytes:
            raise HTTPException(status_code=502, detail="图片接口未返回图片数据")
        return image_bytes

    raise HTTPException(status_code=400, detail="provider 只能是 openai/mirrorstages")


def _record_image_usage(provider: str, config: dict[str, Any], op: str, payload: Any, elapsed: float) -> None:
    """从图片接口响应里抽 usage 并上报；失败也按"按张计费"记一条 estimated。"""
    try:
        from api.usage_meter import record_usage
        usage = (payload or {}).get("usage") if isinstance(payload, dict) else None
        if isinstance(usage, dict) and any(usage.get(k) for k in ("total_tokens", "input_tokens", "output_tokens")):
            pt = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
            ct = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
            tt = int(usage.get("total_tokens") or (pt + ct))
            record_usage(
                kind="image",
                provider=str(provider or ""),
                config_name=str(config.get("config_name") or config.get("name") or ""),
                model=str(config.get("model") or ""),
                prompt_tokens=pt,
                completion_tokens=ct,
                total_tokens=tt,
                elapsed_ms=int(elapsed * 1000),
                source="exact",
                note=op,
            )
        else:
            # 没有 usage：按一次调用记一条，token 标 0，标记 missing
            record_usage(
                kind="image",
                provider=str(provider or ""),
                config_name=str(config.get("config_name") or config.get("name") or ""),
                model=str(config.get("model") or ""),
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                elapsed_ms=int(elapsed * 1000),
                source="missing",
                note=op,
            )
    except Exception:
        pass


def save_generated_image(
    config: dict[str, Any],
    prompt: str,
    filepath: str,
    source_type: str,
    source_id: str = "",
    group_by_project: bool = True,
) -> str:
    image_bytes = generate_image_bytes(config, prompt)
    ext = (config.get("output_format") or "png").lower().lstrip(".")
    if ext == "jpg":
        ext = "jpeg"
    safe_source = re.sub(r"[^A-Za-z0-9._-]+", "_", source_id or "custom").strip("_") or "custom"
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{source_type}_{safe_source}.{ext}"
    out_path = os.path.join(images_dir(filepath, group_by_project=group_by_project), filename)
    with open(out_path, "wb") as f:
        f.write(image_bytes)
    return out_path


def _openai_image_edit_params(config: dict[str, Any], prompt: str) -> dict[str, Any]:
    """与 _openai_image_params 类似，但只保留 edits 端点支持的参数。

    OpenAI / MirrorStages 的 /images/edits 都接受 model / prompt / image / n / size，
    OpenAI 还支持 mask / response_format / quality。
    """
    model = config.get("model") or "gpt-image-1"
    params: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "n": 1,
    }
    size = config.get("size") or "1024x1536"
    if size:
        params["size"] = size
    if model.startswith("gpt-image"):
        quality = config.get("quality")
        if quality:
            params["quality"] = quality
    else:
        params["response_format"] = "b64_json"
    return params


def edit_image_bytes(config: dict[str, Any], prompt: str, source_image_bytes: bytes, source_filename: str = "source.png") -> bytes:
    """对一张已有图片做文本提示编辑。两家厂商都走 OpenAI SDK 的 client.images.edit。"""
    provider = (config.get("provider") or "openai").strip().lower()
    if provider not in {"openai", "mirrorstages"}:
        raise HTTPException(status_code=400, detail="provider 只能是 openai/mirrorstages")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="缺少 openai 依赖，请先安装 requirements.txt") from exc

    api_key = config.get("api_key", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="图片接口缺少 API Key")
    default_base_url = MIRRORSTAGES_OPENAI_BASE_URL if provider == "mirrorstages" else "https://api.openai.com/v1"
    base_url = normalize_mirrorstages_base_url(config.get("base_url") or default_base_url) if provider == "mirrorstages" else (config.get("base_url") or default_base_url)
    client = OpenAI(api_key=api_key, base_url=base_url)

    # openai SDK 接受 (filename, BytesIO, mime) 元组作为 image 参数
    import io
    import mimetypes
    import time as _time
    mime, _ = mimetypes.guess_type(source_filename)
    image_tuple = (source_filename, io.BytesIO(source_image_bytes), mime or "image/png")
    params = _openai_image_edit_params(config, prompt)
    _start = _time.time()
    try:
        response = client.images.edit(image=image_tuple, **params)
    except Exception as exc:
        provider_name = "MirrorStages" if provider == "mirrorstages" else "OpenAI"
        raise HTTPException(status_code=502, detail=f"{provider_name} 图片编辑失败：{exc}") from exc
    payload = response.model_dump() if hasattr(response, "model_dump") else response
    _record_image_usage(provider, config, "edit", payload, _time.time() - _start)
    image_bytes = extract_image_bytes(payload)
    if not image_bytes:
        raise HTTPException(status_code=502, detail="图片编辑接口未返回图片数据")
    return image_bytes


def save_edited_image(
    config: dict[str, Any],
    prompt: str,
    source_image_bytes: bytes,
    source_filename: str,
    filepath: str,
    source_type: str = "edit",
    source_id: str = "",
    group_by_project: bool = True,
) -> str:
    image_bytes = edit_image_bytes(config, prompt, source_image_bytes, source_filename)
    ext = (config.get("output_format") or "png").lower().lstrip(".")
    if ext == "jpg":
        ext = "jpeg"
    safe_source = re.sub(r"[^A-Za-z0-9._-]+", "_", source_id or "edit").strip("_") or "edit"
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_edit_{safe_source}.{ext}"
    out_path = os.path.join(images_dir(filepath, group_by_project=group_by_project), filename)
    with open(out_path, "wb") as f:
        f.write(image_bytes)
    return out_path
