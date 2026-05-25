# api/routers/manju/routes.py
# -*- coding: utf-8 -*-
"""All 22 FastAPI routes for the manju (漫剧) workflow."""

import json
import os
import re
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import Response, StreamingResponse

from api.app_state import get_web_app
from api.image_service import (
    add_image_prompt_items,
    add_image_record,
    image_response_payload,
    images_dir,
    normalize_image_config,
    save_generated_image,
)
from api.schemas import (
    ManjuCharactersUpdateRequest,
    ManjuGenerateRequest,
    ManjuImageGenerateRequest,
    ManjuImagePromptImportRequest,
    ManjuPromptEnhanceRequest,
    ManjuQueueCreateRequest,
    ManjuSettingsRequest,
    ManjuScriptAdaptRequest,
    ManjuShotRegenerateRequest,
    ManjuStoryboardUpdateRequest,
    ManjuStyleTemplateRequest,
)
from api.sse_utils import run_with_sse
from utils import save_string_to_txt

from .export import (
    _attachment_header,
    _content_export_path,
    _csv_response,
    _flatten_export_rows,
    _script_filename,
    _strip_old_script_boilerplate,
    _xlsx_response,
)
from .images import (
    _attach_image_urls,
    _manju_prompt_items,
    _resolve_image_prompt,
)
from .parser import (
    _chapter_window,
    _image_config_path,
    _load_chapters,
    _load_characters_structured,
    _load_settings,
    _load_storyboard_rows,
    _normalize_settings,
    _queue_path,
    _read_json,
    _read_text,
    _save_characters_structured,
    _save_storyboard_rows,
    _script_path,
    _settings_path,
    _work_dir,
    _write_json,
    _decode_upload,
    _parse_chapters,
)
from .pipeline import (
    _character_lock_context,
    _chunked,
    _generate_characters_sync,
    _generate_scenes_sync,
    _generate_storyboards_sync,
    _generate_script_adaptation_sync,
    _llm_adapter,
    _truncate,
)
from .parser import _style_templates_path
from .prompts import (
    _build_storyboard_image_prompt,
    _enhance_character_prompts,
    _enhance_storyboard_prompts,
    _load_style_templates,
    _quality_flags,
)

router = APIRouter(tags=["manju"])


def _sse_response(gen):
    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

@router.post("/manju/import")
async def import_novel_txt(filepath: str = Form("./output"), file: UploadFile = File(...)):
    raw = await file.read()
    text = _decode_upload(raw)
    if not text.strip():
        raise HTTPException(status_code=400, detail="上传的 TXT 内容为空")

    work_dir = _work_dir(filepath)
    source_file = os.path.join(work_dir, "source.txt")
    save_string_to_txt(text, source_file)

    chapters = _parse_chapters(text)
    _write_json(os.path.join(work_dir, "chapters.json"), chapters)
    meta = {
        "filename": file.filename,
        "imported_at": datetime.now().isoformat(timespec="seconds"),
        "chapter_count": len(chapters),
        "total_chars": len(text),
    }
    _write_json(os.path.join(work_dir, "meta.json"), meta)
    return {"message": "✅ 小说 TXT 已导入并解析章节", "meta": meta, "chapters": chapters}


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

@router.get("/manju/status")
def manju_status(filepath: str = "./output"):
    work_dir = _work_dir(filepath)
    image_config = _read_json(_image_config_path(filepath), {})
    safe_image_config = {**image_config, "api_key": "***"} if image_config.get("api_key") else image_config
    return {
        "meta": _read_json(os.path.join(work_dir, "meta.json"), None),
        "chapters": _load_chapters(filepath),
        "settings": _load_settings(filepath),
        "characters": _read_text(os.path.join(work_dir, "characters.md")) if os.path.exists(os.path.join(work_dir, "characters.md")) else "",
        "character_cards": _attach_image_urls(_load_characters_structured(filepath)),
        "script": _read_text(_script_path(filepath)) if os.path.exists(_script_path(filepath)) else "",
        "scenes": _read_text(os.path.join(work_dir, "scenes.md")) if os.path.exists(os.path.join(work_dir, "scenes.md")) else "",
        "storyboards": _read_text(os.path.join(work_dir, "storyboards.md")) if os.path.exists(os.path.join(work_dir, "storyboards.md")) else "",
        "storyboard_shots": _attach_image_urls(_load_storyboard_rows(filepath)),
        "style_templates": _load_style_templates(filepath),
        "image_config": safe_image_config,
        "queue": _read_json(_queue_path(filepath), []),
    }


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@router.put("/manju/settings")
def save_manju_settings(body: ManjuSettingsRequest):
    chapters = _load_chapters(body.filepath)
    settings = _normalize_settings(body.model_dump(exclude={"filepath"}), chapters)
    _write_json(_settings_path(body.filepath), settings)
    return {"message": "✅ 漫剧制作设置已保存", "settings": settings}


