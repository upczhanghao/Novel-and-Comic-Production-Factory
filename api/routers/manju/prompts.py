# api/routers/manju/prompts.py
# -*- coding: utf-8 -*-
"""Prompt building helpers: character/storyboard image prompts, style templates,
visual lock, quality flags, enhance utilities."""

import re
from typing import Any

from .parser import (
    _load_characters_structured,
    _load_settings,
    _load_storyboard_rows,
    _read_json,
    _save_characters_structured,
    _save_storyboard_rows,
    _style_templates_path,
)


DEFAULT_MANJU_NEGATIVE_PROMPT = (
    "low quality, blurry, bad anatomy, distorted face, deformed hands, extra fingers, "
    "extra limbs, duplicate character, inconsistent outfit, wrong hair color, wrong costume, "
    "text, watermark, logo, cropped head, out of frame"
)


def _compact_text(*parts: Any) -> str:
    text = "，".join(str(part).strip() for part in parts if str(part or "").strip())
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ，,")


def _visual_style_for(filepath: str) -> str:
    return _load_settings(filepath).get(
        "visual_style",
        "vertical manhua panel, cinematic composition, consistent character design, high detail",
    )


def _negative_prompt(*parts: Any) -> str:
    custom = ", ".join(str(part).strip() for part in parts if str(part or "").strip())
    return f"{custom}, {DEFAULT_MANJU_NEGATIVE_PROMPT}" if custom else DEFAULT_MANJU_NEGATIVE_PROMPT


def _find_character_cards(filepath: str, text: str) -> list[dict[str, Any]]:
    cards = _load_characters_structured(filepath)
    if not text:
        return []
    return [card for card in cards if card.get("name") and str(card.get("name")) in text]


def _character_visual_lock(card: dict[str, Any]) -> str:
    return _compact_text(
        card.get("name"),
        card.get("identity"),
        card.get("appearance"),
        card.get("costume"),
        card.get("expression"),
        card.get("actions"),
        f"must keep unchanged: {card.get('do_not_change', '')}" if card.get("do_not_change") else "",
    )


def _build_character_image_prompt(filepath: str, card: dict[str, Any]) -> tuple[str, str]:
    visual_style = _visual_style_for(filepath)
    prompt = _compact_text(
        "single full-body character standing portrait",
        "one character only, head-to-toe view, entire body visible, clean readable silhouette",
        _character_visual_lock(card),
        "neutral standing pose, signature expression, simple clean background, no panels",
        visual_style,
        "high detail, sharp focus, professional concept art, consistent design for reuse",
    )
    return prompt, _negative_prompt(
        card.get("prompt_negative"),
        "close-up, bust portrait, multiple poses, split view, character sheet layout, multiple panels, multiple people, busy background",
    )


def _build_storyboard_image_prompt(filepath: str, row: dict[str, Any]) -> tuple[str, str]:
    visual_style = _visual_style_for(filepath)
    character_text = _compact_text(row.get("characters"), row.get("subject"), row.get("prompt_positive"))
    locks = [_character_visual_lock(card) for card in _find_character_cards(filepath, character_text)]
    lock_text = " | ".join(lock for lock in locks if lock)
    prompt = _compact_text(
        "vertical manhua storyboard frame, 9:16 composition",
        row.get("camera"),
        row.get("composition"),
        row.get("subject"),
        row.get("characters"),
        lock_text,
        row.get("location"),
        row.get("light"),
        row.get("continuity"),
        visual_style,
        "clear focal point, cinematic lighting, expressive face, dynamic but readable action",
        "no speech bubbles unless explicitly requested",
        row.get("prompt_positive"),
    )
    return prompt, _negative_prompt(row.get("prompt_negative"))


def _quality_flags(prompt: str, negative: str) -> list[str]:
    issues = []
    checks = {
        "缺少镜头/景别": r"(close-up|medium|wide|特写|近景|中景|远景|全景|景别)",
        "缺少构图": r"(composition|构图|居中|三分法|俯拍|仰拍|侧逆光|对称|纵深)",
        "缺少光线": r"(lighting|light|光|夜|晨|夕阳|霓虹|烛火|阴影)",
        "缺少风格媒介": r"(manhua|manga|anime|comic|国漫|日漫|漫画|概念图|concept art)",
    }
    for label, pattern in checks.items():
        if not re.search(pattern, prompt, re.IGNORECASE):
            issues.append(label)
    if len(prompt) < 120:
        issues.append("提示词过短")
    if not negative or len(negative) < 40:
        issues.append("负向词不足")
    return issues


def _enhance_character_prompts(filepath: str, overwrite_locked: bool = False) -> tuple[int, list[dict[str, Any]]]:
    cards = _load_characters_structured(filepath)
    changed = 0
    for card in cards:
        if card.get("locked") and not overwrite_locked:
            continue
        prompt, negative = _build_character_image_prompt(filepath, card)
        card["prompt_positive"] = prompt
        card["prompt_negative"] = negative
        card["prompt_quality_flags"] = _quality_flags(prompt, negative)
        changed += 1
    _save_characters_structured(filepath, cards)
    return changed, cards


def _enhance_storyboard_prompts(filepath: str, overwrite_locked: bool = False) -> tuple[int, list[dict[str, Any]]]:
    rows = _load_storyboard_rows(filepath)
    changed = 0
    for row in rows:
        if row.get("locked") and not overwrite_locked:
            continue
        prompt, negative = _build_storyboard_image_prompt(filepath, row)
        row["prompt_positive"] = prompt
        row["prompt_negative"] = negative
        row["prompt_quality_flags"] = _quality_flags(prompt, negative)
        changed += 1
    _save_storyboard_rows(filepath, rows)
    return changed, rows


# ---------------------------------------------------------------------------
# Style templates
# ---------------------------------------------------------------------------

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
