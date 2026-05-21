# api/routers/manju/pipeline.py
# -*- coding: utf-8 -*-
"""Script adaptation sync generator, LLM adapter helper, progress relay,
character/scene/storyboard generation sync functions."""

import re
from typing import Any

from api.app_state import get_web_app
from api.manju_instruction_templates import render_manju_instruction
from llm_adapters import create_llm_adapter
from novel_generator.common import invoke_with_cleaning
from utils import save_string_to_txt

from .parser import (
    _chapter_window,
    _load_chapters,
    _load_characters_structured,
    _load_storyboard_rows,
    _save_characters_structured,
    _save_storyboard_rows,
    _script_outline_path,
    _script_path,
    _storyboard_rows_from_markdown,
    _work_dir,
)
from .prompts import _build_storyboard_image_prompt


# ---------------------------------------------------------------------------
# LLM adapter
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Instruction helper
# ---------------------------------------------------------------------------

def _manju_instruction(key: str, **values: Any) -> str:
    return render_manju_instruction(get_web_app().config, key, values)


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------

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
        candidate = re.split(r"[：:，,；;（([\[【\s\-—]", candidate, 1)[0].strip()
        candidate = candidate.strip('《》“”\\"\'`')
        if not candidate or candidate in ignored:
            continue
        if len(candidate) > 16 or not re.search(r"[一-鿿A-Za-z0-9]", candidate):
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


# ---------------------------------------------------------------------------
# Save result helper
# ---------------------------------------------------------------------------

def _save_result(filepath: str, filename: str, content: str) -> None:
    import os
    path = os.path.join(_work_dir(filepath), filename)
    save_string_to_txt(content, path)


# ---------------------------------------------------------------------------
# Characters sync generator
# ---------------------------------------------------------------------------

def _generate_characters_sync(llm_config_name: str, filepath: str, start_chapter: int, end_chapter: int | None,
                              visual_style: str, extra_guidance: str, progress):
    from .parser import _characters_from_markdown  # avoid circular at module level

    chapters = _chapter_window(_load_chapters(filepath), start_chapter, end_chapter)
    if not chapters:
        return "❌ 请先导入小说 TXT"
    llm = _llm_adapter(llm_config_name)
    source = _chapter_digest_balanced(chapters, 30000)
    progress(0.02, desc="正在识别小说角色总表...")

    def build_index_prompt(chapter_source: str, scope: str) -> str:
        return _manju_instruction(
            "character_index",
            scope=scope,
            extra_guidance=extra_guidance or "无",
            chapter_source=chapter_source,
        )

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
        fallback_prompt = _manju_instruction(
            "character_fallback",
            visual_style=visual_style,
            extra_guidance=extra_guidance or "无",
            source=source,
        )
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
        card_prompt = _manju_instruction(
            "character_cards",
            batch_names=batch_names,
            batch_list=chr(10).join(f"- {name}" for name in batch),
            visual_style=visual_style,
            extra_guidance=extra_guidance or "无",
            index_result=_truncate(index_result, 12000),
            source=source,
        )
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


# ---------------------------------------------------------------------------
# Scenes sync generator
# ---------------------------------------------------------------------------

def _generate_scenes_sync(llm_config_name: str, filepath: str, start_chapter: int, end_chapter: int | None,
                          visual_style: str, extra_guidance: str, progress):
    # Import here to avoid circular dependency with routes
    from .routes import manju_status  # noqa: F401 — resolved at call-time

    chapters = _chapter_window(_load_chapters(filepath), start_chapter, end_chapter)
    llm = _llm_adapter(llm_config_name)

    # Inline the status lookup to avoid circular imports
    import os
    from .parser import _read_text, _work_dir as _wd
    work_dir = _wd(filepath)
    chars_path = os.path.join(work_dir, "characters.md")
    characters_md = _read_text(chars_path) if os.path.exists(chars_path) else "尚未生成角色卡，请根据章节临时保持角色一致。"
    characters = _character_lock_context(filepath, characters_md)

    all_output = []
    for idx, ch in enumerate(chapters, 1):
        progress(idx / max(len(chapters), 1), desc=f"正在生成第 {ch['num']} 章场景图提示词...")
        prompt = _manju_instruction(
            "scenes",
            chapter_num=ch["num"],
            chapter_title=ch["title"],
            chapter_content=_truncate(ch["content"], 12000),
            visual_style=visual_style,
            characters=_truncate(characters, 12000),
            extra_guidance=extra_guidance or "无",
        )
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


