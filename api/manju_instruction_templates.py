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
        "description": "用于把原小说摘录规划为可再次导入系统的漫剧正文目录，并控制全剧场景/主角/配角总数。",
        "variables": [
            "target_chapters",
            "target_scenes",
            "target_leads",
            "target_supporting_cast",
            "rename_rule",
            "adaptation_level",
            "episode_duration",
            "script_style",
            "extra_guidance",
            "source_digest",
        ],
        "content": """你是小说改编策划。请把小说内容规划为可再次导入系统的漫剧小说正文目录，**并按下方"产能预算"控制全剧资产数量**。

改编参数：
- 目标剧本章节数：{target_chapters} 章
- 人物名称规则：{rename_rule}
- 剧情改编幅度：{adaptation_level}
- 单章篇幅/节奏参考：{episode_duration}
- 改编风格：{script_style}
- 补充要求：{extra_guidance}

# 产能预算（用于控制后续出图总数，必须严格遵守）

为了让后续"角色卡 / 场景图 / 分镜"模块出图数量可控，请**主动收敛**改编范围，使整本剧本的资产总量满足：
- 全剧总场景数 ≤ {target_scenes} 个（场景=明确地点+特定时间/光线状态）
- 全剧主角数 ≤ {target_leads} 名
- 全剧重要配角数 ≤ {target_supporting_cast} 名（功能性路人不计入）

如果原著的场景或角色明显多于以上预算，请通过：
- 合并相似空间（如多个"客栈房间"合成同一个"客栈"场景）
- 合并戏份不足的次要角色（如多个龙套合成同一个"管家"）
- 砍掉对主线推进作用弱的支线
来主动压缩到预算内。砍掉的支线要在改编里有合理过渡，不要露出剪辑痕迹。

# 硬性要求

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
        "description": "根据目录和原文摘录生成每一章漫剧改编正文，受全剧场景/主角/配角预算约束。",
        "variables": [
            "episode",
            "target_chapters",
            "target_scenes",
            "target_leads",
            "target_supporting_cast",
            "rename_rule",
            "adaptation_level",
            "script_style",
            "extra_guidance",
            "outline",
            "previous_script",
            "source_digest",
        ],
        "content": """你是小说改编作者。请根据目录和原文摘录，只创作第 {episode} 章的漫剧改编正文。

# 产能预算（全剧累计上限，本章必须遵守）

- 全剧总场景数 ≤ {target_scenes} 个：本章新引入场景必须节制；优先复用前几章已经出现过的地点。
- 全剧主角数 ≤ {target_leads}、重要配角数 ≤ {target_supporting_cast}：本章如必须引入新角色，要么是预算内的预定主配角，要么是一次性功能性路人（不会再出现）。
- 不要为了戏剧性临时引入新地点/新角色而超出全剧总预算。

# 硬性要求