# ---------------------------------------------------------------------------
# Script
# ---------------------------------------------------------------------------

@router.post("/manju/script")
def generate_manju_script(body: ManjuScriptAdaptRequest):
    async def _gen():
        async for chunk in run_with_sse(
            _generate_script_adaptation_sync,
            body.llm_config_name, body.filepath, body.start_chapter, body.end_chapter,
            body.target_chapters, body.target_scenes, body.target_leads, body.target_supporting_cast,
            body.rename_characters, body.adaptation_level,
            body.episode_duration, body.script_style, body.extra_guidance,
        ):
            yield chunk
    return _sse_response(_gen())


@router.get("/manju/script/export")
def export_manju_script(filepath: str = "./output"):
    path = _script_path(filepath)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="暂无漫剧改编剧本，请先生成")
    content = _strip_old_script_boilerplate(_read_text(path))
    return Response(
        content=content.encode("utf-8-sig"),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": _attachment_header(_script_filename(filepath), "manju_script.txt")},
    )


# ---------------------------------------------------------------------------
# Characters structured
# ---------------------------------------------------------------------------

@router.put("/manju/characters/structured")
def save_structured_characters(body: ManjuCharactersUpdateRequest):
    _save_characters_structured(body.filepath, body.characters)
    return {"message": "✅ 角色一致性锁定表已保存", "characters": _load_characters_structured(body.filepath)}


# ---------------------------------------------------------------------------
# Storyboards structured
# ---------------------------------------------------------------------------

@router.put("/manju/storyboards/structured")
def save_structured_storyboards(body: ManjuStoryboardUpdateRequest):
    _save_storyboard_rows(body.filepath, body.shots)
    return {"message": "✅ 分镜表格已保存", "shots": _load_storyboard_rows(body.filepath)}


# ---------------------------------------------------------------------------
# Regenerate shot
# ---------------------------------------------------------------------------

@router.post("/manju/storyboards/regenerate-shot")
def regenerate_storyboard_shot(body: ManjuShotRegenerateRequest):
    rows = _load_storyboard_rows(body.filepath)
    target = next((row for row in rows if row.get("id") == body.shot_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="未找到该分镜")
    if target.get("locked"):
        raise HTTPException(status_code=400, detail="该分镜已锁定，不能重生成")
    chapters = _load_chapters(body.filepath)
    chapter = next((ch for ch in chapters if int(ch.get("num", 0)) == int(target.get("chapter_num", 0))), None)
    llm = _llm_adapter(body.llm_config_name)
    characters = _character_lock_context(body.filepath, manju_status(body.filepath).get("characters") or "")
    prompt = f"""你是漫剧分镜导演。请只重写一个分镜，不要改动其他分镜。

硬性要求：
1. 只输出 JSON，不要 Markdown，不要解释。
2. 保持 chapter_num、shot_no、id 不变。
3. 必须严格引用角色一致性锁定表，不能改变角色外貌、服装、道具连续性。
4. 输出字段（新版）：subject、引用场景、引用角色、camera、composition、prompt_positive、prompt_negative。
   - 其中 prompt_positive 是单段画面描述，必须按 A 段（Scene reference: SC-XXX + 复述场景）→ B 段（角色名 + 角色卡复述 + 动作/表情）→ C 段（镜头/构图/画质）三段拼接，末尾用 — 引出避免事项。
   - 引用场景 写 SC-XXX 编号或"临时场景"+一句具体地点+时段。
   - 引用角色 用、分隔。
   - 不要再输出 location、light、subtitle、continuity 这些已废弃字段。

角色一致性锁定表：
{_truncate(characters, 10000)}

全局视觉风格：
{body.visual_style or _load_settings(body.filepath).get("visual_style", "")}

补充要求：
{body.extra_guidance or _load_settings(body.filepath).get("extra_guidance", "")}

原分镜数据：
{json.dumps(target, ensure_ascii=False, indent=2)}

章节内容：
第{target.get('chapter_num')}章 {target.get('chapter_title', '')}
{_truncate(chapter.get('content', '') if chapter else '', 12000)}
"""
    from novel_generator.common import invoke_with_cleaning
    result = invoke_with_cleaning(llm, prompt, enable_streaming=False)
    text = result.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        patch = json.loads(text)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="LLM 未返回合法 JSON，请稍后重试")
    # 字段名规范化：支持 LLM 写中文 "引用场景"/"引用角色" 或 location/characters
    key_aliases = {
        "引用场景": "location",
        "引用角色": "characters",
        "scene_ref": "location",
    }
    for raw_key, value in list(patch.items()):
        target_key = key_aliases.get(raw_key, raw_key)
        if target_key in {"subject", "characters", "camera", "composition", "location",
                          "light", "subtitle", "prompt_positive", "prompt_negative", "continuity"}:
            target[target_key] = value
    target["status"] = "regenerated"
    _save_storyboard_rows(body.filepath, rows)
    return {"message": "✅ 分镜已重生成", "shot": target, "shots": rows}


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

