# api/manju_instruction_templates.py
# -*- coding: utf-8 -*-
"""Configurable AI instruction templates for the Manju workflow."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


DEFAULT_MANJU_INSTRUCTION_TEMPLATES: dict[str, dict[str, Any]] = {
    "script_outline": {
        "title": "小说改编漫剧剧本：目录规划",
        "description": "用于把原小说摘录规划为可再次导入系统的漫剧正文目录。",
        "variables": [
            "target_chapters",
            "rename_rule",
            "adaptation_level",
            "episode_duration",
            "script_style",
            "extra_guidance",
            "source_digest",
        ],
        "content": """你是小说改编策划。请把小说内容规划为可再次导入系统的漫剧小说正文目录。

改编参数：
- 目标剧本章节数：{target_chapters} 章
- 人物名称规则：{rename_rule}
- 剧情改编幅度：{adaptation_level}
- 单章篇幅/节奏参考：{episode_duration}
- 改编风格：{script_style}
- 补充要求：{extra_guidance}

硬性要求：
1. 只输出 {target_chapters} 行目录，编号 1-{target_chapters}，不能多也不能少。
2. 每行格式：第X章 标题｜本章剧情一句话。
3. 不要输出改编原则、人物表、说明、Markdown 表格、分镜、场次。
4. 改编要增强冲突、反转、爽点、情绪钩子，但不能破坏主线逻辑。

小说章节摘录：
{source_digest}
""",
    },
    "script_episode": {
        "title": "小说改编漫剧剧本：逐章正文",
        "description": "用于根据目录和原文摘录生成每一章漫剧改编正文。",
        "variables": [
            "episode",
            "target_chapters",
            "rename_rule",
            "adaptation_level",
            "script_style",
            "extra_guidance",
            "outline",
            "previous_script",
            "source_digest",
        ],
        "content": """你是小说改编作者。请根据目录和原文摘录，只创作第 {episode} 章的漫剧改编正文。

硬性要求：
1. 输出必须是可再次导入的 TXT 小说正文格式。
2. 第一行必须且只能是章节标题，格式严格为：第{episode}章 标题。
3. 标题下一行开始直接写剧情正文，可以包含自然对白，但不要写“场次、画面说明、分镜提示、角色表、剧情节拍、旁白/字幕、情绪点、改编说明”等制作信息。
4. 不要使用 Markdown 标题符号，不要输出列表，不要输出表格，不要解释。
5. 人物名称规则：{rename_rule}
6. 剧情改编幅度：{adaptation_level}。改编可以增强戏剧性，但必须保持主线因果清晰。
7. 风格参考：{script_style}。重点是剧情可读、冲突清晰、适合后续模块继续生成角色图/场景图/分镜图。
8. 结尾要有自然的章节钩子，但仍然写成小说正文。

补充要求：
{extra_guidance}

改编目录：
{outline}

上一章正文结尾：
{previous_script}

小说章节摘录：
{source_digest}
""",
    },
    "character_index": {
        "title": "角色信息与角色卡：角色索引",
        "description": "用于先从小说摘录中识别影响剧情和画面连续性的角色列表。",
        "variables": ["scope", "extra_guidance", "chapter_source"],
        "content": """你是资深漫剧改编导演。请先根据小说摘录建立“角色索引”，用于后续分批生成角色卡。

硬性要求：
1. 尽量识别{scope}内所有会影响剧情或画面连续性的角色，包括主角、核心配角、反派、功能性角色。
2. 不要把地点、势力、物品、章节名当成角色。
3. 只输出角色索引，不要输出详细角色卡。
4. 每行必须严格使用以下格式，方便程序读取：
- 角色名｜重要度：主角/核心配角/反派/功能性角色｜身份：一句话身份｜首次/主要出场：章节号或章节名｜依据：原文线索简述

补充要求：
{extra_guidance}