1. 输出必须是可再次导入的 TXT 小说正文格式。
2. 第一行必须且只能是章节标题，格式严格为：第{episode}章 标题。
3. 标题下一行开始直接写剧情正文，可以包含自然对白，但不要写"场次、画面说明、分镜提示、角色表、剧情节拍、旁白/字幕、情绪点、改编说明"等制作信息。
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
        "description": "从小说摘录识别影响画面连续性的角色名清单，仅用于后续分批生成角色卡。",
        "variables": ["scope", "extra_guidance", "chapter_source"],
        "content": """你是漫剧改编导演。请根据小说摘录建立"角色索引"，仅作为后续生成角色卡时的角色名清单。

硬性要求：
1. 识别{scope}内所有会出现在画面里的角色（主角、核心配角、反派、功能性角色）。
2. 不要把地点、势力、物品、章节名当成角色。
3. 输出格式（每行一个角色，严格按此格式）：
- 角色名｜重要度：主角/核心配角/反派/功能性角色

补充要求：
{extra_guidance}

小说章节摘录：
{chapter_source}
""",
    },
    "character_fallback": {
        "title": "角色信息与角色卡：完整角色库",
        "description": "兜底一次性生成完整角色库。纯角色立绘（白底中性站姿，不含任何场景/剧情/其他角色）。",
        "variables": ["visual_style", "extra_guidance", "source"],
        "content": """你是漫剧角色设定师与 AI 生图提示词工程师。请生成**纯角色立绘**——单角色站在白底前的全身像，用同一段提示词多次生成时主体外观差异 ≤ 5%。

本模块的产物会作为"角色锚点"在分镜阶段和场景图组合，因此：

- 角色卡 **只画一个角色 + 中性站姿 + 干净白色背景**
- 角色卡 **不包含任何场景元素、剧情动作、情绪事件、其他角色**
- 角色卡 **不包含戏剧光照**（如月光、烛火、霓虹），只用标准产品级布光

剧情、心理、关系、弧光、章节号等**与画面无关的信息一律不要输出**。

# 工作约束

1. 识别所有重要角色（主角、核心配角、反派、功能性角色），每个角色独立一段。
2. 字段必须是**画面可视化的具体描述**——禁止性格、剧情作用、弧光、关系、章节号、心理活动、抽象气质词，除非翻译成可见外观。
3. 原文未明确的细节可以合理改编补全，必须在该字段尾部标注"（改编补全）"。
4. 严禁"同上""略""后续继续"等省略表达。

# 画面描述写作铁律（必须全部满足）

每条"画面描述"强制覆盖 11 个维度，每个维度都给具体可视化词，不得空缺：

(1) 年龄范围：精确到 2-3 岁区间。
(2) 性别 + 体型：身高 cm 区间 + 偏瘦/中等/魁梧 + 肩宽。
(3) 脸型：瓜子脸/鹅蛋脸/方下颌/圆脸 + 颧骨高低 + 下巴形状。
(4) 发色 + 发型 + 长度 + 分缝。
(5) 瞳色 + 眼形 + 内/外双 + 眼尾走向。
(6) 肤色：白皙带冷调/白皙偏暖/小麦色/古铜健康。
(7) 服装：颜色（具体颜色名/hex/冷暖调）+ 材质 + 廓形 + 状态（整洁，**不要破损/沾血/凌乱**——剧情状态留给分镜阶段）。
(8) 配饰：位置 + 材质 + 颜色。
(9) **中性表情** + 视线方向（"中性平静的表情，视线直视镜头"）。**不要写戏剧化情绪**。
(10) **中性站姿** + 重心（"双脚与肩同宽自然站立，双手自然垂于体侧"）。**不要写动作**。
(11) **强制固定**画质标签："pure white background, plain solid white #ffffff, no scene, no environment, no objects, soft even studio lighting, neutral product-style photography, manhua concept art reference sheet, ultra detailed, sharp focus, 8k"。

末尾用"—"破折号引出"避免事项"自然句，**且必须显式禁止场景与他人**：
"— single character only, full body in frame, plain white solid background, no scene, no environment, no props except listed accessories, no other characters, no narrative action, no dramatic lighting, no character sheet layout, no multiple poses or split view, no text, no watermark, no extra hands or fingers"。

# 输出格式（每个角色严格按此格式）

## 角色名
- 剧情身份：一句话身份标签（≤20 字）
- 外貌固定设定：覆盖维度 (1)-(6)
- 服装固定设定：覆盖维度 (7)-(8)
- 画面描述：单段英文/中英混合自然语言，覆盖全部 11 个维度，末尾以"—"引出避免事项

# 上下文

全局视觉风格（仅用于辅助理解美术方向，不要把场景描写塞进角色卡）：
{visual_style}

补充要求：
{extra_guidance}

小说章节摘录：
{source}
""",
    },
    "character_cards": {
        "title": "角色信息与角色卡：分批角色卡",
        "description": "为已识别角色分批生成纯角色立绘画面描述（白底中性站姿，不含任何场景/剧情/其他角色），用于在分镜阶段与场景图组合。",
        "variables": [
            "batch_names",
            "batch_list",
            "visual_style",
            "extra_guidance",
            "index_result",
            "source",
            "character_evidence",
        ],
        "content": """你是漫剧角色设定师与 AI 生图提示词工程师。你的目标：产出**纯角色立绘**——单角色站在白底前的全身像，用同一段提示词多次生成时主体外观差异 ≤ 5%。

本模块的产物会作为"角色锚点"在分镜阶段和场景图组合，因此：

- 角色卡 **只画一个角色 + 中性站姿 + 干净白色背景**
- 角色卡 **不包含任何场景元素、剧情动作、情绪事件、其他角色**
- 角色卡 **不包含戏剧光照**（如月光、烛火、霓虹），只用标准产品级布光

剧情、心理、关系、弧光、章节号等**与画面无关的信息一律不要输出**。

本批角色：
{batch_list}

# 工作约束

1. 严格按下方"输出格式"逐个输出本批全部角色，顺序一致，不得合并、不得省略。
2. 每个字段必须是**画面可视化的具体描述**——禁止性格、剧情作用、人物弧光、与谁的关系、出场章节、心理活动、抽象气质词（如"神秘""高冷""沧桑"）。如果原文里只有抽象词，必须翻译成可见外观（"嘴角下垂、眉间常皱、穿暗色高领"）。
3. **以"角色全文证据片段"为第一来源**重建外观；只有证据缺失时才用"章节摘录"补充，再缺再做"改编补全"，必须在该字段尾部加"（改编补全）"。
4. 严禁"同上""略""后续继续"等省略表达。

# 画面描述写作铁律（这是稳定复现的关键，必须全部满足）

为了让文生图模型每次画出相同的人，**画面描述里必须把所有自由度钉死**。每次写"画面描述"时强制覆盖以下 11 个维度，每个维度都给具体可视化词，不得空缺：

(1) 年龄范围：精确到 2-3 岁区间（如"20-22 岁"），不要写"年轻""青年"。
(2) 性别 + 体型：身高 cm 区间 + 偏瘦/中等/魁梧 + 肩宽（如"男性，178-182cm，偏瘦，肩宽中等"）。
(3) 脸型：瓜子脸/鹅蛋脸/方下颌/圆脸 + 颧骨高低 + 下巴形状。
(4) 发色 + 发型 + 长度 + 分缝：例如"亚麻棕色，及腰直发，中分，左侧发丝挽至耳后"。
(5) 瞳色 + 眼形：例如"琥珀色，杏仁眼，内双，眼尾微微上挑"。
(6) 肤色：白皙带冷调 / 白皙偏暖 / 小麦色 / 古铜健康。
(7) 服装：颜色（必须给具体颜色名，最好附 hex 或冷暖调）+ 材质（棉/丝/皮革/重锦缎）+ 廓形（修身/宽松/A 字）+ 状态（整洁，**不要破损/沾血/凌乱**——这些属于剧情状态，留给分镜阶段处理）。
(8) 配饰：位置 + 材质 + 颜色（"左耳银色月牙耳钉""右手腕黑色磨砂皮护腕""腰间挂青铜虎符吊坠"）。
(9) 中性表情 + 视线方向：必须写"中性平静的表情，视线直视镜头"或类似的标准化表情。**不要写戏剧化情绪**（愤怒、悲伤、决绝），那些留给分镜阶段。
(10) 中性站姿 + 重心：必须写"双脚与肩同宽自然站立，双手自然垂于体侧"或类似的标准化站姿。**不要写战斗、奔跑、抚琴等动作**，那些留给分镜阶段。
(11) **强制固定**的背景与画质标签：必须**原样**写入"pure white background, plain solid white #ffffff, no scene, no environment, no objects, soft even studio lighting, neutral product-style photography, manhua concept art reference sheet, ultra detailed, sharp focus, 8k"。

末尾必须用"—"破折号引出"避免事项"自然句，**且必须显式禁止场景与他人**：
"— single character only, full body in frame, plain white solid background, no scene, no environment, no props except listed accessories, no other characters, no narrative action, no dramatic lighting, no character sheet layout, no multiple poses or split view, no text, no watermark, no extra hands or fingers"。

# 输出格式（每个角色严格按此格式，不要增加或重命名字段）

## 角色名
- 剧情身份：一句话身份标签（≤20 字，仅用于辨识，不要展开剧情）
- 外貌固定设定：覆盖维度 (1)-(6)，写成完整一句话或分项
- 服装固定设定：覆盖维度 (7)-(8)
- 画面描述：单段英文/中英混合自然语言，覆盖全部 11 个维度，末尾以"—"引出避免事项

# 上下文

全局视觉风格（仅用于辅助理解美术方向，不要把场景描写塞进角色卡）：
{visual_style}

补充要求：
{extra_guidance}

角色索引（仅用于对齐角色名，不要复述）：
{index_result}

角色全文证据片段（按角色分组，可能为空）：
{character_evidence}

小说章节摘录（仅用于补足证据缺失，不要复述剧情）：
{source}
""",
    },
    "scenes": {
        "title": "章节场景图提示词",
        "description": "把章节拆成纯环境场景库（不含人物）。画面描述只描写空场环境；'出现角色'仅作元数据用于分镜阶段引用。",
        "variables": [
            "chapter_num",
            "chapter_title",
            "chapter_content",
            "visual_style",
            "characters",
            "extra_guidance",
        ],
        "content": """你是漫剧美术导演与 AI 生图提示词工程师。请把下面章节拆成**纯环境场景库**——空场环境，**画面描述里不能出现任何人物**。目标是"用同一段提示词多次生成同一场景，环境差异 ≤ 5%"。

本模块的产物会作为"场景锚点"在分镜阶段与角色卡组合，因此：

- 场景图 **只画空场环境**：建筑、家具、地形、天气、光线
- 场景图 **不画任何人物**（无主角、无配角、无路人、无人影、无人形剪影）
- "出现角色"字段是**元数据**——记录"哪些角色将来会在这个场景里出现"，给分镜阶段引用用，**画面描述里不要写任何人**

剧情、心理、剧情作用、转场说明等**与画面无关的信息一律不要输出**。

# 工作约束

1. 每章 6-12 个关键场景，覆盖主要转场即可。
2. 字段必须是**画面可视化的具体描述**——禁止抽象词（"紧张氛围""很震撼"），必须翻译成可见画面元素（"低角度仰拍 + 顶光投影"）。
3. **禁止在画面描述里出现"主角""人物""一个男人/女人""人影""一群人""背影"等任何指代人物的词**。如果原文里这个空间总是有人活动，也要剥离人物只画空场。
4. 严禁"略""后续同上"等省略表达。

# 画面描述写作铁律（必须全部满足）

每个场景的"画面描述"强制覆盖 10 个维度：

(1) 地点全名 + 室内/室外 + 时段（清晨/正午/黄昏/深夜）。
(2) 主光源方向 + 色温（侧逆光 / 顶光 / 暖橙 3000K / 冷蓝 5500K）。
(3) 辅光与阴影（柔光填充 / 硬阴影 / 体积光）。
(4) 环境物件 ≥5 个，含位置（左前景 / 中景中央 / 远处天际线）。
(5) 透视与镜头焦段（35mm 标准 / 24mm 广角 / 85mm 长焦）。
(6) 色彩主调 + 对比度（暖橙金主调，高对比 / 青灰主调，低对比）。
(7) 天气/粒子（雾气、雨丝、飘雪、飞絮、火星、灰尘）。
(8) 材质质感（粗木纹、湿润青石、锈铁、细腻丝绸）。
(9) 构图（三分法 / 对称 / 引导线 / 框中框）。
(10) **强制固定**画风与画质："empty environment, no people, no characters, no human figures, manhua concept art, cinematic composition, ultra detailed, sharp focus, 8k"。

末尾用"—"破折号引出"避免事项"自然句，**且必须显式禁止人物**：
"— no people, no characters, no human figures, no silhouettes, no shadows of people, no text, no watermark, no logo, clean focal subject"。

# 输出格式（每个场景严格按此格式）

## 场景名（地点+时间，例如"古宅书房·夜"）
- 地点类型：室内 / 室外 / 混合
- 时间/光线：例如"夜晚，暖黄烛光 + 月光从窗外侧射"
- 环境元素：≥5 个关键物件 + 位置
- 出现角色（**仅元数据，不进入画面描述**）：本场会有哪些角色出现（用、分隔，可空，画面描述里不写他们）
- 镜头景别建议：远景 / 全景 / 中景 / 近景 / 特写
- 画面描述：单段英文/中英混合自然语言，**只描写空场环境**，覆盖全部 10 个维度，末尾以"—"引出避免事项

# 上下文

全局视觉风格：
{visual_style}

角色一致性锁定表（仅供"出现角色"字段对齐角色名，画面描述里不要引用）：
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
        "description": "把'纯角色立绘（角色卡）'与'纯环境场景（场景库 SC-XXX）'组合成连续分镜。强制引用 SC-XXX 和角色卡，确保跨镜一致。",
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
        "content": """你是漫剧分镜导演、摄影指导与 AI 生图提示词工程师。本模块的本质是**把已经准备好的两类"乐高积木"组合成连续画面**：

- **角色卡（来自下方"角色一致性锁定表"）**：每个角色都有锁定的外貌/服装/配饰描述。
- **场景库（来自下方"本章已有场景提示词"，编号 SC-XXX）**：每个场景都有锁定的环境描述。

你的工作：根据剧情把"角色卡 + 场景图 + 该镜动作/构图"组合成分镜画面描述。目标是"用同一段提示词多次生成同一分镜，主体差异 ≤ 5%"。剧情解释、心理活动、转场说明、字幕台词等**非画面信息一律不要输出**。

# 工作约束

1. 本章总分镜数为 {shots_per_chapter}。本批只输出全局编号 {shot_start}-{shot_end}，共 {batch_count} 个分镜，不得多也不得少。
2. 镜号使用全局编号，不要从 1 重新计数（除非本批从 1 开始）。
3. **场景必须强制引用 SC-XXX**——在"画面描述"开头明确写 "Scene reference: SC-007 〈场景名〉" 并完整复述该场景的环境描述（光线、物件、色彩、材质）。如果剧情发生地点在场景库里没有，自己写一个临时场景描述但要标注"（临时场景，未入库）"。
4. **角色必须强制引用角色卡**——在"画面描述"里每个角色都用"角色名 + 角色卡里的关键 4-6 个视觉锚点"完整指代，禁止只写"主角"或"他"。
5. 严禁"略""同上""后续继续""省略若干镜头"等省略表达。
6. 如本批包含最后一镜（编号 {shots_per_chapter}），最后一镜必须形成本章画面落点。

# 画面描述写作铁律（必须全部满足）

每个分镜的"画面描述"必须由 3 部分拼接而成（顺序固定，便于模型识别）：

**A 段：场景锚定**——"Scene reference: SC-XXX 〈场景名〉, " + 完整复述场景的：地点 + 时段 + 主光方向色温 + 辅光阴影 + 关键环境物件 + 色彩主调 + 天气粒子 + 材质质感 + 构图。

**B 段：角色锚定 + 该镜动作**——每个出场角色（≤2 名）按以下格式写：
"〈角色名〉(角色卡复述：年龄区间, 性别身高体型, 脸型, 发色发型长度, 瞳色眼形, 肤色, 服装颜色材质廓形, 配饰位置), 该镜动作: 站位（前景左/中景中/背景右）+ 距离 + 手部姿态 + 重心脚 + 头部朝向 + 视线方向, 该镜表情: 眉/眼/嘴具体形态。"

**C 段：镜头与画质**——镜头景别 + 焦段（如 35mm 中景）+ 机位（如 低角度仰拍 30°，距离主体 1.5m）+ 构图（三分法/对称/引导线 + 主体位置 + 画面焦点）+ "vertical manhua storyboard frame, 9:16, manhua concept art, cinematic lighting, ultra detailed, sharp focus, 8k"。

末尾用"—"破折号引出"避免事项"自然句：
"— no text, no speech bubbles unless requested, no watermark, no extra hands or fingers, no inconsistent outfit, no multiple identical characters, no scene mismatch"。

# 输出格式（每个分镜严格按此格式，不要增加或重命名字段）

## 镜号 {shot_start} （示例：## 镜号 12）
- 主体：画面正中的人或物（一句话）
- 引用场景：SC-XXX（若无可用则写"临时场景"并简述地点+时段）
- 引用角色：角色名 1、角色名 2（≤2 名，按出现顺序）
- 角色动作：用"角色名 + 动作 + 表情 + 视线方向"组织（多角色用、分隔）
- 镜头景别：远景 / 全景 / 中景 / 近景 / 特写
- 机位/构图：例如"低角度仰拍 30°，三分法构图，主体偏右 1/3"
- 画面描述：单段英文/中英混合自然语言，**严格按 A→B→C 三段拼接**，末尾以"—"引出避免事项

# 上下文

已完成的本章前序分镜（仅作连续性参考，不要复述）：
{previous_context}

全局视觉风格：
{visual_style}

角色一致性锁定表（B 段必须复述其中关键锚点）：
{characters}

本章已有场景提示词（A 段必须引用其中 SC-XXX 编号并复述环境）：
{chapter_scenes}

补充要求：
{extra_guidance}

章节：
第{chapter_num}章 {chapter_title}
{chapter_content}
""",
    },
    "character_index_local": {
        "title": "全文模式：单章角色识别（Map）",
        "description": "对单一章节识别本章出场角色，仅给名字+别名，由 character_index_reduce 跨章合并。",
        "variables": ["chapter_num", "chapter_title", "chapter_content", "extra_guidance"],
        "content": """你是漫剧改编导演。请只对【第{chapter_num}章 {chapter_title}】识别本章出场角色，作为后续全文合并素材。

硬性要求：
1. 只识别本章出场的角色；本章未出场的不要写。
2. 不要把地点、势力、物品、章节名当成角色。
3. 同一个人在本章有多种称呼时，主名取最显著的那一个，其它写在"别名"里。
4. 输出格式（每行一个角色，严格按此格式）：
- 角色名｜重要度：主角/核心配角/反派/功能性角色｜别名：逗号分隔，可空

补充要求：
{extra_guidance}

本章正文：
{chapter_content}
""",
    },
    "character_index_reduce": {
        "title": "全文模式：跨章角色合并（Reduce）",
        "description": "合并各章本地角色清单为统一索引，仅保留名字与别名。",
        "variables": ["extra_guidance", "per_chapter_indexes"],
        "content": """你是漫剧改编导演。下面是各章节"本章出场角色清单"，请合并去重为统一角色索引。

硬性要求：
1. 同一个人在不同章节的不同称呼合并为同一个角色（基于上下文判断），主名取最常见或最正式的称呼，其余写入"别名"。
2. 不要遗漏只在某一章出现的重要角色。
3. 输出格式（每行一个角色，严格按此格式）：
- 角色名｜重要度：主角/核心配角/反派/功能性角色｜别名：逗号分隔，可空

补充要求：
{extra_guidance}

各章节出场角色清单（按章节顺序）：
{per_chapter_indexes}
""",
    },
    "scenes_local": {
        "title": "全文模式：单章场景识别（Map）",
        "description": "全文扫描下识别本段候选场景，仅输出画面相关字段，由 scenes_reduce 跨章合并。",
        "variables": [
            "chapter_num",
            "chapter_title",
            "segment_index",
            "segment_count",
            "chapter_segment",
            "visual_style",
            "characters",
            "extra_guidance",
        ],
        "content": """你是漫剧美术导演。请只对【第{chapter_num}章 {chapter_title}】第 {segment_index}/{segment_count} 段识别本段出现的所有候选场景，作为后续跨章合并素材。剧情作用、心理、转场说明等**非画面信息一律不要输出**。

硬性要求：
1. 只识别本段出现的场景；本段没出现的不要补。
2. 场景定义=明确地点 + 特定时间/光线状态。同地不同时（白天/夜晚/雨/雪）算不同场景。
3. 不要把人物、动作、情节、心理活动当成场景。
4. 输出 Markdown 列表，每行严格按以下字段，字段间用「｜」分隔：

- 场景名（地点+时间）｜地点类型：室内/室外/混合｜时间/光线：一句话｜环境元素：3-5 个关键物件｜出现角色：本段在此场景出现的角色名（用、分隔，可空）

全局视觉风格：
{visual_style}

角色一致性锁定表（按需引用，可空）：
{characters}

补充要求：
{extra_guidance}

本段正文：
{chapter_segment}
""",
    },
    "scenes_reduce": {
        "title": "全文模式：跨章场景去重 + 完整场景库（Reduce）",
        "description": "合并各段 scenes_local 为整本纯环境场景库（不含人物）。画面描述只描写空场环境；'出现角色'仅作元数据用于分镜阶段引用。",
        "variables": ["visual_style", "characters", "extra_guidance", "per_segment_scenes"],
        "content": """你是漫剧美术导演与 AI 生图提示词工程师。下面是各章节各段的"候选场景清单"。请合并去重为整本统一的**纯环境场景资产库**——空场环境，**画面描述里不能出现任何人物**。目标是"用同一段提示词多次生成同一场景，环境差异 ≤ 5%"。

本模块的产物会作为"场景锚点"在分镜阶段与角色卡组合，因此：

- 场景图 **只画空场环境**：建筑、家具、地形、天气、光线
- 场景图 **不画任何人物**（无主角、无配角、无路人、无人影、无人形剪影）
- "出现角色"字段是**元数据**——记录"哪些角色将来会在这个场景里出现"，给分镜阶段引用用，**画面描述里不要写任何人**

剧情作用、心理、抽象气质等**非画面字段一律不要输出**。

# 工作约束

1. 同一地点+同一时间/光线合并为同一场景；同地不同时（白天/夜晚/雨/雪）保留为不同场景。
2. 严格按下方"输出格式"逐个场景输出，使用 SC-001、SC-002 形式连续编号。
3. 字段必须是**画面可视化的具体描述**，禁止抽象词。
4. **禁止在画面描述里出现"主角""人物""一个男人/女人""人影""一群人""背影"等任何指代人物的词。**
5. 严禁"略""后续同上"。

# 画面描述写作铁律（必须全部满足）

每个场景的"画面描述"强制覆盖 10 个维度：

(1) 地点全名 + 室内/室外 + 时段。
(2) 主光源方向 + 色温（侧逆光 / 顶光 / 暖橙 3000K / 冷蓝 5500K）。
(3) 辅光与阴影。
(4) 环境物件 ≥5 个，含位置（左前景 / 中景中央 / 远处天际线）。
(5) 透视与镜头焦段（35mm 标准 / 24mm 广角 / 85mm 长焦）。
(6) 色彩主调 + 对比度。
(7) 天气/粒子。
(8) 材质质感。
(9) 构图（三分法 / 对称 / 引导线 / 框中框）。
(10) **强制固定**画风与画质："empty environment, no people, no characters, no human figures, manhua concept art, cinematic composition, ultra detailed, sharp focus, 8k"。

末尾用"—"破折号引出"避免事项"自然句，**且必须显式禁止人物**：
"— no people, no characters, no human figures, no silhouettes, no shadows of people, no text, no watermark, no logo, clean focal subject"。

# 输出格式（每个场景严格按此格式）

## SC-001 场景名（地点+时间）
- 地点类型：室内 / 室外 / 混合
- 时间/光线：一句话
- 环境元素：≥5 个关键物件 + 位置
- 出现章节：合并后的章节号列表（例如"3, 7, 12"）
- 出现角色（**仅元数据，不进入画面描述**）：用、分隔，可空
- 镜头景别建议：远景 / 全景 / 中景 / 近景 / 特写
- 画面描述：单段英文/中英混合自然语言，**只描写空场环境**，覆盖全部 10 个维度，末尾以"—"引出避免事项

# 上下文

全局视觉风格：
{visual_style}

角色一致性锁定表（仅供"出现角色"字段对齐角色名，画面描述里不要引用）：
{characters}

补充要求：
{extra_guidance}

各章节各段候选场景清单（按章节顺序）：
{per_segment_scenes}
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
