# api/schemas.py
# -*- coding: utf-8 -*-
"""Pydantic 请求/响应模型"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel as PydanticBaseModel, field_validator

from api.security import normalize_project_path


class BaseModel(PydanticBaseModel):
    @field_validator("filepath", mode="before", check_fields=False)
    @classmethod
    def validate_project_filepath(cls, value):
        if value is None:
            return None
        return normalize_project_path(value)


# ── LLM / Embedding 配置 ──────────────────────────────────────────────────────

class LLMConfigCreate(BaseModel):
    config_name: str
    api_key: str = ""
    base_url: str = ""
    interface_format: str = "OpenAI"
    model_name: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 600
    enable_thinking: bool = False
    thinking_budget: int = 0
    enable_streaming: bool = True


class EmbeddingConfigCreate(BaseModel):
    config_name: str
    interface_format: str = "OpenAI"
    api_key: str = ""
    base_url: str = ""
    model_name: str = ""
    retrieval_k: int = 4


class ImageConfigCreate(BaseModel):
    config_name: str
    provider: str = "openai"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-image-1"
    size: str = "1024x1536"
    quality: str = "medium"
    output_format: str = "png"


class TestLLMConfigRequest(BaseModel):
    interface_format: str = "OpenAI"
    api_key: str = ""
    base_url: str = ""
    model_name: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 600
    enable_thinking: bool = False
    thinking_budget: int = 0


class TestEmbeddingConfigRequest(BaseModel):
    interface_format: str = "OpenAI"
    api_key: str = ""
    base_url: str = ""
    model_name: str = ""


class TestImageConfigRequest(BaseModel):
    provider: str = "openai"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-image-1"
    size: str = "1024x1024"
    quality: str = "low"
    output_format: str = "png"


class SetLLMDefaultRequest(BaseModel):
    slot: str
    config_name: str


class SetDefaultRequest(BaseModel):
    config_name: str


# ── 项目 ──────────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    filepath: str = ""


class ProjectUpdate(BaseModel):
    topic: str = ""
    genre: str = "玄幻"
    num_chapters: int = 10
    word_number: int = 3000
    filepath: Optional[str] = None
    user_guidance: str = ""
    xp_type: str = ""
    xp_selected_presets: Optional[List[str]] = None
    # 持久化到 project_config.json 的扩展字段
    llm_config_name: str = ""
    emb_config_name: str = ""
    arch_style: str = ""
    bp_style: str = ""
    ch_style: str = ""
    ch_narrative_style: str = ""
    expand_style: str = ""
    expand_narrative_style: str = ""
    cont_style: str = ""
    cont_xp_type: str = ""
    # 分步生成中间内容（断点续作）
    step_seed_text: str = ""
    step_char_text: str = ""
    step_char_state_text: str = ""
    step_world_text: str = ""
    step_plot_text: str = ""
    continue_guidance: str = ""
    cont_new_chapters: int = 5
    cont_step_seed_text: str = ""
    cont_step_world_text: str = ""
    cont_step_chars_text: str = ""
    cont_step_arcs_text: str = ""
    cont_step_char_state_text: str = ""


# ── 生成请求 ──────────────────────────────────────────────────────────────────

class GenerateArchRequest(BaseModel):
    llm_config_name: str
    topic: str
    genre: str = "玄幻"
    num_chapters: int = 10
    word_number: int = 3000
    filepath: str = "./output"
    user_guidance: str = ""
    arch_style_name: Optional[str] = None
    xp_type: str = ""
    num_characters: str = "3-6"


class GenerateArchStepRequest(BaseModel):
    llm_config_name: str
    topic: str = ""
    genre: str = "玄幻"
    num_chapters: int = 10
    word_number: int = 3000
    filepath: str = "./output"
    step_guidance: str = ""
    global_guidance: str = ""
    arch_style_name: Optional[str] = None
    xp_type: str = ""
    num_characters: str = "3-6"
    # for characters/world/plot steps
    seed_text: str = ""
    char_text: str = ""
    world_text: str = ""


class SupplementCharactersRequest(BaseModel):
    llm_config_name: str
    existing_characters: str
    supplement_guidance: str
    num_characters: str = "1-2"
    core_seed: str = ""
    world_building: str = ""
    filepath: str = ""


class GenerateCharStateRequest(BaseModel):
    llm_config_name: str
    char_dynamics_text: str


class AssembleArchRequest(BaseModel):
    filepath: str
    topic: str
    genre: str
    num_chapters: int
    word_number: int
    seed_text: str
    char_text: str
    char_state_text: str
    world_text: str
    plot_text: str


class ContinueArchRequest(BaseModel):
    llm_config_name: str
    filepath: str
    new_chapters: int = 5
    user_guidance: str = ""
    arch_style_name: Optional[str] = None
    xp_type: str = ""
    num_characters: str = "1-3"


class ContinueArchStepRequest(BaseModel):
    llm_config_name: str
    filepath: str
    new_chapters: int = 5
    user_guidance: str = ""
    step_guidance: str = ""
    new_characters_text: str = ""
    arch_style_name: Optional[str] = None
    xp_type: str = ""
    num_characters: str = "1-3"
    continuation_seed: str = ""
    world_expansion: str = ""


class AssembleContinuationRequest(BaseModel):
    filepath: str
    new_chapters: int = 5
    new_characters_text: str
    new_arcs_text: str
    new_char_state_text: str
    continuation_seed: str = ""
    world_expansion: str = ""


class CompressContextRequest(BaseModel):
    llm_config_name: str
    filepath: str
    include_world_building: bool = True


class GenerateBlueprintRequest(BaseModel):
    llm_config_name: str
    filepath: str
    num_chapters: int = 10
    user_guidance: str = ""
    bp_style_name: Optional[str] = None
    xp_type: str = ""


class GenerateChapterRequest(BaseModel):
    llm_config_name: str
    emb_config_name: str
    filepath: str
    chapter_num: int
    word_number: int = 3000
    user_guidance: str = ""
    characters_involved: str = ""
    key_items: str = ""
    scene_location: str = ""
    time_constraint: str = ""
    style_name: Optional[str] = None
    narrative_style_name: Optional[str] = None
    xp_type: str = ""
    inject_world_building: bool = False
    scene_by_scene: bool = False  # 按场景分段生成（需有细纲）


class FinalizeChapterRequest(BaseModel):
    llm_config_name: str
    emb_config_name: str
    filepath: str
    chapter_num: int
    word_number: int = 3000


class ExpandScenesRequest(BaseModel):
    llm_config_name: str
    filepath: str
    chapter_num: int
    style_name: Optional[str] = None
    narrative_style_name: Optional[str] = None
    xp_type: str = ""
    polish_guidance: str = ""
    polish_mode: str = "enhance"  # enhance / sensual / modify / add
    include_outline: bool = False
    include_character_state: bool = False
    include_summary: bool = False
    include_world_building: bool = False


class BatchGenerateRequest(BaseModel):
    llm_config_name: str
    emb_config_name: str
    filepath: str
    word_number: int = 3000
    user_guidance: str = ""
    style_name: Optional[str] = None
    narrative_style_name: Optional[str] = None
    xp_type: str = ""
    inject_world_building: bool = False


class SaveChapterRequest(BaseModel):
    content: str


class SaveContentRequest(BaseModel):
    content: str
    filepath: str = "./output"


# ── 文风 ──────────────────────────────────────────────────────────────────────

class StyleAnalyzeRequest(BaseModel):
    llm_config_name: str
    sample_text: str
    style_name: str
    unlock: bool = False


class StyleAnalyzeDNARequest(BaseModel):
    llm_config_name: str
    sample_text: str
    style_name: str
    unlock: bool = False


class StyleMergeRequest(BaseModel):
    llm_config_name: str
    selected_styles: List[str]
    merge_name: str
    user_preference: str = ""
    unlock: bool = False


class StyleSaveRequest(BaseModel):
    analysis_result: str
    style_instruction: str
    source_sample: Optional[str] = None
    calibration_reference: Optional[str] = None
    narrative_for_architecture: Optional[str] = None
    narrative_for_blueprint: Optional[str] = None
    narrative_for_chapter: Optional[str] = None


class StyleCalibrateRequest(BaseModel):
    llm_config_name: str
    style_name: str
    max_iterations: int = 5
    unlock: bool = False


# ── 预设 ──────────────────────────────────────────────────────────────────────

class PresetCreate(BaseModel):
    name: str
    description: str = ""


class PromptUpdate(BaseModel):
    content: str


class InstructionTemplateUpdate(BaseModel):
    content: str


# ── 一致性检查 ────────────────────────────────────────────────────────────────

class ConsistencyCheckRequest(BaseModel):
    llm_config_name: str
    filepath: str
    chapter_num: int


# ── SSE 事件 ──────────────────────────────────────────────────────────────────

class HumanizerRequest(BaseModel):
    llm_config_name: str
    filepath: str
    chapter_num: int
    enable_r8: bool = False
    user_focus: str = ""
    depth: str = "standard"  # quick / standard / deep


class BatchHumanizerRequest(BaseModel):
    llm_config_name: str
    filepath: str
    start_chapter: int
    end_chapter: int
    enable_r8: bool = False
    user_focus: str = ""
    depth: str = "standard"


class GenerateDetailedOutlineRequest(BaseModel):
    llm_config_name: str
    filepath: str
    start_chapter: int
    end_chapter: int
    num_chapters: int = 10
    user_guidance: str = ""
    xp_type: str = ""
    outline_mode: str = "concise"  # concise / detailed


class ReviseStepRequest(BaseModel):
    llm_config_name: str
    original_content: str
    revision_guidance: str
    step_type: str = ""  # core_seed / characters / char_state / world / plot
    filepath: str = ""
    include_core_seed: bool = False
    include_characters: bool = False
    include_world_building: bool = False
    include_plot: bool = False


class BrainstormMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class BrainstormChatRequest(BaseModel):
    llm_config_name: str
    filepath: str
    messages: List[BrainstormMessage]
    include_core_seed: bool = True
    include_characters: bool = True
    include_world_building: bool = True
    include_plot: bool = True
    include_blueprint: bool = False
    include_character_state: bool = False
    extra_context: str = ""
    discussion_mode: str = "advisor"  # advisor / casual / brainstorm / devil / roleplay


class SSEEvent(BaseModel):
    type: str  # progress | result | error | done
    message: str = ""
    content: str = ""


# ── 漫剧制作 ──────────────────────────────────────────────────────────────────

class ManjuGenerateRequest(BaseModel):
    llm_config_name: str
    filepath: str = "./output"
    start_chapter: int = 1
    end_chapter: Optional[int] = None
    shots_per_chapter: int = 12
    visual_style: str = "国漫竖屏短剧，电影级构图，统一角色设定，高细节，适合文生图"
    extra_guidance: str = ""


class ManjuScriptAdaptRequest(BaseModel):
    llm_config_name: str
    filepath: str = "./output"
    start_chapter: int = 1
    end_chapter: Optional[int] = None
    target_chapters: int = 12
    rename_characters: bool = False
    adaptation_level: str = "中度改编"
    episode_duration: str = "3-5分钟"
    script_style: str = "竖屏漫剧，强钩子，快节奏，适合后续分镜和AI绘图"
    extra_guidance: str = ""


class ManjuSettingsRequest(BaseModel):
    filepath: str = "./output"
    llm_config_name: str = ""
    start_chapter: int = 1
    end_chapter: Optional[int] = None
    shots_per_chapter: int = 12
    visual_style: str = "国漫竖屏短剧，电影级构图，统一角色设定，高细节，适合文生图"
    extra_guidance: str = ""


class ManjuCharactersUpdateRequest(BaseModel):
    filepath: str = "./output"
    characters: List[Dict[str, Any]] = []


class ManjuStoryboardUpdateRequest(BaseModel):
    filepath: str = "./output"
    shots: List[Dict[str, Any]] = []


class ManjuShotRegenerateRequest(BaseModel):
    filepath: str = "./output"
    llm_config_name: str
    shot_id: str
    visual_style: str = ""
    extra_guidance: str = ""


class ManjuImageConfigRequest(BaseModel):
    filepath: str = "./output"
    provider: str = "openai"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-image-1"
    size: str = "1024x1536"
    quality: str = "medium"
    output_format: str = "png"


class ManjuImageGenerateRequest(BaseModel):
    filepath: str = "./output"
    source_type: str = "shot"  # shot / character / scene / custom
    source_id: str = ""
    prompt: str = ""
    image_config_name: str = ""
    provider: Optional[str] = None


class ImageGenerateRequest(BaseModel):
    config_name: str
    prompt: str
    filepath: str = "./output"
    source_type: str = "custom"
    source_id: str = ""


class ImagePromptImportRequest(BaseModel):
    filepath: str = "./output"
    items: List[Dict[str, Any]] = []
    replace: bool = False


class ManjuImagePromptImportRequest(BaseModel):
    filepath: str = "./output"
    kind: str = "all"
    replace: bool = False


class ManjuPromptEnhanceRequest(BaseModel):
    filepath: str = "./output"
    kind: str = "all"  # characters / storyboards / all
    llm_config_name: str = ""
    use_llm: bool = False
    overwrite_locked: bool = False


class ManjuStyleTemplateRequest(BaseModel):
    filepath: str = "./output"
    name: str
    visual_style: str
    extra_guidance: str = ""


class ManjuQueueCreateRequest(BaseModel):
    filepath: str = "./output"
    start_chapter: int = 1
    end_chapter: Optional[int] = None
    chunk_size: int = 5
