# api/image_params.py
# -*- coding: utf-8 -*-
"""F1: 把用户选择的「比例 + 分辨率档位」派生为 provider/model 实际接受的 size + quality。

设计要点：
- OpenAI 与 Mirrorstages 的 `/images/generations` 均只接受离散 size：
  1024x1024 / 1024x1536 / 1536x1024（Mirrorstages 完全兼容 OpenAI Images Generations API）。
  分辨率档位映射到 quality，size 由比例决定（向最接近的允许档对齐）。
- 其它自托管 provider 若未来接入，可按比例和档位的「最长边」算出 width×height。
- 配置仍持久化 size / quality 字段以兼容旧调用方与日志。
"""

from typing import Any

ASPECT_RATIOS: tuple[str, ...] = ("1:1", "9:16", "16:9", "4:3", "3:4", "3:2", "2:3")
RESOLUTIONS: tuple[str, ...] = ("480p", "720p", "1080p", "2k", "4k")

# 最长边像素数
_RESOLUTION_LONG_EDGE = {
    "480p": 480,
    "720p": 720,
    "1080p": 1080,
    "2k": 2048,
    "4k": 4096,
}

# 档位 → OpenAI quality
_RESOLUTION_QUALITY_OPENAI = {
    "480p": "low",
    "720p": "low",
    "1080p": "medium",
    "2k": "high",
    "4k": "high",
}

# OpenAI 允许的 size 集合（gpt-image-1 / dall-e-3 通用，向最近匹配回落）
_OPENAI_SIZES: tuple[tuple[int, int], ...] = (
    (1024, 1024),
    (1024, 1536),
    (1536, 1024),
)


def _parse_aspect(aspect: str) -> tuple[int, int]:
    parts = (aspect or "1:1").split(":")
    if len(parts) != 2:
        return 1, 1
    try:
        w = int(parts[0])
        h = int(parts[1])
        return (w, h) if w > 0 and h > 0 else (1, 1)
    except ValueError:
        return 1, 1


def _round_to_multiple(n: int, base: int = 64) -> int:
    return max(base, int(round(n / base)) * base)


def _nearest_openai_size(aspect_w: int, aspect_h: int) -> tuple[int, int]:
    target_ratio = aspect_w / aspect_h
    best = _OPENAI_SIZES[0]
    best_diff = float("inf")
    for w, h in _OPENAI_SIZES:
        diff = abs((w / h) - target_ratio)
        if diff < best_diff:
            best, best_diff = (w, h), diff
    return best


def derive_size(aspect_ratio: str, resolution: str, provider: str, model: str = "") -> str:
    """返回 'WxH' 字符串。"""
    aspect = aspect_ratio if aspect_ratio in ASPECT_RATIOS else "1:1"
    res = resolution if resolution in RESOLUTIONS else "1080p"
    aw, ah = _parse_aspect(aspect)
    provider_l = (provider or "").strip().lower()
    model_l = (model or "").strip().lower()

    if provider_l in {"openai", "mirrorstages"} or model_l.startswith(("gpt-image", "dall-e")):
        w, h = _nearest_openai_size(aw, ah)
        return f"{w}x{h}"

    long_edge = _RESOLUTION_LONG_EDGE.get(res, 1024)
    if aw >= ah:
        w = long_edge
        h = _round_to_multiple(long_edge * ah / aw)
    else:
        h = long_edge
        w = _round_to_multiple(long_edge * aw / ah)
    return f"{w}x{h}"


def derive_quality(resolution: str, model: str = "") -> str:
    res = resolution if resolution in RESOLUTIONS else "1080p"
    model_l = (model or "").strip().lower()
    if model_l == "dall-e-3":
        return "hd" if res in {"1080p", "2k", "4k"} else "standard"
    return _RESOLUTION_QUALITY_OPENAI.get(res, "medium")


def derive_size_quality(config: dict[str, Any]) -> tuple[str, str]:
    """从 config 派生 (size, quality)。优先使用 aspect_ratio + resolution；
    若两者均缺省，回退到 config['size'] / config['quality']（向后兼容）。
    """
    aspect_ratio = str(config.get("aspect_ratio") or "").strip()
    resolution = str(config.get("resolution") or "").strip()
    provider = str(config.get("provider") or "openai").strip().lower()
    model = str(config.get("model") or "").strip()

    if aspect_ratio in ASPECT_RATIOS and resolution in RESOLUTIONS:
        return derive_size(aspect_ratio, resolution, provider, model), derive_quality(resolution, model)

    # 旧配置：直接使用已存的 size/quality
    legacy_size = str(config.get("size") or "1024x1536")
    legacy_quality = str(config.get("quality") or "medium")
    return legacy_size, legacy_quality


def infer_aspect_resolution(size: str, quality: str) -> tuple[str, str]:
    """从老配置的 size + quality 反推 aspect_ratio + resolution，仅用于 UI 初始填充。"""
    try:
        w_str, h_str = (size or "").lower().split("x")
        w, h = int(w_str), int(h_str)
    except (ValueError, AttributeError):
        return "9:16", "1080p"
    ratio = w / h if h else 1
    if abs(ratio - 1) < 0.05:
        aspect = "1:1"
    elif abs(ratio - 16 / 9) < 0.1:
        aspect = "16:9"
    elif abs(ratio - 9 / 16) < 0.1:
        aspect = "9:16"
    elif abs(ratio - 4 / 3) < 0.1:
        aspect = "4:3"
    elif abs(ratio - 3 / 4) < 0.1:
        aspect = "3:4"
    elif ratio > 1:
        aspect = "3:2"
    else:
        aspect = "2:3"
    long_edge = max(w, h)
    if long_edge >= 3000:
        resolution = "4k"
    elif long_edge >= 1800:
        resolution = "2k"
    elif long_edge >= 1000:
        resolution = "1080p"
    elif long_edge >= 700:
        resolution = "720p"
    else:
        resolution = "480p"
    return aspect, resolution
