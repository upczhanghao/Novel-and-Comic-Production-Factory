# api/routers/manju.py
# -*- coding: utf-8 -*-
"""漫剧制作路由：TXT 导入、章节解析、角色卡/场景/分镜提示词生成。"""

import base64
import csv
import io
import json
import os
import re
import zipfile
from datetime import datetime
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import Response, StreamingResponse
import requests

from api.app_state import get_web_app
from api.image_service import (
    add_image_prompt_items,
    image_response_payload,
    normalize_image_config,
    save_generated_image,
)
from api.security import normalize_project_path, safe_join
from api.schemas import (
    ManjuCharactersUpdateRequest,
    ManjuGenerateRequest,
    ManjuImageConfigRequest,
    ManjuImageGenerateRequest,
    ManjuImagePromptImportRequest,
    ManjuQueueCreateRequest,
    ManjuSettingsRequest,
    ManjuScriptAdaptRequest,
    ManjuShotRegenerateRequest,
    ManjuStoryboardUpdateRequest,
    ManjuStyleTemplateRequest,
)
from api.sse_utils import run_with_sse
from llm_adapters import create_llm_adapter
from novel_generator.common import invoke_with_cleaning
from utils import save_string_to_txt

router = APIRouter(tags=["manju"])


def _sse_response(gen):
    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _work_dir(filepath: str) -> str:
    filepath = normalize_project_path(filepath or "./output", allow_blank=False)
    path = safe_join(filepath, "manju")
    os.makedirs(path, exist_ok=True)
    return path


def _characters_json_path(filepath: str) -> str:
    return os.path.join(_work_dir(filepath), "characters.json")


def _storyboards_json_path(filepath: str) -> str:
    return os.path.join(_work_dir(filepath), "storyboards.json")


def _image_config_path(filepath: str) -> str:
    return os.path.join(_work_dir(filepath), "image_config.json")


def _style_templates_path(filepath: str) -> str:
    return os.path.join(_work_dir(filepath), "style_templates.json")


def _queue_path(filepath: str) -> str:
    return os.path.join(_work_dir(filepath), "queue.json")


def _script_path(filepath: str) -> str:
    return os.path.join(_work_dir(filepath), "manju_script.txt")


def _script_outline_path(filepath: str) -> str:
    return os.path.join(_work_dir(filepath), "manju_script_outline.txt")


