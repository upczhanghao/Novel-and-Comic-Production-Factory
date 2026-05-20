# api/library_helpers.py
# -*- coding: utf-8 -*-
"""帮助函数：把 web app 状态适配到 LibraryConfig + embedding adapter。"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import HTTPException

from api.library_service import LibraryConfig
from novel_generator.vectorstore_utils import (
    get_author_vectorstore_dir,
    get_vectorstore_dir,
)


def resolve_embedding_adapter(app, emb_config_name: Optional[str]):
    """根据 config name 创建 embedding adapter；缺失/无效时抛 400。"""
    name = (emb_config_name or "").strip()
    if not name:
        name = (app.config.get("default_embedding_config") or "").strip()
    configs = app.config.get("embedding_configs", {}) or {}
    if not name or name not in configs:
        raise HTTPException(
            status_code=400,
            detail="❌ 请先在「配置 → Embedding」中创建并选择 Embedding 配置",
        )
    conf = configs[name]
    from embedding_adapters import create_embedding_adapter
    return create_embedding_adapter(
        conf.get("interface_format", name),
        conf["api_key"],
        conf["base_url"],
        conf["model_name"],
    )


def knowledge_cfg(filepath: str) -> LibraryConfig:
    return LibraryConfig(
        store_dir=get_vectorstore_dir(filepath),
        collection_name="novel_collection",
        splitter="paragraph",
        label=f"knowledge:{os.path.basename(filepath)}",
    )


def author_ref_cfg(style_name: str, styles_dir: str) -> LibraryConfig:
    return LibraryConfig(
        store_dir=get_author_vectorstore_dir(style_name=style_name, styles_dir=styles_dir),
        collection_name="author_reference_collection",
        splitter="sentence",
        label=f"author_ref:{style_name}",
    )
