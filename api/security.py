# api/security.py
# -*- coding: utf-8 -*-
"""Shared security helpers for API routes."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from fastapi import HTTPException

REDACTED = "***"
_SENSITIVE_KEYS = {"api_key", "password", "token", "secret"}
_SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bms_[A-Za-z0-9]{16,}\b"),
    re.compile(r"(?i)(api[_-]?key|authorization|password|token|secret)(\s*[:=]\s*)[^\s,;}]+"),
]

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = WORKSPACE_ROOT / "output"


def redact_secrets(value: Any) -> Any:
    """Return a copy of nested config data with secret-like values masked."""
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if str(key).lower() in _SENSITIVE_KEYS:
                result[key] = REDACTED if item else item
            else:
                result[key] = redact_secrets(item)
        return result
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    return value


def redact_text(text: str) -> str:
    if not text:
        return text
    redacted = str(text)
    for pattern in _SECRET_PATTERNS:
        if pattern.pattern.startswith("(?i)"):
            redacted = pattern.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", redacted)
        else:
            redacted = pattern.sub(REDACTED, redacted)
    return redacted


def _resolve_workspace_path(path: str | os.PathLike[str], *, default: str = "./output") -> Path:
    raw = str(path or default).strip() or default
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = WORKSPACE_ROOT / candidate
    return candidate.resolve(strict=False)


def normalize_project_path(path: str | os.PathLike[str] = "./output", *, allow_blank: bool = True) -> str:
    """Normalize a project path and reject access outside the workspace."""
    raw = str(path or "").strip()
    if not raw and allow_blank:
        return ""

    resolved = _resolve_workspace_path(raw or "./output")
    try:
        resolved.relative_to(WORKSPACE_ROOT)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="路径必须位于项目工作区内") from exc
    return str(resolved)


def resolve_files_root(path: str | os.PathLike[str] = "") -> str:
    """Resolve the root for the file-manager endpoints.

    Blank input falls back to the workspace ``output/`` directory so the
    file manager works without an active project.
    """
    raw = str(path or "").strip()
    if not raw:
        return str(DEFAULT_OUTPUT_DIR)
    return normalize_project_path(raw, allow_blank=False)


def safe_join(base: str | os.PathLike[str], *parts: str | os.PathLike[str]) -> str:
    """Join path parts below a validated base directory."""
    safe_base = Path(normalize_project_path(base, allow_blank=False)).resolve(strict=False)
    target = safe_base.joinpath(*[str(part) for part in parts]).resolve(strict=False)
    try:
        target.relative_to(safe_base)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="路径访问被拒绝") from exc
    return str(target)


def default_cors_origins() -> list[str]:
    configured = os.getenv("NOVELWRITER_CORS_ORIGINS", "").strip()
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:7860",
        "http://127.0.0.1:7860",
    ]
