# api/routers/styles.py
# -*- coding: utf-8 -*-
"""文风 + 叙事DNA 路由"""

import os
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse

from api.schemas import (
    StyleAnalyzeRequest, StyleAnalyzeDNARequest,
    StyleMergeRequest, StyleSaveRequest, StyleCalibrateRequest,
)
from api.app_state import get_web_app
from api.sse_utils import run_with_sse

router = APIRouter(tags=["styles"])


def _sse_response(gen):
    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/styles")
def list_styles():
    app = get_web_app()
    return {"styles": app.list_styles()}


@router.post("/styles/analyze")
def analyze_style(body: StyleAnalyzeRequest):
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.analyze_style,
            body.llm_config_name, body.sample_text, body.style_name,
            body.unlock,
        ):
            yield chunk

    return _sse_response(_gen())


@router.post("/styles/analyze-dna")
def analyze_narrative_dna(body: StyleAnalyzeDNARequest):
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.analyze_narrative_dna,
            body.llm_config_name, body.sample_text, body.style_name,
            body.unlock,
        ):
            yield chunk

    return _sse_response(_gen())


@router.post("/styles/merge")
def merge_styles(body: StyleMergeRequest):
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.merge_styles,
            body.llm_config_name, body.selected_styles,
            body.merge_name, body.user_preference,
            body.unlock,
        ):
            yield chunk

    return _sse_response(_gen())


@router.post("/styles/calibrate")
def calibrate_style(body: StyleCalibrateRequest):
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.calibrate_style,
            body.llm_config_name, body.style_name, body.max_iterations,
            body.unlock,
        ):
            yield chunk

    return _sse_response(_gen())


@router.post("/styles/calibrate-narrative")
def calibrate_narrative(body: StyleCalibrateRequest):
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.calibrate_narrative,
            body.llm_config_name, body.style_name, body.max_iterations,
            body.unlock,
        ):
            yield chunk

    return _sse_response(_gen())


@router.get("/styles/{name}")
def get_style(name: str):
    app = get_web_app()
    instruction, analysis, msg = app.load_style(name)
    if msg.startswith("❌"):
        raise HTTPException(status_code=404, detail=msg)
    narrative = app.get_narrative_instructions(name)
    # 读取额外字段供前端展示/编辑
    import os, json
    style_file = os.path.join(app.get_styles_dir(), f"{name}.json")
    source_sample = ""
    calibration_reference = ""
    has_calibration_snapshot = False
    snapshot_timestamp = ""
    if os.path.exists(style_file):
        try:
            with open(style_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            source_sample = data.get("source_sample", "")
            calibration_reference = data.get("calibration_reference", "")
            snapshot = data.get("pre_calibration_snapshot")
            if snapshot:
                has_calibration_snapshot = True
                snapshot_timestamp = snapshot.get("timestamp", "")
        except (OSError, json.JSONDecodeError):
            # 文件损坏或无法读取时不阻塞主响应；前端编辑器仍可基于 instruction/analysis 渲染
            pass
    return {
        "style_name": name,
        "style_instruction": instruction,
        "analysis_result": analysis,
        "source_sample": source_sample,
        "calibration_reference": calibration_reference,
        "has_calibration_snapshot": has_calibration_snapshot,
        "snapshot_timestamp": snapshot_timestamp,
        "narrative_for_architecture": narrative.get("for_architecture", ""),
        "narrative_for_blueprint": narrative.get("for_blueprint", ""),
        "narrative_for_chapter": narrative.get("for_chapter", ""),
        "message": msg,
    }


@router.put("/styles/{name}")
def save_style(name: str, body: StyleSaveRequest):
    app = get_web_app()
    msg = app.save_style(
        name, body.analysis_result, body.style_instruction,
        source_sample=body.source_sample,
        calibration_reference=body.calibration_reference,
        narrative_for_architecture=body.narrative_for_architecture,
        narrative_for_blueprint=body.narrative_for_blueprint,
        narrative_for_chapter=body.narrative_for_chapter,
    )
    if msg.startswith("❌"):
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg}


@router.post("/styles/{name}/rollback-calibration")
def rollback_calibration(name: str):
    app = get_web_app()
    msg = app.rollback_calibration(name)
    if msg.startswith("❌"):
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg}


@router.delete("/styles/{name}")
def delete_style(name: str):
    app = get_web_app()
    _, msg = app.delete_style(name)
    if msg.startswith("❌"):
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg}


# ── 作者参考库（绑定到文风）──────────────────────────────────────────────────

from typing import Optional
from fastapi import Query
from api.library_helpers import resolve_embedding_adapter, author_ref_cfg
from api import library_service as lib


def _author_cfg(name: str):
    app = get_web_app()
    style_file = os.path.join(app.get_styles_dir(), f"{name}.json")
    if not os.path.exists(style_file):
        raise HTTPException(status_code=404, detail=f"❌ 文风「{name}」不存在")
    return author_ref_cfg(name, app.get_styles_dir())