小说章节摘录：
{chapter_source}
""",
    },
    "character_fallback": {
        "title": "角色信息与角色卡：完整角色库",
        "description": "当角色索引解析不稳定时，用于一次性生成完整角色资料库。",
        "variables": ["visual_style", "extra_guidance", "source"],
        "content": """你是资深漫剧改编导演和角色设定师。请根据整本小说内容，整理适合“漫剧/短剧分镜/AI绘图”的角色资料库。

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
{extra_guidance}

小说章节摘录：
{source}
""",
    },
    "character_cards": {
        "title": "角色信息与角色卡：分批角色卡",
        "description": "用于为已识别角色分批生成角色信息与角色卡生图提示词。",
        "variables": [
            "batch_names",
            "batch_list",
            "visual_style",
            "extra_guidance",
            "index_result",
            "source",
        ],
        "content": """你是资深漫剧角色设定师和 AI 生图提示词工程师。请只为“本批角色”生成细致角色信息与角色卡提示词。

本批角色：
{batch_list}

硬性要求：
1. 必须逐个输出本批全部角色，顺序与上方一致，不得合并、不得省略。
2. 每个角色都要包含：剧情身份、性格关键词、人物弧光、与其他角色关系、首次/主要出场章节、外貌固定设定、服装固定设定、表情气质、动作习惯、禁忌变化点。
3. 每个角色必须生成可复用的“角色卡提示词”，细到年龄感、脸型、发型发色、体型、服装材质/颜色、标志物、表情、气质、镜头偏好。
4. 原文未明确的信息可以合理改编补全，但必须标注“改编补全”。
5. 不得写“同上”“略”“其余角色类似”“后续继续”等省略表达。
6. 正向提示词必须是可直接给文生图模型使用的画面语言，避免剧情解释；目标是“单张全身角色立绘”，必须包含：single full-body character standing portrait、one character only、head-to-toe view、年龄感、脸型、发型发色、体型、服装材质颜色、标志物、表情气质、简单干净背景、统一视觉风格。
7. 禁止生成多视图角色设定表、半身特写拼贴、表情九宫格、分屏构图；负向提示词必须包含：close-up, bust portrait, multiple poses, split view, character sheet layout, low quality, blurry, bad anatomy, deformed hands, extra fingers, inconsistent outfit, wrong hair color, text, watermark。

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
{extra_guidance}

角色索引：
{index_result}

小说章节摘录：
{source}
""",
    },
    "scenes": {
        "title": "章节场景图提示词",
        "description": "用于把章节拆成适合 AI 绘图/场景概念图的场景资产库。",
        "variables": [
            "chapter_num",
            "chapter_title",
            "chapter_content",
            "visual_style",
            "characters",
            "extra_guidance",
        ],
        "content": """你是漫剧美术导演和 AI 生图提示词工程师。请把下面章节拆成适合 AI 绘图/场景概念图的“场景资产库”。

输出要求：
- 每章列出 6-12 个关键场景，不要遗漏主要剧情转场。
- 每个场景包含：场景编号、剧情作用、地点、时间/光线、环境元素、出现角色、人物站位、情绪氛围、镜头景别、正向绘图提示词、负向提示词。
- 必须严格引用下方“角色一致性锁定表”，保持角色外貌、服装、气质、禁忌变化点一致。
- 不要写成小说正文，要写成可直接给绘图模型使用的提示词。
- 正向提示词必须按“主体/空间 + 人物站位 + 镜头景别 + 构图 + 光线色彩 + 风格媒介 + 画质约束”组织。
- 禁止只写抽象词，如“紧张氛围”“很震撼”；必须转化成可见画面元素。
- 负向提示词必须包含：low quality, blurry, bad anatomy, distorted face, text, watermark, logo。

全局视觉风格：
{visual_style}

角色一致性锁定表：
{characters}

补充要求：
{extra_guidance}

