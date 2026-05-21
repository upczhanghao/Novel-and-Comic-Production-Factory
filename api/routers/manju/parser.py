# api/routers/manju/parser.py
# -*- coding: utf-8 -*-
"""TXT decoding, chapter parsing, settings normalization, structured load/save,
markdown table parsing, JSON I/O helpers, path helpers."""

import json
import os
import re
from typing import Any

from fastapi import HTTPException

from api.security import normalize_project_path, safe_join


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

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


def _settings_path(filepath: str) -> str:
    return os.path.join(_work_dir(filepath), "settings.json")


# ---------------------------------------------------------------------------
# JSON / text I/O
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# TXT decoding
# ---------------------------------------------------------------------------

def _decode_upload(data: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "gb18030", "gbk", "big5"):
        try:
            text = data.decode(enc)
            if text.strip():
                return text
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Chapter parsing
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Settings normalization
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Markdown parsing helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Structured load/save
# ---------------------------------------------------------------------------

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
            r"(?m)^\s*(?:#{2,6}\s*)?(?:[-*]\s*)?(?:(?:分镜|镜号)\s*[：:]?\s*)?([0-9]+)(?!\s*[-~－—]\s*)(?:\s*[.、]\s*)?(?:镜号)?(?:\s*[：:].*)?$",
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
