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
        config_name=llm_config_name,
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
        if content:
            progress(value, desc=message, content=content)
        else:
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
    # 模式 A：旧版逐章 scenes.md 用 "# 第N章" 标题分块
    pattern = re.compile(
        rf"(?ms)^#\s*第\s*{chapter_num}\s*章.*?(?=^#\s*第\s*\d+\s*章|\Z)"
    )
    match = pattern.search(markdown)
    if match:
        return _truncate(match.group(0), limit)

    # 模式 B：全文模式 scenes_reduce 输出 "## SC-001 ..." + "出现章节: 3, 7, 12"
    # 抽出"出现章节"包含 chapter_num 的场景块
    sc_pattern = re.compile(r"(?ms)^##\s*SC[-_]?\d+.*?(?=^##\s*SC[-_]?\d+|\Z)")
    blocks: list[str] = []
    for m in sc_pattern.finditer(markdown):
        block = m.group(0)
        ch_match = re.search(r"出现章节[：:]\s*([0-9, ，、]+)", block)
        if not ch_match:
            continue
        chapter_nums = {int(n) for n in re.findall(r"\d+", ch_match.group(1))}
        if chapter_num in chapter_nums:
            blocks.append(block.strip())
    if blocks:
        return _truncate("\n\n".join(blocks), limit)

    # 都没匹配上：返回前 limit 字（不再返回整本，避免 token 爆炸）
    return _truncate(markdown, limit)