@router.get("/manju/styles")
def list_style_templates(filepath: str = "./output"):
    return {"templates": _load_style_templates(filepath)}


@router.post("/manju/styles")
def save_style_template(body: ManjuStyleTemplateRequest):
    custom = _read_json(_style_templates_path(body.filepath), [])
    if not isinstance(custom, list):
        custom = []
    custom = [item for item in custom if item.get("name") != body.name]
    custom.append({
        "name": body.name,
        "visual_style": body.visual_style,
        "extra_guidance": body.extra_guidance,
    })
    _write_json(_style_templates_path(body.filepath), custom)
    return {"message": "✅ 美术风格模板已保存", "templates": _load_style_templates(body.filepath)}


# ---------------------------------------------------------------------------
# Export content (md/txt download)
# ---------------------------------------------------------------------------

@router.get("/manju/export-content")
def export_manju_prompt_content(filepath: str = "./output", kind: str = "characters", format: str = "md"):
    path, label = _content_export_path(filepath, kind)
    content = _read_text(path)
    ext = "txt" if format == "txt" else "md"
    return Response(
        content=content.encode("utf-8-sig"),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": _attachment_header(f"{label}.{ext}", f"{kind}.{ext}")},
    )


# ---------------------------------------------------------------------------
# Image prompts import
# ---------------------------------------------------------------------------

@router.post("/manju/image-prompts/import")
def import_manju_prompts_to_images(body: ManjuImagePromptImportRequest):
    items = _manju_prompt_items(body.filepath, body.kind, body.shot_ids)
    if not items:
        raise HTTPException(status_code=404, detail="暂无可导入的图片提示词，请先生成对应内容")
    rows = add_image_prompt_items(body.filepath, items, body.replace)
    return {
        "message": f"✅ 已导入图片生成模块：本次 {len(items)} 条，队列共 {len(rows)} 条",
        "items": rows,
        "imported": len(items),
        "count": len(rows),
    }


# ---------------------------------------------------------------------------
# Prompts enhance
# ---------------------------------------------------------------------------

@router.post("/manju/prompts/enhance")
def enhance_manju_prompts(body: ManjuPromptEnhanceRequest):
    changed = 0
    result: dict[str, Any] = {}
    if body.kind in ("characters", "all"):
        count, cards = _enhance_character_prompts(body.filepath, body.overwrite_locked)
        changed += count
        result["characters"] = cards
    if body.kind in ("storyboards", "all"):
        count, rows = _enhance_storyboard_prompts(body.filepath, body.overwrite_locked)
        changed += count
        result["storyboards"] = rows
    if body.kind not in ("characters", "storyboards", "all"):
        raise HTTPException(status_code=400, detail="kind 只能是 characters/storyboards/all")
    return {
        "message": f"✅ 已增强 {changed} 条生图提示词",
        "changed": changed,
        **result,
    }


# ---------------------------------------------------------------------------
# Export assets (json/csv/xlsx)
# ---------------------------------------------------------------------------

