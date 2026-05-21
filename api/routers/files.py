# api/routers/files.py
# -*- coding: utf-8 -*-
"""文件管理路由：浏览/读/写/删除/批量下载/全文搜索/树视图。"""

import io
import os
import shutil
import zipfile
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.security import resolve_files_root, safe_join
from utils import read_file, save_string_to_txt

router = APIRouter(tags=["files"])

# 允许浏览的文件扩展名白名单
ALLOWED_EXTENSIONS = {".txt", ".json", ".md"}
# 隐藏目录（不返回也不递归）
SKIP_DIRS = {"__pycache__", "trash", ".git", ".cache", "vector_store"}
# 大小上限：避免一次性把超大文件塞进响应
MAX_READ_SIZE = 4 * 1024 * 1024   # 4MB
MAX_SEARCH_SIZE = 2 * 1024 * 1024  # 2MB


def _is_allowed(name: str) -> bool:
    return any(name.endswith(ext) for ext in ALLOWED_EXTENSIONS)


@router.get("/files")
def list_files(filepath: str = "./output"):
    """列出项目目录下的文件（扁平表）。"""
    filepath = resolve_files_root(filepath)
    if not os.path.exists(filepath):
        return {"files": [], "filepath": filepath}

    result = []
    for root, dirs, files in os.walk(filepath):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in SKIP_DIRS]
        for fname in sorted(files):
            if not _is_allowed(fname):
                continue
            full = os.path.join(root, fname)
            try:
                stat = os.stat(full)
            except OSError:
                continue
            rel = os.path.relpath(full, filepath)
            result.append({
                "path": rel.replace("\\", "/"),
                "name": fname,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "directory": os.path.relpath(root, filepath).replace("\\", "/"),
            })
    return {"files": result, "filepath": filepath}


@router.get("/files/tree")
def file_tree(filepath: str = "./output"):
    """以嵌套树的形式返回目录结构。"""
    filepath = resolve_files_root(filepath)
    if not os.path.exists(filepath):
        return {"tree": {"name": os.path.basename(filepath) or filepath, "path": "", "type": "dir", "children": []}, "filepath": filepath}

    def build(node_path: str, rel: str) -> dict:
        children: list[dict] = []
        try:
            entries = sorted(os.listdir(node_path))
        except OSError:
            entries = []
        for entry in entries:
            if entry.startswith(".") or entry in SKIP_DIRS:
                continue
            child_full = os.path.join(node_path, entry)
            child_rel = (rel + "/" + entry) if rel else entry
            if os.path.isdir(child_full):
                children.append(build(child_full, child_rel))
            else:
                if not _is_allowed(entry):
                    continue
                try:
                    stat = os.stat(child_full)
                except OSError:
                    continue
                children.append({
                    "name": entry,
                    "path": child_rel,
                    "type": "file",
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                })
        return {
            "name": os.path.basename(node_path) or node_path,
            "path": rel,
            "type": "dir",
            "children": children,
        }

    return {"tree": build(filepath, ""), "filepath": filepath}


@router.get("/files/recent")
def recent_files(filepath: str = "./output", limit: int = 20):
    """按修改时间倒序返回最近文件。"""
    data = list_files(filepath)
    files = sorted(data["files"], key=lambda f: f.get("mtime", 0), reverse=True)
    return {"files": files[: max(1, min(limit, 100))], "filepath": data["filepath"]}


@router.get("/files/content")
def get_file_content(filepath: str = "./output", path: str = ""):
    if not path:
        raise HTTPException(status_code=400, detail="path 参数不能为空")
    base = resolve_files_root(filepath)
    full = safe_join(base, path)

    ext = os.path.splitext(full)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=403, detail="不支持的文件类型")
    if not os.path.exists(full):
        raise HTTPException(status_code=404, detail=f"文件不存在: {path}")
    try:
        size = os.path.getsize(full)
    except OSError:
        size = 0
    if size > MAX_READ_SIZE:
        raise HTTPException(status_code=413, detail=f"文件过大无法直接预览（{size} bytes），请下载后查看")
    content = read_file(full)
    return {"path": path, "content": content, "size": size}


class FileWriteBody(BaseModel):
    filepath: str = "./output"
    path: str
    content: str


@router.put("/files/content")
def write_file_content(body: FileWriteBody):
    """编辑/覆盖已有文件内容（仅允许白名单后缀）。"""
    if not body.path:
        raise HTTPException(status_code=400, detail="path 不能为空")
    base = resolve_files_root(body.filepath)
    full = safe_join(base, body.path)
    ext = os.path.splitext(full)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=403, detail="不支持的文件类型")

    os.makedirs(os.path.dirname(full) or base, exist_ok=True)
    try:
        save_string_to_txt(body.content or "", full)
    except Exception:
        with open(full, "w", encoding="utf-8") as f:
            f.write(body.content or "")
    return {"message": f"✅ 已保存 {body.path}", "size": os.path.getsize(full)}


class FilesDeleteBody(BaseModel):
    filepath: str = "./output"
    paths: list[str]