def _segment_chapter(content: str, max_chars: int = 6000) -> list[str]:
    """把单章正文按段落软切分到不超过 max_chars 的段落，便于全文 map-reduce。"""
    text = (content or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    paragraphs = re.split(r"(?:\r?\n){2,}", text)
    segments: list[str] = []
    buf: list[str] = []
    buf_len = 0
    for para in paragraphs:
        plen = len(para) + 2
        if buf_len + plen > max_chars and buf:
            segments.append("\n\n".join(buf))
            buf = [para]
            buf_len = plen
        else:
            buf.append(para)
            buf_len += plen
    if buf:
        segments.append("\n\n".join(buf))
    # 段落过长导致单段仍超限，硬切
    final: list[str] = []
    for seg in segments:
        if len(seg) <= max_chars:
            final.append(seg)
        else:
            for i in range(0, len(seg), max_chars):
                final.append(seg[i : i + max_chars])
    return final


def _collect_character_evidence(name: str, aliases: list[str], chapters: list[dict],
                                 max_total_chars: int = 8000, max_per_chapter: int = 1200) -> str:
    """为某个角色从全文抽取相关原文段落（按名字/别名匹配）。
    不调用 LLM；纯字符串匹配，便于把'证据'喂给 character_cards 模板。"""
    if not name:
        return ""
    needles = [n for n in {name, *aliases} if n]
    if not needles:
        return ""
    evidence: list[str] = []
    total = 0
    for ch in chapters:
        content = (ch.get("content") or "").strip()
        if not content:
            continue
        # 按段落筛选包含名字的段落
        paragraphs = re.split(r"(?:\r?\n){2,}", content)
        hits = [p for p in paragraphs if any(n in p for n in needles)]
        if not hits:
            continue
        chapter_excerpt = "\n\n".join(hits)
        if len(chapter_excerpt) > max_per_chapter:
            chapter_excerpt = chapter_excerpt[:max_per_chapter] + "..."
        block = f"【第{ch.get('num')}章 {ch.get('title', '')}】\n{chapter_excerpt}"
        if total + len(block) > max_total_chars:
            remain = max_total_chars - total
            if remain > 200:
                evidence.append(block[:remain] + "...")
            break
        evidence.append(block)
        total += len(block) + 2
    return "\n\n".join(evidence)


def _parse_local_index_aliases(local_index_text: str) -> dict[str, list[str]]:
    """从 character_index_local 输出里抽取 角色名 -> 别名列表。
    格式约定：- 角色名｜重要度：…｜身份：…｜别名：a, b｜本章作用：…｜原文证据：…"""
    aliases: dict[str, list[str]] = {}
    for raw in (local_index_text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = re.sub(r"^(?:[-*+•]\s*|\d+[.、)]\s*)+", "", line).strip()
        if "｜" not in line and "|" not in line:
            continue
        sep = "｜" if "｜" in line else "|"
        parts = [p.strip() for p in line.split(sep)]
        name = parts[0] if parts else ""
        if not name:
            continue
        alias_list: list[str] = []
        for p in parts[1:]:
            if p.startswith("别名"):
                value = p.split("：", 1)[-1].split(":", 1)[-1]
                for a in re.split(r"[,，、]", value):
                    a = a.strip()
                    if a and a != "无" and a != "空":
                        alias_list.append(a)
                break
        aliases.setdefault(name, []).extend(a for a in alias_list if a not in aliases[name])
    return aliases


def _character_lock_context(filepath: str, fallback: str) -> str:
    cards = [c for c in _load_characters_structured(filepath) if c.get("locked", True)]
    if not cards:
        return fallback
    lines = []
    for card in cards:
        # 仅保留新模板里实际还有值的字段；空字段不输出，避免膨胀锁定块
        parts = [f"【{card.get('name', '')}】"]
        for label, key in [
            ("身份", "identity"),
            ("外貌锁定", "appearance"),
            ("服装锁定", "costume"),
            ("画面描述", "prompt_positive"),
            ("负向提示词", "prompt_negative"),
        ]:
            value = str(card.get(key) or "").strip()
            if value:
                parts.append(f"{label}：{value}")
        lines.append("\n".join(parts))
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
                              visual_style: str, extra_guidance: str, full_scan: bool, progress):
    from .parser import _characters_from_markdown  # avoid circular at module level

    chapters = _chapter_window(_load_chapters(filepath), start_chapter, end_chapter)
    if not chapters:
        return "❌ 请先导入小说 TXT"
    llm = _llm_adapter(llm_config_name)

    if full_scan:
        return _generate_characters_full_scan(
            llm, llm_config_name, filepath, chapters, visual_style, extra_guidance, progress,
            _characters_from_markdown_fn=_characters_from_markdown,
        )

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
            character_evidence="（非全文扫描模式，无证据片段；请仅依据章节摘录与角色索引重建外观）",
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
# Characters: full-scan map-reduce path
# ---------------------------------------------------------------------------

def _generate_characters_full_scan(llm, llm_config_name: str, filepath: str, chapters: list[dict],
                                   visual_style: str, extra_guidance: str, progress,
                                   _characters_from_markdown_fn) -> str:
    """全文扫描模式：每章 Map -> 全局 Reduce -> 每角色证据收集 -> 角色卡。"""
    total_chapters = len(chapters)
    if total_chapters == 0:
        return "❌ 请先导入小说 TXT"

    # 阶段 1：Map - 每章本地角色识别
    progress(0.01, desc=f"全文扫描：开始扫描 {total_chapters} 章本地角色...")
    local_indexes: list[str] = []
    aliases_acc: dict[str, list[str]] = {}
    for ch_idx, ch in enumerate(chapters, 1):
        prompt = _manju_instruction(
            "character_index_local",
            chapter_num=ch.get("num"),
            chapter_title=ch.get("title", ""),
            chapter_content=_truncate(ch.get("content") or "", 12000),
            extra_guidance=extra_guidance or "无",
        )
        progress(
            0.02 + 0.30 * (ch_idx - 1) / max(total_chapters, 1),
            desc=f"扫描第 {ch.get('num')} 章本地角色 ({ch_idx}/{total_chapters})",
        )
        local = invoke_with_cleaning(
            llm, prompt, progress=_relay_progress(progress, f"第 {ch.get('num')} 章本地角色："),
            enable_streaming=False,
        )
        local_indexes.append(f"## 第 {ch.get('num')} 章 {ch.get('title', '')}\n\n{local.strip()}")
        # 把本章 alias 累加，用于后续证据收集
        for name, lst in _parse_local_index_aliases(local).items():
            aliases_acc.setdefault(name, [])
            for a in lst:
                if a not in aliases_acc[name]:
                    aliases_acc[name].append(a)

    progress(0.32, desc="本地角色扫描完成，正在跨章合并去重...", content="\n\n".join(local_indexes[-3:]))

    # 阶段 2：Reduce - 跨章合并
    reduce_prompt = _manju_instruction(
        "character_index_reduce",
        extra_guidance=extra_guidance or "无",
        per_chapter_indexes=_truncate("\n\n".join(local_indexes), 60000),
    )
    index_result = invoke_with_cleaning(
        llm, reduce_prompt, progress=_relay_progress(progress, "跨章合并："),
        enable_streaming=False,
    )
    progress(0.40, desc="跨章合并完成", content=index_result)

    # 把 reduce 结果里的 alias 也吸收一遍
    for name, lst in _parse_local_index_aliases(index_result).items():
        aliases_acc.setdefault(name, [])
        for a in lst:
            if a not in aliases_acc[name]:
                aliases_acc[name].append(a)

    names = _extract_character_names(index_result)
    if not names:
        # 极端兜底
        progress(0.45, desc="跨章索引解析失败，回退完整角色库生成")
        full_source = _chapter_digest_balanced(chapters, 30000)
        fallback_prompt = _manju_instruction(
            "character_fallback", visual_style=visual_style,
            extra_guidance=extra_guidance or "无", source=full_source,
        )
        result = invoke_with_cleaning(llm, fallback_prompt, progress=progress)
        _save_result(filepath, "characters.md", result)
        _save_characters_structured(filepath, _characters_from_markdown_fn(result))
        return result

    # 阶段 3：每个角色全文证据收集（不调 LLM）+ 分批角色卡（Map）
    sections = [f"# 角色索引（全文模式）\n\n{index_result.strip()}", "# 角色信息与角色卡提示词"]
    # 全文模式下大幅压缩 source，把 token 预算让给 character_evidence
    full_source = _chapter_digest_balanced(chapters, 8000)
    # 全文模式下每批角色数从 4 减到 2，避免输出超 max_tokens 截断
    batches = list(_chunked(names, 2))
    total_batches = max(len(batches), 1)
    for batch_idx, batch in enumerate(batches, 1):
        batch_names = "、".join(batch)
        evidence_blocks: list[str] = []
        for nm in batch:
            ev = _collect_character_evidence(
                nm, aliases_acc.get(nm, []), chapters,
                max_total_chars=2500, max_per_chapter=600,
            )
            if ev:
                evidence_blocks.append(f"### {nm}\n\n{ev}")
            else:
                evidence_blocks.append(f"### {nm}\n\n（全文未找到该角色名相关段落，请基于章节摘录与改编补全）")
        progress(
            0.45 + 0.50 * (batch_idx - 1) / total_batches,
            desc=f"生成角色卡第 {batch_idx}/{total_batches} 批：{batch_names}",
        )
        card_prompt = _manju_instruction(
            "character_cards",
            batch_names=batch_names,
            batch_list=chr(10).join(f"- {name}" for name in batch),
            visual_style=visual_style,
            extra_guidance=extra_guidance or "无",
            index_result=_truncate(index_result, 6000),
            source=full_source,
            character_evidence=_truncate("\n\n".join(evidence_blocks), 6000),
        )
        result = invoke_with_cleaning(
            llm, card_prompt, progress=_relay_progress(progress, f"角色卡第 {batch_idx}/{total_batches} 批："),
        )
        sections.append(f"## 第 {batch_idx} 批：{batch_names}\n\n{result.strip()}")
        progress(
            0.45 + 0.50 * batch_idx / total_batches,
            desc=f"角色卡第 {batch_idx}/{total_batches} 批完成",
            content="\n\n".join(sections),
        )

    final = "\n\n".join(sections)
    _save_result(filepath, "characters.md", final)
    _save_characters_structured(filepath, _characters_from_markdown_fn(final))
    return final


# ---------------------------------------------------------------------------
# Scenes sync generator
# ---------------------------------------------------------------------------

def _generate_scenes_sync(llm_config_name: str, filepath: str, start_chapter: int, end_chapter: int | None,
                          visual_style: str, extra_guidance: str, full_scan: bool, progress):
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

    if full_scan:
        return _generate_scenes_full_scan(
            llm, filepath, chapters, visual_style, characters, extra_guidance, progress,
        )

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
# Scenes: full-scan map-reduce path
# ---------------------------------------------------------------------------

def _generate_scenes_full_scan(llm, filepath: str, chapters: list[dict], visual_style: str,
                               characters: str, extra_guidance: str, progress) -> str:
    """全文扫描模式：每章按段 Map -> 跨章 Reduce 去重 -> 输出场景库。"""
    from .parser import _scenes_from_markdown, _save_scenes_structured

    if not chapters:
        return "❌ 请先导入小说 TXT"

    # 阶段 1：Map - 每章按段识别本地场景
    progress(0.01, desc=f"全文扫描：开始扫描 {len(chapters)} 章本地场景...")
    local_blocks: list[str] = []
    chapter_segment_jobs: list[tuple[dict, int, int, str]] = []
    for ch in chapters:
        segments = _segment_chapter(ch.get("content") or "", max_chars=6000)
        if not segments:
            continue
        for s_idx, seg in enumerate(segments, 1):
            chapter_segment_jobs.append((ch, s_idx, len(segments), seg))

    total_jobs = max(len(chapter_segment_jobs), 1)
    for idx, (ch, s_idx, s_total, seg) in enumerate(chapter_segment_jobs, 1):
        prompt = _manju_instruction(
            "scenes_local",
            chapter_num=ch.get("num"),
            chapter_title=ch.get("title", ""),
            segment_index=s_idx,
            segment_count=s_total,
            chapter_segment=seg,
            visual_style=visual_style,
            characters=_truncate(characters, 8000),
            extra_guidance=extra_guidance or "无",
        )
        progress(
            0.02 + 0.55 * (idx - 1) / total_jobs,
            desc=f"扫描第 {ch.get('num')} 章 第 {s_idx}/{s_total} 段场景 ({idx}/{total_jobs})",
        )
        local = invoke_with_cleaning(
            llm, prompt, progress=_relay_progress(progress, f"第{ch.get('num')}章·段{s_idx}场景："),
            enable_streaming=False,
        )
        local_blocks.append(
            f"## 第 {ch.get('num')} 章 {ch.get('title', '')} · 第 {s_idx}/{s_total} 段\n\n{local.strip()}"
        )
        # 把渐进结果保存到 scenes_local.md 便于断点观察
        _save_result(filepath, "scenes_local.md", "\n\n---\n\n".join(local_blocks))

    progress(0.60, desc="本地场景扫描完成，正在跨章去重合并...", content=_sse_preview("\n\n".join(local_blocks[-3:])))

    # 阶段 2：Reduce - 跨章合并去重
    reduce_prompt = _manju_instruction(
        "scenes_reduce",
        visual_style=visual_style,
        characters=_truncate(characters, 6000),
        extra_guidance=extra_guidance or "无",
        per_segment_scenes=_truncate("\n\n".join(local_blocks), 30000),
    )
    reduced = invoke_with_cleaning(
        llm, reduce_prompt, progress=_relay_progress(progress, "跨章场景合并："),
        enable_streaming=False,
    )
    progress(0.95, desc="跨章场景合并完成，正在保存结构化场景库...", content=_sse_preview(reduced))

    # 持久化：scenes.md（合并后）+ scenes.json（结构化）+ scenes_local.md（中间产物）
    _save_result(filepath, "scenes.md", reduced)
    structured = _scenes_from_markdown(reduced)
    _save_scenes_structured(filepath, structured)
    progress(1.0, desc=f"✅ 全文场景库已生成（{len(structured)} 个场景）", content=_sse_preview(reduced))
    return "✅ 章节场景图提示词（全文模式）已生成并保存，正在加载完整内容..."


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
                                     target_chapters: int, target_scenes: int, target_leads: int,
                                     target_supporting_cast: int, rename_characters: bool, adaptation_level: str,
                                     episode_duration: str, script_style: str, extra_guidance: str, progress):
    from .export import _normalize_reimportable_chapter  # avoid circular

    chapters = _chapter_window(_load_chapters(filepath), start_chapter, end_chapter)
    target_chapters = max(1, min(int(target_chapters or 12), 120))
    target_scenes = max(1, min(int(target_scenes or 30), 500))
    target_leads = max(1, min(int(target_leads or 2), 20))
    target_supporting_cast = max(0, min(int(target_supporting_cast or 6), 50))
    llm = _llm_adapter(llm_config_name)
    source_digest = _chapter_digest_balanced(chapters, 42000)
    rename_rule = "允许根据漫剧传播效果重命名人物，但正文中只使用新名字，不要输出原名-新名对照表。" if rename_characters else "不得修改人物名称，必须沿用小说原名。"
    progress(0.03, desc="正在规划漫剧正文改编结构...")

    outline_prompt = _manju_instruction(
        "script_outline",
        target_chapters=target_chapters,
        target_scenes=target_scenes,
        target_leads=target_leads,
        target_supporting_cast=target_supporting_cast,
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
            target_scenes=target_scenes,
            target_leads=target_leads,
            target_supporting_cast=target_supporting_cast,
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
