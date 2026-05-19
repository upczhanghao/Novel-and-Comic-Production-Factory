# api/routers/files.py
# -*- coding: utf-8 -*-
"""文件管理路由"""

import os
from fastapi import APIRouter, HTTPException
from api.security import normalize_project_path, safe_join
from utils import read_file

router = APIRouter(tags=["files"])

# 允许浏览的文件扩展名白名单
ALLOWED_EXTENSIONS = {".txt", ".json", ".md"}


@router.get("/files")
def list_files(filepath: str = "./output"):
    """列出项目目录下的文件树"""
    filepath = normalize_project_path(filepath, allow_blank=False)
    if not os.path.exists(filepath):
        return {"files": [], "filepath": filepath}

    result = []
    for root, dirs, files in os.walk(filepath):
        # Skip hidden dirs and __pycache__
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        for fname in sorted(files):
            if any(fname.endswith(ext) for ext in ALLOWED_EXTENSIONS):
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, filepath)
                size = os.path.getsize(full)
                result.append({
                    "path": rel,
                    "name": fname,
                    "size": size,
                    "directory": os.path.relpath(root, filepath),
                })
    return {"files": result, "filepath": filepath}


@router.get("/files/content")
def get_file_content(filepath: str = "./output", path: str = ""):
    """读取指定文件内容"""
    if not path:
        raise HTTPException(status_code=400, detail="path 参数不能为空")

    base = normalize_project_path(filepath, allow_blank=False)
    full = safe_join(base, path)

    ext = os.path.splitext(full)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=403, detail="不支持的文件类型")

    if not os.path.exists(full):
        raise HTTPException(status_code=404, detail=f"文件不存在: {path}")

    content = read_file(full)
    return {"path": path, "content": content}