@router.get("/manju/export")
def export_manju_assets(filepath: str = "./output", kind: str = "storyboards", format: str = "json"):
    rows = _flatten_export_rows(kind, filepath)
    filename = f"manju_{kind}"
    if format == "json":
        return Response(
            content=json.dumps(rows, ensure_ascii=False, indent=2),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
        )
    if format == "csv":
        return _csv_response(rows, filename)
    if format in ("xlsx", "excel"):
        return _xlsx_response(rows, filename)
    raise HTTPException(status_code=400, detail="format 只能是 json/csv/xlsx")


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/manju/stats")
def manju_stats(filepath: str = "./output"):
    cards = _load_characters_structured(filepath)
    rows = _load_storyboard_rows(filepath)
    names = [c.get("name", "") for c in cards if c.get("name")]
    appearances = {name: 0 for name in names}
    links: dict[str, int] = {}
    for row in rows:
        text = " ".join(str(row.get(key, "")) for key in ("characters", "subject", "prompt_positive", "continuity"))
        present = [name for name in names if name and name in text]
        for name in present:
            appearances[name] = appearances.get(name, 0) + 1
        for i, left in enumerate(present):
            for right in present[i + 1:]:
                key = "｜".join(sorted([left, right]))
                links[key] = links.get(key, 0) + 1
    return {
        "appearances": [{"name": k, "count": v} for k, v in sorted(appearances.items(), key=lambda x: x[1], reverse=True)],
        "relations": [{"source": k.split("｜")[0], "target": k.split("｜")[1], "count": v} for k, v in sorted(links.items(), key=lambda x: x[1], reverse=True)],
    }


# ---------------------------------------------------------------------------
# Continuity check
# ---------------------------------------------------------------------------

@router.get("/manju/continuity-check")
def continuity_check(filepath: str = "./output"):
    cards = _load_characters_structured(filepath)
    rows = sorted(_load_storyboard_rows(filepath), key=lambda r: (int(r.get("chapter_num") or 0), int(r.get("shot_no") or 0)))
    issues = []
    card_names = {c.get("name") for c in cards if c.get("name")}
    locked_names = {c.get("name") for c in cards if c.get("name") and c.get("locked", True)}
    prev = None
    import re as _re
    light_pattern = _re.compile(r"(light|lighting|sun|moon|lamp|candle|fire|backlit|rim light|key light|3000K|5500K|6500K|warm|cool|阳光|月光|烛火|霓虹|暖光|冷光|侧光|顶光|逆光|侧逆光|晨|昏|夜|雨|雪|雾)", _re.IGNORECASE)
    for row in rows:
        ref_text = " ".join(str(row.get(key, "")) for key in ("characters", "subject", "prompt_positive", "continuity"))
        mentioned = {name for name in card_names if name and name in ref_text}
        prompt_positive = str(row.get("prompt_positive", ""))
        has_location = bool(row.get("location")) or "Scene reference" in prompt_positive or "SC-" in prompt_positive
        has_light = bool(row.get("light")) or bool(light_pattern.search(prompt_positive))
        if not has_location:
            issues.append({"level": "warning", "shot_id": row.get("id"), "message": "缺少背景场景/地点，后续画面连续性较弱"})
        if not has_light:
            issues.append({"level": "warning", "shot_id": row.get("id"), "message": "缺少光影色彩/时间信息"})
        user_prompt = prompt_positive
        user_negative = str(row.get("prompt_negative", ""))
        if user_prompt:
            for flag in _quality_flags(user_prompt, user_negative):
                issues.append({"level": "warning", "shot_id": row.get("id"), "message": f"生图提示词{flag}"})
        else:
            prompt, negative = _build_storyboard_image_prompt(filepath, row)
            for flag in _quality_flags(prompt, negative):
                issues.append({"level": "warning", "shot_id": row.get("id"), "message": f"生图提示词{flag}"})
        for name in mentioned - locked_names:
            issues.append({"level": "warning", "shot_id": row.get("id"), "message": f"角色“{name}”未锁定，可能发生外貌漂移"})
        if prev and row.get("chapter_num") == prev.get("chapter_num"):
            if prev.get("location") and row.get("location") and prev.get("location") != row.get("location"):
                continuity = str(row.get("continuity", ""))
                if not any(word in continuity for word in ("转场", "切到", "来到", "进入", "离开")):
                    issues.append({"level": "info", "shot_id": row.get("id"), "message": "地点较上一镜变化，但连续性备注未说明转场"})
        prev = row
    return {"issues": issues, "issue_count": len(issues)}


# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------

@router.post("/manju/queue")
def create_chapter_queue(body: ManjuQueueCreateRequest):
    chapters = _chapter_window(_load_chapters(body.filepath), body.start_chapter, body.end_chapter)
    chunk_size = max(1, min(int(body.chunk_size or 5), 50))
    queue = []
    for idx, chunk in enumerate(_chunked(chapters, chunk_size), 1):
        queue.append({
            "id": f"batch_{idx}",
            "start_chapter": chunk[0]["num"],
            "end_chapter": chunk[-1]["num"],
            "status": "pending",
            "attempts": 0,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        })
    _write_json(_queue_path(body.filepath), queue)
    return {"message": "✅ 章节批量队列已创建", "queue": queue}


