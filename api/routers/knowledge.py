# api/routers/knowledge.py
# -*- coding: utf-8 -*-
"""知识库路由 — 支持 per-file 管理、检索、重建"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from typing import Optional

from api.app_state import get_web_app
from api.security import normalize_project_path
from api.library_helpers import resolve_embedding_adapter, knowledge_cfg
from api import library_service as lib

router = APIRouter(tags=["knowledge"])


def _cfg(filepath: str):
    return knowledge_cfg(normalize_project_path(filepath, allow_blank=False))


# ── 导入 ─────────────────────────────────────────────────────────────────────

@router.post("/knowledge/import")
async def import_knowledge(
    emb_config_name: str = Form(""),
    filepath: str = Form(...),
    file: UploadFile = File(...),
    tags: str = Form(""),
):
    app = get_web_app()
    fp = normalize_project_path(filepath, allow_blank=False)
    emb = resolve_embedding_adapter(app, emb_config_name)
    content_bytes = await file.read()
    if not content_bytes:
        raise HTTPException(status_code=400, detail="❌ 上传的文件内容为空")

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    try:
        rec = lib.import_file(
            _cfg(fp), emb,
            file_bytes=content_bytes,
            original_filename=file.filename or "unknown.txt",
            tags=tag_list,
        )
        return {
            "message": f"✅ 已导入「{rec['filename']}」— {rec['chunks']} 个片段已索引",
            "record": rec,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"❌ 导入失败: {e}")


# ── 文件列表 ─────────────────────────────────────────────────────────────────

@router.get("/knowledge/files")
def list_knowledge_files(filepath: str = Query(...)):
    fp = normalize_project_path(filepath, allow_blank=False)
    return {"files": lib.list_files(_cfg(fp))}


# ── 统计 ─────────────────────────────────────────────────────────────────────

@router.get("/knowledge/stats")
def knowledge_stats(filepath: str = Query(...), emb_config_name: str = Query("")):
    app = get_web_app()
    fp = normalize_project_path(filepath, allow_blank=False)
    emb = None
    try:
        emb = resolve_embedding_adapter(app, emb_config_name)
    except HTTPException:
        pass
    return lib.stats(_cfg(fp), emb)


# ── 删除单文件 ───────────────────────────────────────────────────────────────

@router.delete("/knowledge/files/{file_id}")
def delete_knowledge_file(file_id: str, filepath: str = Query(...), emb_config_name: str = Query("")):
    app = get_web_app()
    fp = normalize_project_path(filepath, allow_blank=False)
    emb = resolve_embedding_adapter(app, emb_config_name)
    try:
        rec = lib.delete_file(_cfg(fp), emb, file_id)
        return {"message": f"✅ 已删除「{rec.get('filename', file_id)}」", "record": rec}
    except KeyError:
        raise HTTPException(status_code=404, detail="文件不存在")


# ── 重命名 / 改标签 ─────────────────────────────────────────────────────────

@router.put("/knowledge/files/{file_id}")
def update_knowledge_file(file_id: str, body: dict, filepath: str = Query(...)):
    fp = normalize_project_path(filepath, allow_blank=False)
    try:
        rec = lib.update_metadata(
            _cfg(fp), file_id,
            filename=body.get("filename"),
            tags=body.get("tags"),
            author=body.get("author"),
        )
        return {"message": "✅ 已更新", "record": rec}
    except KeyError:
        raise HTTPException(status_code=404, detail="文件不存在")


# ── 替换文件内容 ─────────────────────────────────────────────────────────────

@router.post("/knowledge/files/{file_id}/replace")
async def replace_knowledge_file(
    file_id: str,
    filepath: str = Form(...),
    emb_config_name: str = Form(""),
    file: UploadFile = File(...),
):
    app = get_web_app()
    fp = normalize_project_path(filepath, allow_blank=False)
    emb = resolve_embedding_adapter(app, emb_config_name)
    content_bytes = await file.read()
    try:
        rec = lib.replace_file(
            _cfg(fp), emb,
            file_id=file_id,
            file_bytes=content_bytes,
            original_filename=file.filename,
        )
        return {"message": f"✅ 已替换「{rec['filename']}」— {rec['chunks']} 个片段", "record": rec}
    except KeyError:
        raise HTTPException(status_code=404, detail="文件不存在")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"❌ 替换失败: {e}")


# ── 检索 ─────────────────────────────────────────────────────────────────────

@router.get("/knowledge/search")
def search_knowledge(
    filepath: str = Query(...),
    query: str = Query(...),
    emb_config_name: str = Query(""),
    k: int = Query(6),
    file_id: Optional[str] = Query(None),
):
    app = get_web_app()
    fp = normalize_project_path(filepath, allow_blank=False)
    emb = resolve_embedding_adapter(app, emb_config_name)
    hits = lib.search(_cfg(fp), emb, query=query, k=k, file_id=file_id)
    return {"hits": hits}


# ── 查看原文 ─────────────────────────────────────────────────────────────────

@router.get("/knowledge/files/{file_id}/source")
def get_source(file_id: str, filepath: str = Query(...)):
    fp = normalize_project_path(filepath, allow_blank=False)
    text = lib.get_source_text(_cfg(fp), file_id)
    if text is None:
        raise HTTPException(status_code=404, detail="源文件不存在")
    return {"text": text}


# ── 清空 ─────────────────────────────────────────────────────────────────────

@router.delete("/knowledge")
def clear_knowledge(filepath: str = Query(...)):
    fp = normalize_project_path(filepath, allow_blank=False)
    lib.clear_library(_cfg(fp))
    return {"message": "✅ 知识库已清空"}


# ── 重建索引 ─────────────────────────────────────────────────────────────────

@router.post("/knowledge/rebuild")
def rebuild_knowledge(body: dict):
    app = get_web_app()
    fp = normalize_project_path(body.get("filepath", ""), allow_blank=False)
    emb = resolve_embedding_adapter(app, body.get("emb_config_name", ""))
    result = lib.rebuild_library(_cfg(fp), emb)
    return {"message": f"✅ 重建完成：成功 {result['ok']}，失败 {result['failed']}", **result}
