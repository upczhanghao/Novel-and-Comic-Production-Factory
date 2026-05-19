# api/routers/images.py
# -*- coding: utf-8 -*-
"""独立图片生成模块。"""

import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from api.app_state import get_web_app
from api.image_service import (
    add_image_prompt_items,
    image_response_payload,
    images_dir,
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
    return {"message": "✅ 图片已生成", **image_response_payload(out_path, prompt, body.config_name)}


@router.get("/images/list")
def list_images(filepath: str = "./output"):
    filepath = normalize_project_path(filepath, allow_blank=False)
    root = images_dir(filepath)
    rows = []
    for filename in sorted(os.listdir(root), reverse=True):
        path = os.path.join(root, filename)
        if not os.path.isfile(path) or os.path.splitext(filename)[1].lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        stat = os.stat(path)
        rows.append({
            **image_response_payload(path, "", ""),
            "size": stat.st_size,
            "mtime": stat.st_mtime,
        })
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


@router.get("/images/file")
def get_image_file(path: str, download: bool = False):
    abs_path = safe_served_image_path(path)
    return FileResponse(
        abs_path,
        filename=os.path.basename(abs_path),
        media_type=None,
        headers={"Content-Disposition": f'{"attachment" if download else "inline"}; filename="{os.path.basename(abs_path)}"'},
    )