@router.put("/manju/queue/{batch_id}")
def update_chapter_queue(batch_id: str, filepath: str = "./output", status: str = "pending"):
    queue = _read_json(_queue_path(filepath), [])
    if not isinstance(queue, list):
        queue = []
    for item in queue:
        if item.get("id") == batch_id:
            item["status"] = status
            item["updated_at"] = datetime.now().isoformat(timespec="seconds")
            if status == "retry":
                item["status"] = "pending"
                item["attempts"] = int(item.get("attempts", 0)) + 1
    _write_json(_queue_path(filepath), queue)
    return {"message": "✅ 队列状态已更新", "queue": queue}


# ---------------------------------------------------------------------------
# Image generation
# ---------------------------------------------------------------------------

@router.post("/manju/images/generate")
def generate_manju_image(body: ManjuImageGenerateRequest):
    if body.image_config_name:
        app = get_web_app()
        config = app.config.get("image_configs", {}).get(body.image_config_name, {})
    else:
        config = _read_json(_image_config_path(body.filepath), {})
    if not config:
        raise HTTPException(status_code=400, detail="请先在模型配置中保存图片生成配置")
    provider = (body.provider or config.get("provider", "openai")).strip().lower()
    if body.provider:
        config = {**config, "provider": provider}
    # 注入 config_name 给 _record_image_usage 上报用
    if body.image_config_name and "config_name" not in config:
        config = {**config, "config_name": body.image_config_name}
    prompt = _resolve_image_prompt(body)
    config = normalize_image_config(config)
    # A4: 与 ImageView 派发共用 images_dir(filepath) 而非 manju 工作目录，
    # 让分镜图自动出现在 RecordsTab。
    out_path = save_generated_image(
        config,
        prompt,
        body.filepath,
        body.source_type,
        body.source_id,
    )
    rel_path = os.path.relpath(out_path, images_dir(body.filepath))
    if body.source_type == "shot" and body.source_id:
        rows = _load_storyboard_rows(body.filepath)
        for row in rows:
            if row.get("id") == body.source_id:
                row["image_path"] = out_path
                row["image_relative_path"] = rel_path
                row["image_url"] = image_response_payload(out_path, prompt, body.image_config_name).get("url")
                row["image_download_url"] = image_response_payload(out_path, prompt, body.image_config_name).get("download_url")
        _save_storyboard_rows(body.filepath, rows)
    if body.source_type == "character" and body.source_id:
        cards = _load_characters_structured(body.filepath)
        for card in cards:
            if card.get("id") == body.source_id or card.get("name") == body.source_id:
                card["image_path"] = out_path
                card["image_relative_path"] = rel_path
                card["image_url"] = image_response_payload(out_path, prompt, body.image_config_name).get("url")
                card["image_download_url"] = image_response_payload(out_path, prompt, body.image_config_name).get("download_url")
        _save_characters_structured(body.filepath, cards)
    payload = image_response_payload(out_path, prompt, body.image_config_name)
    add_image_record(body.filepath, {
        **payload,
        "id": os.path.splitext(os.path.basename(out_path))[0],
        "source_type": body.source_type,
        "source_id": body.source_id,
    })
    return {"message": "✅ 图片已生成", **payload, "relative_path": rel_path}


# ---------------------------------------------------------------------------
# Generate characters / scenes / storyboards (SSE)
# ---------------------------------------------------------------------------

@router.post("/manju/characters")
def generate_characters(body: ManjuGenerateRequest):
    async def _gen():
        async for chunk in run_with_sse(
            _generate_characters_sync,
            body.llm_config_name, body.filepath, body.start_chapter, body.end_chapter,
            body.visual_style, body.extra_guidance, body.full_scan,
        ):
            yield chunk
    return _sse_response(_gen())


@router.post("/manju/scenes")
def generate_scenes(body: ManjuGenerateRequest):
    async def _gen():
        async for chunk in run_with_sse(
            _generate_scenes_sync,
            body.llm_config_name, body.filepath, body.start_chapter, body.end_chapter,
            body.visual_style, body.extra_guidance, body.full_scan,
        ):
            yield chunk
    return _sse_response(_gen())


@router.post("/manju/storyboards")
def generate_storyboards(body: ManjuGenerateRequest):
    async def _gen():
        async for chunk in run_with_sse(
            _generate_storyboards_sync,
            body.llm_config_name, body.filepath, body.start_chapter, body.end_chapter,
            body.shots_per_chapter, body.visual_style, body.extra_guidance,
        ):
            yield chunk
    return _sse_response(_gen())