@router.post("/styles/{name}/author-reference/import")
async def import_author_reference(
    name: str,
    emb_config_name: str = Form(""),
    file: UploadFile = File(...),
    tags: str = Form(""),
):
    app = get_web_app()
    cfg = _author_cfg(name)
    emb = resolve_embedding_adapter(app, emb_config_name)
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="❌ 上传的文件内容为空")
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    try:
        rec = lib.import_file(
            cfg, emb,
            file_bytes=file_bytes,
            original_filename=file.filename or "unknown.txt",
            tags=tag_list,
            author=name,
        )
        return {
            "message": f"✅ 已导入「{rec['filename']}」— {rec['chunks']} 个片段已索引",
            "record": rec,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"❌ 导入失败: {e}")


@router.get("/styles/{name}/author-reference/files")
def list_author_ref_files(name: str):
    return {"files": lib.list_files(_author_cfg(name))}


@router.get("/styles/{name}/author-reference/stats")
def author_ref_stats(name: str, emb_config_name: str = Query("")):
    app = get_web_app()
    cfg = _author_cfg(name)
    emb = None
    try:
        emb = resolve_embedding_adapter(app, emb_config_name)
    except HTTPException:
        pass
    return lib.stats(cfg, emb)


@router.delete("/styles/{name}/author-reference/files/{file_id}")
def delete_author_ref_file(name: str, file_id: str, emb_config_name: str = Query("")):
    app = get_web_app()
    emb = resolve_embedding_adapter(app, emb_config_name)
    try:
        rec = lib.delete_file(_author_cfg(name), emb, file_id)
        return {"message": f"✅ 已删除「{rec.get('filename', file_id)}」", "record": rec}
    except KeyError:
        raise HTTPException(status_code=404, detail="文件不存在")


@router.put("/styles/{name}/author-reference/files/{file_id}")
def update_author_ref_file(name: str, file_id: str, body: dict):
    try:
        rec = lib.update_metadata(
            _author_cfg(name), file_id,
            filename=body.get("filename"),
            tags=body.get("tags"),
            author=body.get("author"),
        )
        return {"message": "✅ 已更新", "record": rec}
    except KeyError:
        raise HTTPException(status_code=404, detail="文件不存在")


@router.post("/styles/{name}/author-reference/files/{file_id}/replace")
async def replace_author_ref_file(
    name: str, file_id: str,
    emb_config_name: str = Form(""),
    file: UploadFile = File(...),
):
    app = get_web_app()
    emb = resolve_embedding_adapter(app, emb_config_name)
    content_bytes = await file.read()
    try:
        rec = lib.replace_file(
            _author_cfg(name), emb,
            file_id=file_id,
            file_bytes=content_bytes,
            original_filename=file.filename,
        )
        return {"message": f"✅ 已替换「{rec['filename']}」— {rec['chunks']} 个片段", "record": rec}
    except KeyError:
        raise HTTPException(status_code=404, detail="文件不存在")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"❌ 替换失败: {e}")


@router.get("/styles/{name}/author-reference/search")
def search_author_ref(
    name: str,
    query: str = Query(...),
    emb_config_name: str = Query(""),
    k: int = Query(6),
    file_id: Optional[str] = Query(None),
):
    app = get_web_app()
    emb = resolve_embedding_adapter(app, emb_config_name)
    hits = lib.search(_author_cfg(name), emb, query=query, k=k, file_id=file_id)
    return {"hits": hits}


@router.get("/styles/{name}/author-reference/files/{file_id}/source")
def get_author_ref_source(name: str, file_id: str):
    text = lib.get_source_text(_author_cfg(name), file_id)
    if text is None:
        raise HTTPException(status_code=404, detail="源文件不存在")
    return {"text": text}


@router.delete("/styles/{name}/author-reference")
def clear_author_reference(name: str):
    lib.clear_library(_author_cfg(name))
    return {"message": f"✅ 文风「{name}」的作者参考库已清空"}


@router.post("/styles/{name}/author-reference/rebuild")
def rebuild_author_ref(name: str, body: dict):
    app = get_web_app()
    emb = resolve_embedding_adapter(app, body.get("emb_config_name", ""))
    result = lib.rebuild_library(_author_cfg(name), emb)
    return {"message": f"✅ 重建完成：成功 {result['ok']}，失败 {result['failed']}", **result}


@router.get("/styles/{name}/author-reference/status")
def author_reference_status(name: str):
    cfg = _author_cfg(name)
    s = lib.stats(cfg)
    return {
        "has_author_reference": s["exists"] and s["file_count"] > 0,
        "file_count": s["file_count"],
        "manifest_chunks": s["manifest_chunks"],
    }