@router.delete("/files/item")
def delete_file_item(filepath: str = Query("./output"), path: str = Query(...)):
    base = resolve_files_root(filepath)
    full = safe_join(base, path)
    if not os.path.exists(full):
        raise HTTPException(status_code=404, detail=f"不存在: {path}")
    if os.path.isdir(full):
        raise HTTPException(status_code=400, detail="该接口不支持删除目录")
    # 移动到 trash 而非直接删除
    trash_dir = os.path.join(os.path.dirname(base), "trash", os.path.basename(base))
    os.makedirs(trash_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(trash_dir, f"{timestamp}_{os.path.basename(full)}")
    try:
        shutil.move(full, dest)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")
    return {"message": f"✅ 已删除 {path}", "trash": dest}


@router.post("/files/batch-delete")
def batch_delete_files(body: FilesDeleteBody):
    base = resolve_files_root(body.filepath)
    trash_dir = os.path.join(os.path.dirname(base), "trash", os.path.basename(base))
    os.makedirs(trash_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ok, failed = [], []
    for p in body.paths:
        try:
            full = safe_join(base, p)
            if not os.path.isfile(full):
                failed.append({"path": p, "error": "不存在或非文件"})
                continue
            dest = os.path.join(trash_dir, f"{timestamp}_{os.path.basename(full)}")
            shutil.move(full, dest)
            ok.append(p)
        except Exception as e:
            failed.append({"path": p, "error": str(e)})
    return {
        "message": f"✅ 成功删除 {len(ok)}，失败 {len(failed)}",
        "ok": ok,
        "failed": failed,
    }


@router.get("/files/search")
def search_files(
    filepath: str = Query("./output"),
    query: str = Query(...),
    case_sensitive: bool = Query(False),
    limit: int = Query(200),
):
    """全文搜索：返回匹配文件、匹配次数、首个匹配片段。"""
    if not query.strip():
        raise HTTPException(status_code=400, detail="query 不能为空")
    base = resolve_files_root(filepath)
    if not os.path.isdir(base):
        return {"results": [], "query": query}

    needle = query if case_sensitive else query.lower()
    results = []
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in SKIP_DIRS]
        for fname in sorted(files):
            if not _is_allowed(fname):
                continue
            full = os.path.join(root, fname)
            try:
                if os.path.getsize(full) > MAX_SEARCH_SIZE:
                    continue
                with open(full, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            except OSError:
                continue
            haystack = text if case_sensitive else text.lower()
            idx = haystack.find(needle)
            if idx < 0:
                continue
            # 计算匹配次数
            count = haystack.count(needle)
            # 截取上下文
            start = max(0, idx - 40)
            end = min(len(text), idx + len(query) + 80)
            snippet = text[start:end].replace("\n", " ").strip()
            # 行号
            line_no = text[:idx].count("\n") + 1
            rel = os.path.relpath(full, base).replace("\\", "/")
            results.append({
                "path": rel,
                "matches": count,
                "snippet": snippet,
                "line": line_no,
            })
            if len(results) >= limit:
                break
        if len(results) >= limit:
            break
    return {"results": results, "query": query}


@router.get("/files/download")
def download_single_file(filepath: str = Query("./output"), path: str = Query(...)):
    base = resolve_files_root(filepath)
    full = safe_join(base, path)
    if not os.path.isfile(full):
        raise HTTPException(status_code=404, detail="文件不存在")
    if os.path.splitext(full)[1].lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=403, detail="不支持的文件类型")
    with open(full, "rb") as f:
        data = f.read()
    name = os.path.basename(full)
    from urllib.parse import quote
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"}
    return StreamingResponse(io.BytesIO(data), media_type="application/octet-stream", headers=headers)


class FilesArchiveBody(BaseModel):
    filepath: str = "./output"
    paths: Optional[list[str]] = None  # None 表示打包整个目录


@router.post("/files/archive")
def archive_files(body: FilesArchiveBody):
    """打包为 zip 并下载（流式）。"""
    base = resolve_files_root(body.filepath)
    if not os.path.isdir(base):
        raise HTTPException(status_code=404, detail="项目目录不存在")

    # 收集待打包文件
    targets: list[tuple[str, str]] = []  # (abs, arcname)
    if body.paths:
        for p in body.paths:
            full = safe_join(base, p)
            if os.path.isfile(full):
                targets.append((full, p))
            elif os.path.isdir(full):
                for root, dirs, files in os.walk(full):
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in SKIP_DIRS]
                    for fname in files:
                        if not _is_allowed(fname):
                            continue
                        f_abs = os.path.join(root, fname)
                        arc = os.path.relpath(f_abs, base).replace("\\", "/")
                        targets.append((f_abs, arc))
    else:
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in SKIP_DIRS]
            for fname in files:
                if not _is_allowed(fname):
                    continue
                f_abs = os.path.join(root, fname)
                arc = os.path.relpath(f_abs, base).replace("\\", "/")
                targets.append((f_abs, arc))

    if not targets:
        raise HTTPException(status_code=400, detail="没有可打包的文件")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for abs_path, arc in targets:
            try:
                zf.write(abs_path, arc)
            except OSError:
                continue
    buf.seek(0)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"{os.path.basename(base) or 'project'}_{timestamp}.zip"
    from urllib.parse import quote
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(archive_name)}"}
    return StreamingResponse(buf, media_type="application/zip", headers=headers)
