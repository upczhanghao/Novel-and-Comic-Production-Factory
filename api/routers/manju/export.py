# api/routers/manju/export.py
# -*- coding: utf-8 -*-
"""Script export filename helpers, attachment header, script normalization,
content export path, markdown prompt item collection, flatten export rows,
CSV/XLSX response builders."""

import csv
import io
import json
import os
import re
import zipfile
from typing import Any
from urllib.parse import quote

from fastapi import HTTPException
from fastapi.responses import Response

from .parser import (
    _load_characters_structured,
    _load_storyboard_rows,
    _read_json,
    _read_text,
    _work_dir,
)
from .prompts import (
    _build_character_image_prompt,
    _build_storyboard_image_prompt,
)


# ---------------------------------------------------------------------------
# Script filename / attachment header
# ---------------------------------------------------------------------------

def _script_filename(filepath: str) -> str:
    meta = _read_json(os.path.join(_work_dir(filepath), "meta.json"), {}) or {}
    raw_name = os.path.splitext(str(meta.get("filename") or "manju_script"))[0]
    safe = re.sub(r'[\\/:*?"<>|\s]+', "_", raw_name).strip("_") or "manju_script"
    return f"{safe}_漫剧改编剧本.txt"


def _attachment_header(filename: str, fallback: str = "download.txt") -> str:
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "_", fallback).strip("_") or "download.txt"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


# ---------------------------------------------------------------------------
# Script normalization / stripping boilerplate
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Content export path
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Markdown prompt item collection
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Flatten export rows
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# CSV / XLSX response builders
# ---------------------------------------------------------------------------

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