章节：
第{chapter_num}章 {chapter_title}
{chapter_content}
""",
    },
    "storyboards": {
        "title": "章节分镜图提示词",
        "description": "用于根据章节内容、角色锁定表和场景提示词生成连续分镜。",
        "variables": [
            "shots_per_chapter",
            "shot_start",
            "shot_end",
            "batch_count",
            "previous_context",
            "visual_style",
            "characters",
            "chapter_scenes",
            "extra_guidance",
            "chapter_num",
            "chapter_title",
            "chapter_content",
        ],
        "content": """你是漫剧分镜导演、摄影指导和 AI 生图提示词工程师。请根据章节内容生成连续分镜图提示词。

硬性要求：
1. 本章总分镜数为 {shots_per_chapter}。本次只输出全局编号 {shot_start}-{shot_end}，共 {batch_count} 个分镜，不能多也不能少。
2. 每个分镜必须使用全局编号，不要从 1 重新编号，除非本批从 1 开始。
3. 分镜必须覆盖完整剧情：开场交代、冲突推进、关键动作、情绪反应、信息揭示、结尾钩子。
4. 本批要承接已完成分镜，必须严格引用“角色一致性锁定表”，保持角色、服饰、道具、空间方向、情绪递进连续。
5. 不得写“略”“同上”“后续继续”“省略若干镜头”等省略表达。
6. 如果本批包含最后一个镜头（编号 {shots_per_chapter}），最后一镜必须形成本章结尾钩子或情绪落点。
7. 正向绘图提示词必须只写画面，不写剧情解释；必须包含：vertical manhua storyboard frame、镜头景别、机位/构图、角色锁定特征、动作表情、背景场景、光影色彩、统一视觉风格、high detail。
8. 分镜提示词必须避免泛泛描述，不要只写“某人很震惊”，要写具体表情、姿势、视线方向、手部动作和画面焦点。
9. 负向提示词必须包含：low quality, blurry, bad anatomy, deformed hands, extra fingers, inconsistent outfit, text, watermark。

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
{previous_context}

全局视觉风格：
{visual_style}

角色一致性锁定表：
{characters}

本章已有场景提示词：
{chapter_scenes}

补充要求：
{extra_guidance}

章节：
第{chapter_num}章 {chapter_title}
{chapter_content}
""",
    },
}


def _saved_templates(config: dict[str, Any]) -> dict[str, Any]:
    root = config.setdefault("instruction_templates", {})
    manju = root.setdefault("manju", {})
    return manju if isinstance(manju, dict) else {}


def list_manju_instruction_templates(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    saved = _saved_templates(config)
    templates: dict[str, dict[str, Any]] = {}
    for key, default in DEFAULT_MANJU_INSTRUCTION_TEMPLATES.items():
        item = deepcopy(default)
        custom = saved.get(key)
        if isinstance(custom, dict) and isinstance(custom.get("content"), str):
            item["content"] = custom["content"]
            item["customized"] = custom["content"] != default["content"]
        elif isinstance(custom, str):
            item["content"] = custom
            item["customized"] = custom != default["content"]
        else:
            item["customized"] = False
        item["key"] = key
        item["default_content"] = default["content"]
        templates[key] = item
    return templates


def get_manju_instruction_template(config: dict[str, Any], key: str) -> str:
    templates = list_manju_instruction_templates(config)
    if key not in templates:
        raise KeyError(key)
    return str(templates[key]["content"])


def save_manju_instruction_template(config: dict[str, Any], key: str, content: str) -> None:
    if key not in DEFAULT_MANJU_INSTRUCTION_TEMPLATES:
        raise KeyError(key)
    saved = _saved_templates(config)
    saved[key] = {"content": content}


def reset_manju_instruction_template(config: dict[str, Any], key: str) -> str:
    if key not in DEFAULT_MANJU_INSTRUCTION_TEMPLATES:
        raise KeyError(key)
    saved = _saved_templates(config)
    saved.pop(key, None)
    return str(DEFAULT_MANJU_INSTRUCTION_TEMPLATES[key]["content"])


def render_manju_instruction(config: dict[str, Any], key: str, values: dict[str, Any]) -> str:
    template = get_manju_instruction_template(config, key)

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in values:
            return match.group(0)
        value = values[name]
        if value is None:
            return ""
        return str(value)

    return re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", replace, template)