# ---------------------------------------------------------------------------
# Storyboards sync generator
# ---------------------------------------------------------------------------

def _generate_storyboards_sync(llm_config_name: str, filepath: str, start_chapter: int, end_chapter: int | None,
                               shots_per_chapter: int, visual_style: str, extra_guidance: str, progress):
    import os
    from .parser import _read_text, _work_dir as _wd

    chapters = _chapter_window(_load_chapters(filepath), start_chapter, end_chapter)
    shots_per_chapter = max(1, min(int(shots_per_chapter or 12), 80))
    llm = _llm_adapter(llm_config_name)

    work_dir = _wd(filepath)
    chars_path = os.path.join(work_dir, "characters.md")
    scenes_path = os.path.join(work_dir, "scenes.md")
    characters_md = _read_text(chars_path) if os.path.exists(chars_path) else "尚未生成角色卡，请根据章节临时保持角色一致。"
    characters = _character_lock_context(filepath, characters_md)
    scenes = _read_text(scenes_path) if os.path.exists(scenes_path) else "尚未生成场景图提示词，请直接根据章节内容拆分。"

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
            prompt = _manju_instruction(
                "storyboards",
                shots_per_chapter=shots_per_chapter,
                shot_start=shot_start,
                shot_end=shot_end,
                batch_count=batch_count,
                previous_context=previous_context or "暂无，这是本章第一批分镜。",
                visual_style=visual_style,
                characters=_truncate(characters, 12000),
                chapter_scenes=chapter_scenes or "尚未生成本章场景图提示词，请直接根据章节内容拆分。",
                extra_guidance=extra_guidance or "无",
                chapter_num=ch["num"],
                chapter_title=ch["title"],
                chapter_content=_truncate(ch["content"], 14000),
            )
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


# ---------------------------------------------------------------------------
# Script adaptation sync generator
# ---------------------------------------------------------------------------

def _generate_script_adaptation_sync(llm_config_name: str, filepath: str, start_chapter: int, end_chapter: int | None,
                                     target_chapters: int, rename_characters: bool, adaptation_level: str,
                                     episode_duration: str, script_style: str, extra_guidance: str, progress):
    from .export import _normalize_reimportable_chapter  # avoid circular

    chapters = _chapter_window(_load_chapters(filepath), start_chapter, end_chapter)
    target_chapters = max(1, min(int(target_chapters or 12), 120))
    llm = _llm_adapter(llm_config_name)
    source_digest = _chapter_digest_balanced(chapters, 42000)
    rename_rule = "允许根据漫剧传播效果重命名人物，但正文中只使用新名字，不要输出原名-新名对照表。" if rename_characters else "不得修改人物名称，必须沿用小说原名。"
    progress(0.03, desc="正在规划漫剧正文改编结构...")

    outline_prompt = _manju_instruction(
        "script_outline",
        target_chapters=target_chapters,
        rename_rule=rename_rule,
        adaptation_level=adaptation_level,
        episode_duration=episode_duration,
        script_style=script_style,
        extra_guidance=extra_guidance or "无",
        source_digest=source_digest,
    )
    outline = invoke_with_cleaning(llm, outline_prompt, progress=_relay_progress(progress, "正文目录："))
    save_string_to_txt(outline, _script_outline_path(filepath))

    outputs: list[str] = []
    previous_script = ""
    for episode in range(1, target_chapters + 1):
        progress(0.08 + 0.88 * (episode - 1) / target_chapters, desc=f"正在改编第 {episode}/{target_chapters} 章漫剧剧本...")
        episode_prompt = _manju_instruction(
            "script_episode",
            episode=episode,
            target_chapters=target_chapters,
            rename_rule=rename_rule,
            adaptation_level=adaptation_level,
            script_style=script_style,
            extra_guidance=extra_guidance or "无",
            outline=_truncate(outline, 18000),
            previous_script=_truncate(previous_script, 5000) if previous_script else "暂无，这是第一章。",
            source_digest=source_digest,
        )
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
