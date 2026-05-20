# api/routers/images.py
# -*- coding: utf-8 -*-
"""独立图片生成模块。"""

import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from api.app_state import get_web_app
from api.image_service import (
    add_image_record,
    add_image_prompt_items,
    delete_image_prompt_item,
    delete_image_record,
    image_response_payload,
    images_dir,
    list_image_records,
    list_image_prompt_queue,
    save_generated_image,
    safe_served_image_path,
)
from api.schemas import ImageGenerateRequest, ImagePromptImportRequest
from api.security import normalize_project_path

router = APIRouter(tags=["images"])


def _get_image_config(config_name: str) -> dict:
    app = get_web_app()
    configs = app.config.get("image_configs", {})
    config = configs.get(config_name)
    if not config:
        raise HTTPException(status_code=400, detail=f"未找到图片生成配置：{config_name}")
    return config


@router.post("/images/generate")
def generate_image(body: ImageGenerateRequest):
    prompt = body.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="提示词不能为空")
    config = _get_image_config(body.config_name)
    out_path = save_generated_image(config, prompt, body.filepath, body.source_type, body.source_id)
    payload = {
        **image_response_payload(out_path, prompt, body.config_name, config),
        "id": os.path.splitext(os.path.basename(out_path))[0],
        "source_type": body.source_type,
        "source_id": body.source_id,
    }
    add_image_record(body.filepath, payload)
    return {"message": "✅ 图片已生成", **payload}


@router.get("/images/list")
def list_images(filepath: str = "./output"):
    filepath = normalize_project_path(filepath, allow_blank=False)
    root = images_dir(filepath)
    rows_by_path: dict[str, dict] = {}

    for record in list_image_records(filepath):
        path = str(record.get("path") or "")
        if not path or not os.path.exists(path):
            continue
        stat = os.stat(path)
        payload = image_response_payload(path, str(record.get("prompt") or ""), str(record.get("config_name") or ""))
        payload.update(record)
        payload.update({
            "id": str(record.get("id") or os.path.splitext(os.path.basename(path))[0]),
            "filename": os.path.basename(path),
            "url": image_response_payload(path, "", "").get("url"),
            "download_url": image_response_payload(path, "", "").get("download_url"),
            "size": stat.st_size,
            "mtime": stat.st_mtime,
        })
        rows_by_path[os.path.abspath(path)] = payload

    for filename in sorted(os.listdir(root), reverse=True):
        path = os.path.join(root, filename)
        if not os.path.isfile(path) or os.path.splitext(filename)[1].lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        abs_path = os.path.abspath(path)
        if abs_path in rows_by_path:
            continue
        stat = os.stat(path)
        rows_by_path[abs_path] = {
            **image_response_payload(path, "", ""),
            "id": os.path.splitext(filename)[0],
            "created_at": "",
            "size": stat.st_size,
            "mtime": stat.st_mtime,
        }

    rows = sorted(rows_by_path.values(), key=lambda item: float(item.get("mtime") or 0), reverse=True)
    for row in rows:
        add_image_record(filepath, row)
    return {"images": rows, "save_dir": root}


@router.get("/images/prompts")
def list_image_prompts(filepath: str = "./output"):
    filepath = normalize_project_path(filepath, allow_blank=False)
    return {"items": list_image_prompt_queue(filepath), "save_dir": images_dir(filepath)}


@router.post("/images/prompts/import")
def import_image_prompts(body: ImagePromptImportRequest):
    rows = add_image_prompt_items(body.filepath, body.items, body.replace)
    return {
        "message": f"✅ 已导入 {len(body.items)} 条图片提示词",
        "items": rows,
        "count": len(rows),
        "save_dir": images_dir(body.filepath),
    }


@router.delete("/images/prompts/{item_id}")
def delete_image_prompt(item_id: str, filepath: str = "./output"):
    filepath = normalize_project_path(filepath, allow_blank=False)
    rows = delete_image_prompt_item(filepath, item_id)
    return {"message": "✅ 已删除待生成提示词", "items": rows, "count": len(rows), "save_dir": images_dir(filepath)}


@router.delete("/images/records/{record_id}")
def delete_generated_image_record(record_id: str, filepath: str = "./output", delete_file: bool = True):
    filepath = normalize_project_path(filepath, allow_blank=False)
    rows = delete_image_record(filepath, record_id=record_id, delete_file=delete_file)
    return {"message": "✅ 已删除生成记录", "items": rows, "count": len(rows), "save_dir": images_dir(filepath)}


@router.post("/images/records/batch-delete")
def batch_delete_generated_image_records(body: dict):
    filepath = normalize_project_path(str(body.get("filepath") or "./output"), allow_blank=False)
    ids = [str(x) for x in (body.get("ids") or []) if str(x).strip()]
    delete_file = bool(body.get("delete_file", True))
    if not ids:
        raise HTTPException(status_code=400, detail="未提供要删除的记录")
    rows: list = []
    failed: list[str] = []
    for record_id in ids:
        try:
            rows = delete_image_record(filepath, record_id=record_id, delete_file=delete_file)
        except HTTPException:
            failed.append(record_id)
    return {
        "message": f"✅ 已删除 {len(ids) - len(failed)} 条生成记录" + (f"，{len(failed)} 条未找到" if failed else ""),
        "items": rows,
        "count": len(rows),
        "failed": failed,
        "save_dir": images_dir(filepath),
    }


@router.post("/images/prompts/batch-delete")
def batch_delete_image_prompts(body: dict):
    filepath = normalize_project_path(str(body.get("filepath") or "./output"), allow_blank=False)
    ids = [str(x) for x in (body.get("ids") or []) if str(x).strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="未提供要删除的提示词")
    rows: list = []
    failed: list[str] = []
    for item_id in ids:
        try:
            rows = delete_image_prompt_item(filepath, item_id)
        except HTTPException:
            failed.append(item_id)
    return {
        "message": f"✅ 已删除 {len(ids) - len(failed)} 条提示词" + (f"，{len(failed)} 条未找到" if failed else ""),
        "items": rows,
        "count": len(rows),
        "failed": failed,
        "save_dir": images_dir(filepath),
    }


@router.get("/images/file")
def get_image_file(path: str, download: bool = False):
    abs_path = safe_served_image_path(path)
    return FileResponse(
        abs_path,
        filename=os.path.basename(abs_path),
        media_type=None,
        headers={"Content-Disposition": f'{"attachment" if download else "inline"}; filename="{os.path.basename(abs_path)}"'},
    )