def _images_dir(filepath: str) -> str:
    path = safe_join(_work_dir(filepath), "images")
    os.makedirs(path, exist_ok=True)
    return path


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _read_json(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _decode_upload(data: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "gb18030", "gbk", "big5"):
        try:
            text = data.decode(enc)
            if text.strip():
                return text
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _parse_chapters(text: str) -> list[dict[str, Any]]:
    pattern = re.compile(
        r"(?m)^\s*(第\s*[零〇一二三四五六七八九十百千万\d]+\s*[章节回集卷部篇][^\n]{0,80}|Chapter\s+\d+[^\n]{0,80})\s*$",
        re.IGNORECASE,
    )
    matches = list(pattern.finditer(text))
    if not matches:
        title = "全文"
        return [{"num": 1, "title": title, "content": text.strip(), "chars": len(text.strip())}]

    chapters = []
    preface = text[:matches[0].start()].strip()
    if preface:
        chapters.append({"num": 1, "title": "序章/引子", "content": preface, "chars": len(preface)})

    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        title = re.sub(r"\s+", " ", match.group(1)).strip()
        content = text[start:end].strip()
        if content:
            chapters.append({
                "num": len(chapters) + 1,
                "title": title,
                "content": content,
                "chars": len(content),
            })
    return chapters


def _chapter_window(chapters: list[dict[str, Any]], start: int, end: int | None) -> list[dict[str, Any]]:
    if not chapters:
        raise HTTPException(status_code=400, detail="请先导入小说 TXT")
    real_end = end or len(chapters)
    if start < 1 or real_end < start:
        raise HTTPException(status_code=400, detail="章节范围不合法")
    return [c for c in chapters if start <= int(c["num"]) <= real_end]


def _load_chapters(filepath: str) -> list[dict[str, Any]]:
    data = _read_json(os.path.join(_work_dir(filepath), "chapters.json"), [])
    return data if isinstance(data, list) else []


def _settings_path(filepath: str) -> str:
    return os.path.join(_work_dir(filepath), "settings.json")


def _normalize_settings(settings: dict[str, Any], chapters: list[dict[str, Any]]) -> dict[str, Any]:
    chapter_count = len(chapters)
    start = int(settings.get("start_chapter") or 1)
    end_value = settings.get("end_chapter")
    end = int(end_value) if end_value else (chapter_count or start)
    if chapter_count:
        start = max(1, min(start, chapter_count))
        end = max(start, min(end, chapter_count))
    else:
        start = max(1, start)
        end = max(start, end)
    shots = max(1, min(int(settings.get("shots_per_chapter") or 12), 80))
    return {
        "llm_config_name": settings.get("llm_config_name", ""),
        "start_chapter": start,
        "end_chapter": end,
        "shots_per_chapter": shots,
        "visual_style": settings.get("visual_style")
        or "国漫竖屏短剧，电影级构图，统一角色设定，高细节，适合文生图",
        "extra_guidance": settings.get("extra_guidance", ""),
    }


def _load_settings(filepath: str) -> dict[str, Any]:
    return _normalize_settings(_read_json(_settings_path(filepath), {}), _load_chapters(filepath))


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


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    head = text[: int(limit * 0.65)]
    tail = text[-int(limit * 0.25):]
    return f"{head}\n\n……【中间内容已压缩省略】……\n\n{tail}"


def _chapter_digest(chapters: list[dict[str, Any]], per_chapter_chars: int = 1200) -> str:
    parts = []
    for ch in chapters:
        parts.append(
            f"【第{ch['num']}章：{ch['title']}】\n{_truncate(ch.get('content', ''), per_chapter_chars)}"
        )
    return "\n\n".join(parts)


def _chapter_digest_balanced(chapters: list[dict[str, Any]], total_chars: int = 32000) -> str:
    """给每章分配相近摘录长度，避免长篇只保留开头和结尾。"""
    if not chapters:
        return ""
    header_budget = 80 * len(chapters)
    content_budget = max(total_chars - header_budget, len(chapters) * 40)
    per_chapter = max(40, min(1200, content_budget // max(len(chapters), 1)))
    return _chapter_digest(chapters, per_chapter)


def _chunked(items: list[Any], size: int):
    for idx in range(0, len(items), size):
        yield items[idx:idx + size]


def _relay_progress(progress, prefix: str):
    def _inner(value=None, desc: str = "", total=None, content: str = ""):
        message = f"{prefix}{desc}" if desc else prefix
        progress(value, desc=message)
    return _inner


def _sse_preview(content: str, limit: int = 40000) -> str:
    if len(content) <= limit:
        return content
    return (
        f"【流式预览仅显示最后 {limit} 字，完整内容已实时保存，生成结束后会自动加载。】\n\n"
        + content[-limit:]
    )


def _extract_character_names(index_text: str) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    ignored = {
        "角色名", "姓名", "称谓", "主角", "配角", "反派", "功能性角色", "核心配角",
        "重要角色", "角色", "身份", "无", "未知", "待定",
    }
    for raw in index_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = re.sub(r"^(?:[-*+•]\s*|\d+[.、)]\s*)+", "", line).strip()
        if not line or line.startswith(("角色名", "姓名", "称谓")):
            continue
        if "｜" in line:
            candidate = line.split("｜", 1)[0]
        elif "|" in line:
            candidate = line.split("|", 1)[0]
        else:
            candidate = line
        candidate = re.sub(r"^(?:角色名|姓名|称谓)\s*[:：]\s*", "", candidate).strip()
        candidate = re.split(r"[：:，,；;（(\[【\s\-—]", candidate, 1)[0].strip()
        candidate = candidate.strip("《》“”\"'`")
        if not candidate or candidate in ignored:
            continue
        if len(candidate) > 16 or not re.search(r"[\u4e00-\u9fffA-Za-z0-9]", candidate):
            continue
        if candidate not in seen:
            seen.add(candidate)
            names.append(candidate)
    return names[:100]


def _chapter_markdown_section(markdown: str, chapter_num: int, limit: int) -> str:
    if not markdown:
        return ""
    pattern = re.compile(
        rf"(?ms)^#\s*第\s*{chapter_num}\s*章.*?(?=^#\s*第\s*\d+\s*章|\Z)"
    )
    match = pattern.search(markdown)
    section = match.group(0) if match else markdown
    return _truncate(section, limit)


def _clean_key(text: str) -> str:
    text = re.sub(r"[*_`#\s]+", "", text.strip())
    return text.strip("-：:|")


def _section_fields(section: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    current = ""
    lines = section.splitlines()
    for raw in lines:
        line = raw.strip()
        match = re.match(r"^(?:[-*]\s*)?(?:\*\*)?([^：:*]{2,20})(?:\*\*)?\s*[：:]\s*(.*)$", line)
        if match:
            current = _clean_key(match.group(1))
            fields[current] = match.group(2).strip()
        elif current and line:
            fields[current] = f"{fields[current]}\n{line}".strip()
    return fields


def _field_value(fields: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = fields.get(_clean_key(key))
        if value:
            return value
    return ""


def _storyboard_row_from_fields(chapter_num: int, chapter_title: str, shot_no: int,
                                fields: dict[str, str], raw: str) -> dict[str, Any]:
    return {
        "id": f"ch{chapter_num}_shot{shot_no}",
        "chapter_num": chapter_num,
        "chapter_title": chapter_title,
        "shot_no": shot_no,
        "locked": False,
        "plot": _field_value(fields, "对应剧情", "剧情", "剧情作用", "内容"),
        "subject": _field_value(fields, "画面主体", "主体", "画面", "镜头内容"),
        "characters": _field_value(fields, "出现角色", "角色动作/表情", "角色动作表情", "人物动作", "角色", "出场人物"),
        "camera": _field_value(fields, "镜头景别", "景别"),
        "composition": _field_value(fields, "机位/构图", "机位构图", "构图", "机位"),
        "location": _field_value(fields, "背景场景", "地点", "场景", "背景", "环境"),
        "light": _field_value(fields, "光影色彩", "光线", "时间/光线", "时间光线", "色彩"),
        "subtitle": _field_value(fields, "台词/字幕建议", "台词字幕建议", "台词", "字幕", "旁白/字幕", "旁白字幕"),
        "prompt_positive": _field_value(fields, "正向绘图提示词", "正向提示词", "画面提示词", "提示词", "prompt", "Prompt"),
        "prompt_negative": _field_value(fields, "负向提示词", "反向提示词", "Negative Prompt"),
        "continuity": _field_value(fields, "连续性备注", "连续性", "备注"),
        "raw": raw,
        "image_path": "",
        "status": "ready",
    }


def _split_markdown_table_row(line: str) -> list[str]:
    text = line.strip()
    if not text.startswith("|") or not text.endswith("|"):
        return []
    return [cell.strip().strip("*") for cell in text.strip("|").split("|")]


def _parse_storyboard_tables(body: str, chapter_num: int, chapter_title: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    lines = body.splitlines()
    idx = 0
    while idx < len(lines) - 1:
        headers = _split_markdown_table_row(lines[idx])
        separator = _split_markdown_table_row(lines[idx + 1])
        is_separator = bool(separator) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in separator)
        if not headers or not is_separator:
            idx += 1
            continue

        idx += 2
        while idx < len(lines):
            cells = _split_markdown_table_row(lines[idx])
            if not cells:
                break
            fields = {_clean_key(headers[col]): cells[col] for col in range(min(len(headers), len(cells)))}
            shot_text = (
                _field_value(fields, "镜号", "分镜", "镜头", "编号")
                or (cells[0] if cells else "")
            )
            match = re.search(r"\d+", shot_text)
            if match and not re.search(r"\d+\s*[-~－—]\s*\d+", shot_text):
                shot_no = int(match.group(0))
                rows.append(_storyboard_row_from_fields(
                    chapter_num,
                    chapter_title,
                    shot_no,
                    fields,
                    lines[idx].strip(),
                ))
            idx += 1
        idx += 1
    return rows


def _markdown_table_start_offsets(body: str) -> list[int]:
    starts: list[int] = []
    offset = 0
    lines = body.splitlines(keepends=True)
    for idx, line in enumerate(lines[:-1]):
        headers = _split_markdown_table_row(line)
        separator = _split_markdown_table_row(lines[idx + 1])
        is_separator = bool(separator) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in separator)
        if headers and is_separator:
            starts.append(offset)
        offset += len(line)
    return starts


def _characters_from_markdown(markdown: str) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    sections = re.split(r"(?m)^##\s+", markdown)
    for raw in sections[1:]:
        title, _, body = raw.partition("\n")
        name = title.strip().split("（", 1)[0].strip()
        if not name or (name.startswith("第") and "批" in name):
            continue
        fields = _section_fields(body)
        positive = fields.get("正向提示词") or fields.get("角色卡提示词") or ""
        negative = fields.get("负向提示词") or ""
        card = {
            "id": re.sub(r"\W+", "_", name).strip("_") or f"char_{len(cards) + 1}",
            "name": name,
            "locked": True,
            "identity": fields.get("剧情身份", ""),
            "personality": fields.get("性格关键词", ""),
            "arc": fields.get("人物弧光", ""),
            "relationships": fields.get("关系网络", "") or fields.get("与其他角色关系", ""),
            "chapters": fields.get("出场章节", "") or fields.get("首次/主要出场章节", ""),
            "appearance": fields.get("外貌固定设定", ""),
            "costume": fields.get("服装固定设定", ""),
            "expression": fields.get("表情气质", ""),
            "actions": fields.get("动作习惯", ""),
            "do_not_change": fields.get("禁忌变化点", ""),
            "prompt_positive": positive,
            "prompt_negative": negative,
            "continuity_notes": fields.get("连续性备注", ""),
            "raw": body.strip(),
        }
        cards.append(card)
    return cards


def _load_characters_structured(filepath: str) -> list[dict[str, Any]]:
    data = _read_json(_characters_json_path(filepath), [])
    return data if isinstance(data, list) else []


def _save_characters_structured(filepath: str, characters: list[dict[str, Any]]) -> None:
    normalized = []
    for idx, card in enumerate(characters, 1):
        item = dict(card)
        item["id"] = item.get("id") or re.sub(r"\W+", "_", item.get("name", "")).strip("_") or f"char_{idx}"
        item["name"] = item.get("name") or f"角色{idx}"
        item["locked"] = bool(item.get("locked", True))
        normalized.append(item)
    _write_json(_characters_json_path(filepath), normalized)


def _character_lock_context(filepath: str, fallback: str) -> str:
    cards = [c for c in _load_characters_structured(filepath) if c.get("locked", True)]
    if not cards:
        return fallback
    lines = []
    for card in cards:
        lines.append(
            "\n".join([
                f"【{card.get('name', '')}】",
                f"身份：{card.get('identity', '')}",
                f"外貌锁定：{card.get('appearance', '')}",
                f"服装锁定：{card.get('costume', '')}",
                f"气质/表情：{card.get('expression', '')}",
                f"正向提示词：{card.get('prompt_positive', '')}",
                f"负向提示词：{card.get('prompt_negative', '')}",
                f"禁忌变化点：{card.get('do_not_change', '')}",
            ])
        )
    return "\n\n".join(lines)


def _storyboard_rows_from_markdown(markdown: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    chapter_pattern = re.compile(r"(?ms)^#\s*第\s*(\d+)\s*章\s*([^\n（]*)[^\n]*\n(.*?)(?=^#\s*第\s*\d+\s*章|\Z)")
    for ch_match in chapter_pattern.finditer(markdown):
        chapter_num = int(ch_match.group(1))
        chapter_title = ch_match.group(2).strip()
        body = ch_match.group(3)
        by_key: dict[tuple[int, int], dict[str, Any]] = {}
        for table_row in _parse_storyboard_tables(body, chapter_num, chapter_title):
            by_key[(chapter_num, int(table_row["shot_no"]))] = table_row

        table_starts = _markdown_table_start_offsets(body)
        shot_matches = list(re.finditer(
            r"(?m)^\s*(?:#{2,6}\s*)?(?:[-*]\s*)?(?:(?:分镜|镜号)\s*[：:]?\s*)?([0-9]+)(?!\s*[-~－—]\s*)(?:\s*[.、]\s*)?(?:镜号)?(?:\s*[：:].*)?\s*$",
            body,
        ))
        for idx, match in enumerate(shot_matches):
            start = match.start()
            end_candidates = [shot_matches[idx + 1].start()] if idx + 1 < len(shot_matches) else [len(body)]
            end_candidates.extend(pos for pos in table_starts if pos > start)
            end = min(end_candidates)
            block = body[start:end].strip()
            fields = _section_fields(block)
            shot_no = int(match.group(1))
            row = _storyboard_row_from_fields(chapter_num, chapter_title, shot_no, fields, block)
            key = (chapter_num, shot_no)
            existing = by_key.get(key)
            if not existing or len(json.dumps(row, ensure_ascii=False)) > len(json.dumps(existing, ensure_ascii=False)):
                by_key[key] = row
        rows.extend(by_key[key] for key in sorted(by_key))
    return rows


def _load_storyboard_rows(filepath: str) -> list[dict[str, Any]]:
    data = _read_json(_storyboards_json_path(filepath), [])
    return data if isinstance(data, list) else []


def _save_storyboard_rows(filepath: str, rows: list[dict[str, Any]]) -> None:
    normalized = []
    for idx, row in enumerate(rows, 1):
        item = dict(row)
        chapter_num = int(item.get("chapter_num") or 0)
        shot_no = int(item.get("shot_no") or idx)
        item["id"] = item.get("id") or f"ch{chapter_num}_shot{shot_no}"
        item["chapter_num"] = chapter_num
        item["shot_no"] = shot_no
        item["locked"] = bool(item.get("locked", False))
        normalized.append(item)
    _write_json(_storyboards_json_path(filepath), normalized)


def _default_style_templates() -> list[dict[str, str]]:
    return [
        {"name": "国漫竖屏", "visual_style": "国漫竖屏短剧，电影级构图，高细节角色，明快色彩，适合移动端观看", "extra_guidance": "强调情绪特写、服装连续、镜头节奏清晰"},
        {"name": "日漫清透", "visual_style": "现代日漫，干净线条，透明光感，柔和色彩，细腻表情", "extra_guidance": "适合校园、恋爱、轻奇幻题材"},
        {"name": "赛博霓虹", "visual_style": "赛博朋克，霓虹灯，雨夜城市，高对比光影，未来科技质感", "extra_guidance": "突出机械道具、城市层次、冷暖色反差"},
        {"name": "古风电影", "visual_style": "东方古风，电影级置景，丝绸服饰，水墨氛围，写实国风", "extra_guidance": "强调朝堂、江湖、宫廷礼制与服饰材质"},
        {"name": "暗黑奇幻", "visual_style": "暗黑奇幻，厚重油画感，低饱和，高戏剧光，史诗场面", "extra_guidance": "适合战争、神秘仪式、压迫感场景"},
    ]


def _load_style_templates(filepath: str) -> list[dict[str, str]]:
    custom = _read_json(_style_templates_path(filepath), [])
    return _default_style_templates() + (custom if isinstance(custom, list) else [])


def _llm_adapter(llm_config_name: str):
    app = get_web_app()
    conf = app.config.get("llm_configs", {}).get(llm_config_name)
    if not conf:
        raise ValueError(f"未找到 LLM 配置：{llm_config_name}")
    return create_llm_adapter(
        interface_format=conf.get("interface_format", "OpenAI"),
        base_url=conf.get("base_url", ""),
        model_name=conf.get("model_name", ""),
        api_key=conf.get("api_key", ""),
        temperature=conf.get("temperature", 0.7),
        max_tokens=conf.get("max_tokens", 4096),
        timeout=conf.get("timeout", 600),
        enable_thinking=conf.get("enable_thinking", False),
        thinking_budget=conf.get("thinking_budget", 0),
    )


def _save_result(filepath: str, filename: str, content: str) -> None:
    path = os.path.join(_work_dir(filepath), filename)
    save_string_to_txt(content, path)


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


@router.put("/manju/settings")
def save_manju_settings(body: ManjuSettingsRequest):
    chapters = _load_chapters(body.filepath)
    settings = _normalize_settings(body.model_dump(exclude={"filepath"}), chapters)
    _write_json(_settings_path(body.filepath), settings)
    return {"message": "✅ 漫剧制作设置已保存", "settings": settings}


def _script_filename(filepath: str) -> str:
    meta = _read_json(os.path.join(_work_dir(filepath), "meta.json"), {}) or {}
    raw_name = os.path.splitext(str(meta.get("filename") or "manju_script"))[0]
    safe = re.sub(r'[\\/:*?"<>|\s]+', "_", raw_name).strip("_") or "manju_script"
    return f"{safe}_漫剧改编剧本.txt"


def _attachment_header(filename: str, fallback: str = "download.txt") -> str:
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "_", fallback).strip("_") or "download.txt"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


def _normalize_reimportable_chapter(text: str, episode: int) -> str:
    text = text.replace("```", "").strip()
    lines = []
    skip_section = False
    production_headings = (
        "改编参数", "改编总纲", "人物改编表", "剧本目录", "场次列表", "角色表",
        "剧情节拍", "分镜提示", "时长预估", "画面说明", "动作", "情绪点",
        "旁白/字幕", "旁白字幕", "适合分镜的关键画面", "场次",
        "原名-新名对照表", "原名 - 新名对照表", "正式剧本", "地点", "时间",
        "出场人物", "对白", "旁白", "字幕", "表面", "内里",
    )
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            skip_section = False
            lines.append("")
            continue
        if stripped.startswith(("#", "-", ">", "|")):
            stripped = stripped.lstrip("#>-| ").rstrip("| ").strip()
        stripped = re.sub(r"^\*\*(.*?)\*\*\s*[：:]\s*", r"\1：", stripped)
        if any(stripped.startswith(f"{heading}：") or stripped == heading for heading in production_headings):
            skip_section = True
            continue
        if re.match(r"^约\s*\d+", stripped):
            continue
        if re.match(r"^[^：:\n]{1,20}\s*-\s*[^：:\n]{1,20}\s*[：:]", stripped):
            continue
        if re.match(r"^场次\s*\d+", stripped):
            skip_section = False
            continue
        if skip_section and re.match(r"^\d+[.、]\s*", stripped):
            continue
        lines.append(stripped)

    cleaned = "\n".join(lines).strip()
    title_matches = list(re.finditer(rf"(?m)^第\s*{episode}\s*章[^\n]*$", cleaned))
    if title_matches:
        match = max(title_matches, key=lambda item: (len(item.group(0).strip()), item.start()))
        title = re.sub(r"\s+", " ", match.group(0)).strip()
        body = cleaned[match.end():].strip()
    else:
        title = f"第{episode}章 漫剧改编"
        body = cleaned
    title = re.sub(r"^#+\s*", "", title).strip()
    title = re.sub(r"\s+", " ", title)
    body = re.sub(r"(?m)^\s*#{1,6}\s*", "", body)
    return f"{title}\n{body.strip()}\n"


def _looks_reimportable_script(text: str) -> bool:
    stripped = text.lstrip()
    if stripped.startswith(("#", "##", "###")):
        return False
    return bool(re.search(r"(?m)^\s*第\s*[零〇一二三四五六七八九十百千万\d]+\s*[章节回集卷部篇][^\n]{0,80}\s*$", text))


def _strip_old_script_boilerplate(text: str) -> str:
    if _looks_reimportable_script(text):
        return text
    marker = re.search(r"(?m)^\s*#{1,6}\s*分章剧本\s*$", text)
    if marker:
        text = text[marker.end():]
    matches = list(re.finditer(r"(?m)^\s*#{1,6}\s*第\s*(\d+)\s*章[^\n]*$", text))
    if not matches:
        return text
    parts = []
    for idx, match in enumerate(matches):
        episode = int(match.group(1))
        title_text = re.sub(r"^#+\s*", "", match.group(0).strip())
        if idx + 1 < len(matches) and int(matches[idx + 1].group(1)) == episode and re.fullmatch(rf"第\s*{episode}\s*章", title_text):
            continue
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        block = text[match.start():end]
        parts.append(_normalize_reimportable_chapter(block, episode))
    return "\n\n".join(parts).strip() + "\n"


def _generate_script_adaptation_sync(llm_config_name: str, filepath: str, start_chapter: int, end_chapter: int | None,
                                     target_chapters: int, rename_characters: bool, adaptation_level: str,
                                     episode_duration: str, script_style: str, extra_guidance: str, progress):
    chapters = _chapter_window(_load_chapters(filepath), start_chapter, end_chapter)
    target_chapters = max(1, min(int(target_chapters or 12), 120))
    llm = _llm_adapter(llm_config_name)
    source_digest = _chapter_digest_balanced(chapters, 42000)
    rename_rule = "允许根据漫剧传播效果重命名人物，但正文中只使用新名字，不要输出原名-新名对照表。" if rename_characters else "不得修改人物名称，必须沿用小说原名。"
    progress(0.03, desc="正在规划漫剧正文改编结构...")

    outline_prompt = f"""你是小说改编策划。请把小说内容规划为可再次导入系统的漫剧小说正文目录。

改编参数：
- 目标剧本章节数：{target_chapters} 章
- 人物名称规则：{rename_rule}
- 剧情改编幅度：{adaptation_level}
- 单章篇幅/节奏参考：{episode_duration}
- 改编风格：{script_style}
- 补充要求：{extra_guidance or "无"}

硬性要求：
1. 只输出 {target_chapters} 行目录，编号 1-{target_chapters}，不能多也不能少。
2. 每行格式：第X章 标题｜本章剧情一句话
3. 不要输出改编原则、人物表、说明、Markdown 表格、分镜、场次。
4. 改编要增强冲突、反转、爽点、情绪钩子，但不能破坏主线逻辑。

小说章节摘录：
{source_digest}
"""
    outline = invoke_with_cleaning(llm, outline_prompt, progress=_relay_progress(progress, "正文目录："))
    save_string_to_txt(outline, _script_outline_path(filepath))

    outputs: list[str] = []
    previous_script = ""
    for episode in range(1, target_chapters + 1):
        progress(0.08 + 0.88 * (episode - 1) / target_chapters, desc=f"正在改编第 {episode}/{target_chapters} 章漫剧剧本...")
        episode_prompt = f"""你是小说改编作者。请根据目录和原文摘录，只创作第 {episode} 章的漫剧改编正文。

硬性要求：
1. 输出必须是可再次导入的 TXT 小说正文格式。
2. 第一行必须且只能是章节标题，格式严格为：第{episode}章 标题
3. 标题下一行开始直接写剧情正文，可以包含自然对白，但不要写“场次、画面说明、分镜提示、角色表、剧情节拍、旁白/字幕、情绪点、改编说明”等制作信息。
4. 不要使用 Markdown 标题符号，不要输出列表，不要输出表格，不要解释。
5. 人物名称规则：{rename_rule}
6. 剧情改编幅度：{adaptation_level}。改编可以增强戏剧性，但必须保持主线因果清晰。
7. 风格参考：{script_style}。重点是剧情可读、冲突清晰、适合后续模块继续生成角色图/场景图/分镜图。
8. 结尾要有自然的章节钩子，但仍然写成小说正文。

补充要求：
{extra_guidance or "无"}

改编目录：
{_truncate(outline, 18000)}

上一章正文结尾：
{_truncate(previous_script, 5000) if previous_script else "暂无，这是第一章。"}

小说章节摘录：
{source_digest}
"""
        episode_script = invoke_with_cleaning(
            llm,
            episode_prompt,
            progress=_relay_progress(progress, f"第 {episode}/{target_chapters} 章剧本："),
        )
        block = _normalize_reimportable_chapter(episode_script, episode)
        outputs.append(block)
        previous_script = block
        preview = "\n\n".join(outputs).strip() + "\n"
        save_string_to_txt(preview, _script_path(filepath))
        progress(
            0.08 + 0.88 * episode / target_chapters,
            desc=f"第 {episode}/{target_chapters} 章漫剧剧本完成",
            content=preview,
        )

    final = "\n\n".join(outputs).strip() + "\n"
    save_string_to_txt(final, _script_path(filepath))
    return final


@router.post("/manju/script")
def generate_manju_script(body: ManjuScriptAdaptRequest):
    async def _gen():
        async for chunk in run_with_sse(
            _generate_script_adaptation_sync,
            body.llm_config_name, body.filepath, body.start_chapter, body.end_chapter,
            body.target_chapters, body.rename_characters, body.adaptation_level,
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


@router.put("/manju/characters/structured")
def save_structured_characters(body: ManjuCharactersUpdateRequest):
    _save_characters_structured(body.filepath, body.characters)
    return {"message": "✅ 角色一致性锁定表已保存", "characters": _load_characters_structured(body.filepath)}


@router.put("/manju/storyboards/structured")
def save_structured_storyboards(body: ManjuStoryboardUpdateRequest):
    _save_storyboard_rows(body.filepath, body.shots)
    return {"message": "✅ 分镜表格已保存", "shots": _load_storyboard_rows(body.filepath)}


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
4. 输出字段：subject、characters、camera、composition、location、light、subtitle、prompt_positive、prompt_negative、continuity。

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
    result = invoke_with_cleaning(llm, prompt, enable_streaming=False)
    text = result.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        patch = json.loads(text)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="LLM 未返回合法 JSON，请稍后重试")
    for key in ("subject", "characters", "camera", "composition", "location", "light", "subtitle", "prompt_positive", "prompt_negative", "continuity"):
        if key in patch:
            target[key] = patch[key]
    target["status"] = "regenerated"
    _save_storyboard_rows(body.filepath, rows)
    return {"message": "✅ 分镜已重生成", "shot": target, "shots": rows}


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


@router.put("/manju/image-config")
def save_image_config(body: ManjuImageConfigRequest):
    existing = _read_json(_image_config_path(body.filepath), {})
    config = body.model_dump(exclude={"filepath"})
    config["provider"] = (config.get("provider") or "openai").strip().lower()
    config["output_format"] = (config.get("output_format") or "png").strip().lower().lstrip(".")
    if not config.get("api_key") or config.get("api_key") == "***":
        config["api_key"] = existing.get("api_key", "")
    _write_json(_image_config_path(body.filepath), config)
    safe_config = {**config, "api_key": "***" if config.get("api_key") else ""}
    return {"message": "✅ 图片生成接口设置已保存", "image_config": safe_config}


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


def _content_export_path(filepath: str, kind: str) -> tuple[str, str]:
    mapping = {
        "characters": ("characters.md", "角色信息与角色卡提示词"),
        "scenes": ("scenes.md", "章节场景图提示词"),
        "storyboards": ("storyboards.md", "章节分镜图提示词"),
    }
    if kind not in mapping:
        raise HTTPException(status_code=400, detail="kind 只能是 characters/scenes/storyboards")
    filename, label = mapping[kind]
    path = os.path.join(_work_dir(filepath), filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"暂无{label}，请先生成")
    return path, label


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


def _collect_markdown_prompt_items(markdown: str, source_type: str, source_label: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    lines = markdown.splitlines()
    current_title = source_label
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        heading = re.match(r"^#{1,6}\s*(.+)$", line)
        if heading:
            current_title = heading.group(1).strip()
            idx += 1
            continue
        clean_line = re.sub(r"[*`]", "", line)
        if re.search(r"(?:负向提示词|反向提示词|Negative Prompt)", clean_line, re.IGNORECASE):
            idx += 1
            continue
        positive_match = re.search(r"(?:正向绘图提示词|正向提示词|画面提示词)\s*(?:[：:]\s*)?(.*)$", clean_line)
        if not positive_match:
            idx += 1
            continue
        prompt_parts = []
        first = positive_match.group(1).strip().strip("：: ")
        if first:
            prompt_parts.append(first)
        idx += 1
        while idx < len(lines):
            candidate = lines[idx].strip()
            if not candidate:
                idx += 1
                if prompt_parts:
                    break
                continue
            if re.match(r"^(#{1,6}\s+|---+$)", candidate):
                break
            if re.search(r"(?:负向提示词|反向提示词|连续性备注|剧情作用|地点|时间/光线|环境元素|出现角色|人物站位|情绪氛围|镜头景别|对应剧情|画面主体|角色动作)", candidate):
                break
            prompt_parts.append(candidate.lstrip("- ").strip())
            idx += 1
        prompt = "\n".join(prompt_parts).strip()
        if prompt:
            item_no = len(items) + 1
            items.append({
                "id": f"{source_type}_{item_no}",
                "title": f"{source_label}｜{current_title}｜{item_no}",
                "prompt": prompt,
                "source_type": source_type,
                "source_id": str(item_no),
                "source_label": source_label,
            })
        continue
    return items


def _manju_prompt_items(filepath: str, kind: str) -> list[dict[str, Any]]:
    if kind == "characters":
        return [
            {
                "id": card.get("id") or card.get("name") or f"character_{idx}",
                "title": f"角色卡｜{card.get('name') or idx}",
                "prompt": card.get("prompt_positive", ""),
                "negative_prompt": card.get("prompt_negative", ""),
                "source_type": "manju_character",
                "source_id": str(card.get("id") or card.get("name") or idx),
                "source_label": "角色卡",
            }
            for idx, card in enumerate(_load_characters_structured(filepath), 1)
            if card.get("prompt_positive")
        ]
    if kind == "scenes":
        path = os.path.join(_work_dir(filepath), "scenes.md")
        return _collect_markdown_prompt_items(_read_text(path) if os.path.exists(path) else "", "manju_scene", "场景图")
    if kind == "storyboards":
        rows = _load_storyboard_rows(filepath)
        if rows:
            return [
                {
                    "id": row.get("id") or f"shot_{idx}",
                    "title": f"分镜图｜第{row.get('chapter_num')}章｜镜{row.get('shot_no')}",
                    "prompt": row.get("prompt_positive", ""),
                    "negative_prompt": row.get("prompt_negative", ""),
                    "source_type": "manju_storyboard",
                    "source_id": str(row.get("id") or idx),
                    "source_label": "分镜图",
                }
                for idx, row in enumerate(rows, 1)
                if row.get("prompt_positive")
            ]
        path = os.path.join(_work_dir(filepath), "storyboards.md")
        return _collect_markdown_prompt_items(_read_text(path) if os.path.exists(path) else "", "manju_storyboard", "分镜图")
    if kind == "all":
        items: list[dict[str, Any]] = []
        for item_kind in ("characters", "scenes", "storyboards"):
            items.extend(_manju_prompt_items(filepath, item_kind))
        return items
    raise HTTPException(status_code=400, detail="kind 只能是 characters/scenes/storyboards/all")


@router.post("/manju/image-prompts/import")
def import_manju_prompts_to_images(body: ManjuImagePromptImportRequest):
    items = _manju_prompt_items(body.filepath, body.kind)
    if not items:
        raise HTTPException(status_code=404, detail="暂无可导入的图片提示词，请先生成对应内容")
    rows = add_image_prompt_items(body.filepath, items, body.replace)
    return {
        "message": f"✅ 已导入图片生成模块：本次 {len(items)} 条，队列共 {len(rows)} 条",
        "items": rows,
        "imported": len(items),
        "count": len(rows),
    }


def _flatten_export_rows(kind: str, filepath: str) -> list[dict[str, Any]]:
    if kind == "characters":
        return _load_characters_structured(filepath)
    if kind == "storyboards":
        return _load_storyboard_rows(filepath)
    if kind == "all":
        rows = []
        for item in _load_characters_structured(filepath):
            rows.append({"asset_type": "character", **item})
        for item in _load_storyboard_rows(filepath):
            rows.append({"asset_type": "shot", **item})
        return rows
    raise HTTPException(status_code=400, detail="kind 只能是 characters/storyboards/all")


def _csv_response(rows: list[dict[str, Any]], filename: str) -> Response:
    headers = sorted({key for row in rows for key in row.keys()})
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in headers})
    return Response(
        content=buf.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
    )


def _xlsx_response(rows: list[dict[str, Any]], filename: str) -> Response:
    headers = sorted({key for row in rows for key in row.keys()})

    def cell_ref(col_idx: int, row_idx: int) -> str:
        name = ""
        col = col_idx
        while col:
            col, rem = divmod(col - 1, 26)
            name = chr(65 + rem) + name
        return f"{name}{row_idx}"

    def cell_xml(value: Any, col_idx: int, row_idx: int) -> str:
        text = str(value if value is not None else "")
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f'<c r="{cell_ref(col_idx, row_idx)}" t="inlineStr"><is><t>{text}</t></is></c>'

    sheet_rows = []
    sheet_rows.append("<row r=\"1\">" + "".join(cell_xml(h, idx + 1, 1) for idx, h in enumerate(headers)) + "</row>")
    for row_idx, row in enumerate(rows, 2):
        sheet_rows.append(
            f'<row r="{row_idx}">' + "".join(cell_xml(row.get(h, ""), idx + 1, row_idx) for idx, h in enumerate(headers)) + "</row>"
        )
    sheet = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{''.join(sheet_rows)}</sheetData></worksheet>'''
    workbook = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="manju" sheetId="1" r:id="rId1"/></sheets></workbook>'''
    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'''
    workbook_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'''
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'''
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet)
    return Response(
        content=out.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
    )


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


@router.get("/manju/continuity-check")
def continuity_check(filepath: str = "./output"):
    cards = _load_characters_structured(filepath)
    rows = sorted(_load_storyboard_rows(filepath), key=lambda r: (int(r.get("chapter_num") or 0), int(r.get("shot_no") or 0)))
    issues = []
    card_names = {c.get("name") for c in cards if c.get("name")}
    locked_names = {c.get("name") for c in cards if c.get("name") and c.get("locked", True)}
    prev = None
    for row in rows:
        ref_text = " ".join(str(row.get(key, "")) for key in ("characters", "subject", "prompt_positive", "continuity"))
        mentioned = {name for name in card_names if name and name in ref_text}
        if not row.get("location"):
            issues.append({"level": "warning", "shot_id": row.get("id"), "message": "缺少背景场景/地点，后续画面连续性较弱"})
        if not row.get("light"):
            issues.append({"level": "warning", "shot_id": row.get("id"), "message": "缺少光影色彩/时间信息"})
        for name in mentioned - locked_names:
            issues.append({"level": "warning", "shot_id": row.get("id"), "message": f"角色“{name}”未锁定，可能发生外貌漂移"})
        if prev and row.get("chapter_num") == prev.get("chapter_num"):
            if prev.get("location") and row.get("location") and prev.get("location") != row.get("location"):
                continuity = str(row.get("continuity", ""))
                if not any(word in continuity for word in ("转场", "切到", "来到", "进入", "离开")):
                    issues.append({"level": "info", "shot_id": row.get("id"), "message": "地点较上一镜变化，但连续性备注未说明转场"})
        prev = row
    return {"issues": issues, "issue_count": len(issues)}


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


def _resolve_image_prompt(body: ManjuImageGenerateRequest) -> str:
    if body.prompt.strip():
        return body.prompt.strip()
    if body.source_type == "character":
        for card in _load_characters_structured(body.filepath):
            if card.get("id") == body.source_id or card.get("name") == body.source_id:
                return "\n".join([
                    str(card.get("prompt_positive", "")),
                    f"角色锁定：{card.get('appearance', '')}，{card.get('costume', '')}",
                    f"负向：{card.get('prompt_negative', '')}",
                ]).strip()
    if body.source_type == "shot":
        for row in _load_storyboard_rows(body.filepath):
            if row.get("id") == body.source_id:
                return "\n".join([
                    str(row.get("prompt_positive", "")),
                    f"画面主体：{row.get('subject', '')}",
                    f"背景：{row.get('location', '')}",
                    f"连续性：{row.get('continuity', '')}",
                    f"负向：{row.get('prompt_negative', '')}",
                ]).strip()
    raise HTTPException(status_code=400, detail="未找到可用于生成图片的提示词")


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
    prompt = _resolve_image_prompt(body)
    config = normalize_image_config(config)
    out_path = save_generated_image(
        config,
        prompt,
        _work_dir(body.filepath),
        body.source_type,
        body.source_id,
        group_by_project=False,
    )
    rel_path = os.path.relpath(out_path, _work_dir(body.filepath))
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
    return {"message": "✅ 图片已生成", **payload, "relative_path": rel_path}


def _generate_characters_sync(llm_config_name: str, filepath: str, start_chapter: int, end_chapter: int | None,
                              visual_style: str, extra_guidance: str, progress):
    chapters = _chapter_window(_load_chapters(filepath), start_chapter, end_chapter)
    if not chapters:
        return "❌ 请先导入小说 TXT"
    llm = _llm_adapter(llm_config_name)
    source = _chapter_digest_balanced(chapters, 30000)
    progress(0.02, desc="正在识别小说角色总表...")

    def build_index_prompt(chapter_source: str, scope: str) -> str:
        return f"""你是资深漫剧改编导演。请先根据小说摘录建立“角色索引”，用于后续分批生成角色卡。

硬性要求：
1. 尽量识别{scope}内所有会影响剧情或画面连续性的角色，包括主角、核心配角、反派、功能性角色。
2. 不要把地点、势力、物品、章节名当成角色。
3. 只输出角色索引，不要输出详细角色卡。
4. 每行必须严格使用以下格式，方便程序读取：
- 角色名｜重要度：主角/核心配角/反派/功能性角色｜身份：一句话身份｜首次/主要出场：章节号或章节名｜依据：原文线索简述

补充要求：
{extra_guidance or "无"}

小说章节摘录：
{chapter_source}
"""

    if len(chapters) > 60:
        index_parts = []
        chapter_batches = list(_chunked(chapters, 40))
        for index_idx, chapter_batch in enumerate(chapter_batches, 1):
            first_num = chapter_batch[0]["num"]
            last_num = chapter_batch[-1]["num"]
            progress(
                0.02 + 0.24 * (index_idx - 1) / max(len(chapter_batches), 1),
                desc=f"正在扫描角色索引 {index_idx}/{len(chapter_batches)}：第 {first_num}-{last_num} 章",
            )
            batch_source = _chapter_digest(chapter_batch, 650)
            prompt = build_index_prompt(batch_source, f"第 {first_num}-{last_num} 章")
            batch_index = invoke_with_cleaning(
                llm, prompt, progress=_relay_progress(progress, f"角色索引第 {index_idx}/{len(chapter_batches)} 批：")
            )
            index_parts.append(f"## 第 {first_num}-{last_num} 章角色索引\n\n{batch_index.strip()}")
            progress(
                0.02 + 0.24 * index_idx / max(len(chapter_batches), 1),
                desc=f"角色索引 {index_idx}/{len(chapter_batches)} 扫描完成",
                content="\n\n".join(index_parts),
            )
        index_result = "\n\n".join(index_parts)
    else:
        index_prompt = build_index_prompt(source, "整本小说")
        index_result = invoke_with_cleaning(
            llm, index_prompt, progress=_relay_progress(progress, "角色索引：")
        )

    names = _extract_character_names(index_result)

    if not names:
        progress(0.2, desc="角色索引解析不稳定，改用完整角色库生成...")
        fallback_prompt = f"""你是资深漫剧改编导演和角色设定师。请根据整本小说内容，整理适合“漫剧/短剧分镜/AI绘图”的角色资料库。

要求：
1. 识别所有重要角色，按主角、核心配角、反派、功能性角色分组。
2. 每个角色必须包含：姓名/称谓、剧情身份、性格关键词、人物弧光、与其他角色关系、首次/主要出场章节、外貌固定设定、服装固定设定、表情气质、动作习惯、禁忌变化点。
3. 为每个角色生成“角色卡提示词”，用于后续文生图，必须细致、稳定、可复用。
4. 同一个角色的外貌、服装、气质要保持连续一致；如果原文缺失，请做合理改编并明确标注“改编补全”。
5. 不得写“其余略”“后续同上”等省略表达。
6. 输出 Markdown，中文为主，可保留关键英文绘图词。

全局视觉风格：
{visual_style}

补充要求：
{extra_guidance or "无"}

小说章节摘录：
{source}
"""
        result = invoke_with_cleaning(llm, fallback_prompt, progress=progress)
        _save_result(filepath, "characters.md", result)
        _save_characters_structured(filepath, _characters_from_markdown(result))
        return result

    sections = [f"# 角色索引\n\n{index_result.strip()}", "# 角色信息与角色卡提示词"]
    batches = list(_chunked(names, 4))
    total_batches = max(len(batches), 1)
    for batch_idx, batch in enumerate(batches, 1):
        batch_names = "、".join(batch)
        progress(
            0.30 + 0.64 * (batch_idx - 1) / total_batches,
            desc=f"正在生成角色卡第 {batch_idx}/{total_batches} 批：{batch_names}",
        )
        card_prompt = f"""你是资深漫剧角色设定师。请只为“本批角色”生成细致角色信息与角色卡提示词。

本批角色：
{chr(10).join(f"- {name}" for name in batch)}

硬性要求：
1. 必须逐个输出本批全部角色，顺序与上方一致，不得合并、不得省略。
2. 每个角色都要包含：剧情身份、性格关键词、人物弧光、与其他角色关系、首次/主要出场章节、外貌固定设定、服装固定设定、表情气质、动作习惯、禁忌变化点。
3. 每个角色必须生成可复用的“角色卡提示词”，细到年龄感、脸型、发型发色、体型、服装材质/颜色、标志物、表情、气质、镜头偏好。
4. 原文未明确的信息可以合理改编补全，但必须标注“改编补全”。
5. 不得写“同上”“略”“其余角色类似”“后续继续”等省略表达。

建议格式：
## 角色名
- 剧情身份：
- 性格关键词：
- 人物弧光：
- 关系网络：
- 出场章节：
- 外貌固定设定：
- 服装固定设定：
- 表情气质：
- 动作习惯：
- 禁忌变化点：
- 角色卡提示词：
  - 正向提示词：
  - 负向提示词：
  - 连续性备注：

全局视觉风格：
{visual_style}

补充要求：
{extra_guidance or "无"}

角色索引：
{_truncate(index_result, 12000)}

小说章节摘录：
{source}
"""
        result = invoke_with_cleaning(
            llm, card_prompt, progress=_relay_progress(progress, f"角色卡第 {batch_idx}/{total_batches} 批：")
        )
        sections.append(f"## 第 {batch_idx} 批：{batch_names}\n\n{result.strip()}")
        progress(
            0.30 + 0.64 * batch_idx / total_batches,
            desc=f"角色卡第 {batch_idx}/{total_batches} 批完成",
            content="\n\n".join(sections),
        )

    final = "\n\n".join(sections)
    _save_result(filepath, "characters.md", final)
    _save_characters_structured(filepath, _characters_from_markdown(final))
    return final


def _generate_scenes_sync(llm_config_name: str, filepath: str, start_chapter: int, end_chapter: int | None,
                          visual_style: str, extra_guidance: str, progress):
    chapters = _chapter_window(_load_chapters(filepath), start_chapter, end_chapter)
    llm = _llm_adapter(llm_config_name)
    characters_md = manju_status(filepath).get("characters") or "尚未生成角色卡，请根据章节临时保持角色一致。"
    characters = _character_lock_context(filepath, characters_md)
    all_output = []
    for idx, ch in enumerate(chapters, 1):
        progress(idx / max(len(chapters), 1), desc=f"正在生成第 {ch['num']} 章场景图提示词...")
        prompt = f"""你是漫剧美术导演。请把下面章节拆成适合 AI 绘图/场景概念图的“场景图提示词清单”。

输出要求：
- 每章列出 6-12 个关键场景，不要遗漏主要剧情转场。
- 每个场景包含：场景编号、剧情作用、地点、时间/光线、环境元素、出现角色、人物站位、情绪氛围、镜头景别、正向绘图提示词、负向提示词。
- 必须严格引用下方“角色一致性锁定表”，保持角色外貌、服装、气质、禁忌变化点一致。
- 不要写成小说正文，要写成可直接给绘图模型使用的提示词。

全局视觉风格：
{visual_style}

角色一致性锁定表：
{_truncate(characters, 12000)}

补充要求：
{extra_guidance or "无"}

章节：
第{ch['num']}章 {ch['title']}
{_truncate(ch['content'], 12000)}
"""
        result = invoke_with_cleaning(
            llm,
            prompt,
            progress=_relay_progress(progress, f"第 {ch['num']} 章场景："),
            enable_streaming=False,
        )
        all_output.append(f"# 第{ch['num']}章 {ch['title']}\n\n{result}")
        current = "\n\n---\n\n".join(all_output)
        _save_result(filepath, "scenes.md", current)
        progress(idx / max(len(chapters), 1), desc=f"第 {ch['num']} 章场景图提示词完成", content=_sse_preview(current))
    final = "\n\n---\n\n".join(all_output)
    _save_result(filepath, "scenes.md", final)
    return "✅ 章节场景图提示词已生成并保存，正在加载完整内容..."


def _generate_storyboards_sync(llm_config_name: str, filepath: str, start_chapter: int, end_chapter: int | None,
                               shots_per_chapter: int, visual_style: str, extra_guidance: str, progress):
    chapters = _chapter_window(_load_chapters(filepath), start_chapter, end_chapter)
    shots_per_chapter = max(1, min(int(shots_per_chapter or 12), 80))
    llm = _llm_adapter(llm_config_name)
    status = manju_status(filepath)
    characters_md = status.get("characters") or "尚未生成角色卡，请根据章节临时保持角色一致。"
    characters = _character_lock_context(filepath, characters_md)
    scenes = status.get("scenes") or "尚未生成场景图提示词，请直接根据章节内容拆分。"
    all_output = []
    shot_batch_size = 8
    total_units = max(len(chapters) * ((shots_per_chapter + shot_batch_size - 1) // shot_batch_size), 1)
    done_units = 0
    for idx, ch in enumerate(chapters, 1):
        chapter_parts = []
        for shot_start in range(1, shots_per_chapter + 1, shot_batch_size):
            shot_end = min(shot_start + shot_batch_size - 1, shots_per_chapter)
            batch_count = shot_end - shot_start + 1
            progress(
                done_units / total_units,
                desc=f"正在生成第 {ch['num']} 章分镜 {shot_start}-{shot_end}/{shots_per_chapter}...",
            )
            previous_context = _truncate("\n\n".join(chapter_parts[-2:]), 3500)
            chapter_scenes = _chapter_markdown_section(scenes, int(ch["num"]), 8000)
            prompt = f"""你是漫剧分镜导演。请根据章节内容生成连续分镜图提示词。

硬性要求：
1. 本章总分镜数为 {shots_per_chapter}。本次只输出全局编号 {shot_start}-{shot_end}，共 {batch_count} 个分镜，不能多也不能少。
2. 每个分镜必须使用全局编号，不要从 1 重新编号，除非本批从 1 开始。
3. 分镜必须覆盖完整剧情：开场交代、冲突推进、关键动作、情绪反应、信息揭示、结尾钩子。
4. 本批要承接已完成分镜，必须严格引用“角色一致性锁定表”，保持角色、服饰、道具、空间方向、情绪递进连续。
5. 不得写“略”“同上”“后续继续”“省略若干镜头”等省略表达。
6. 如果本批包含最后一个镜头（编号 {shots_per_chapter}），最后一镜必须形成本章结尾钩子或情绪落点。

每个分镜包含：
- 镜号
- 对应剧情
- 画面主体
- 角色动作/表情
- 镜头景别
- 机位/构图
- 背景场景
- 光影色彩
- 台词/字幕建议
- 正向绘图提示词
- 负向提示词
- 连续性备注

输出格式：
使用 Markdown 分镜清单，必须逐条列出 {shot_start}-{shot_end}。

已完成的本章前序分镜：
{previous_context or "暂无，这是本章第一批分镜。"}

全局视觉风格：
{visual_style}

角色一致性锁定表：
{_truncate(characters, 12000)}

本章已有场景提示词：
{chapter_scenes or "尚未生成本章场景图提示词，请直接根据章节内容拆分。"}

补充要求：
{extra_guidance or "无"}

章节：
第{ch['num']}章 {ch['title']}
{_truncate(ch['content'], 14000)}
"""
            result = invoke_with_cleaning(
                llm,
                prompt,
                progress=_relay_progress(progress, f"第 {ch['num']} 章分镜 {shot_start}-{shot_end}："),
                enable_streaming=False,
            )
            chapter_parts.append(f"## 分镜 {shot_start}-{shot_end}\n\n{result.strip()}")
            done_units += 1
            preview = f"# 第{ch['num']}章 {ch['title']}（{shots_per_chapter}镜）\n\n" + "\n\n".join(chapter_parts)
            current = "\n\n---\n\n".join(all_output + [preview])
            _save_result(filepath, "storyboards.md", current)
            progress(
                done_units / total_units,
                desc=f"第 {ch['num']} 章分镜 {shot_start}-{shot_end} 完成",
                content=_sse_preview(current),
            )
        all_output.append(f"# 第{ch['num']}章 {ch['title']}（{shots_per_chapter}镜）\n\n" + "\n\n".join(chapter_parts))
        current = "\n\n---\n\n".join(all_output)
        _save_result(filepath, "storyboards.md", current)
        progress(done_units / total_units, desc=f"第 {ch['num']} 章分镜完成", content=_sse_preview(current))
    final = "\n\n---\n\n".join(all_output)
    _save_result(filepath, "storyboards.md", final)
    _save_storyboard_rows(filepath, _storyboard_rows_from_markdown(final))
    return "✅ 章节分镜图提示词已生成并保存，正在加载完整内容..."


@router.post("/manju/characters")
def generate_characters(body: ManjuGenerateRequest):
    async def _gen():
        async for chunk in run_with_sse(
            _generate_characters_sync,
            body.llm_config_name, body.filepath, body.start_chapter, body.end_chapter,
            body.visual_style, body.extra_guidance,
        ):
            yield chunk
    return _sse_response(_gen())


@router.post("/manju/scenes")
def generate_scenes(body: ManjuGenerateRequest):
    async def _gen():
        async for chunk in run_with_sse(
            _generate_scenes_sync,
            body.llm_config_name, body.filepath, body.start_chapter, body.end_chapter,
            body.visual_style, body.extra_guidance,
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
