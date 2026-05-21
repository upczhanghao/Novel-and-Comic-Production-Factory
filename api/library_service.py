# api/library_service.py
# -*- coding: utf-8 -*-
"""统一的"向量库 + 文件清单"管理服务。

同时服务于：
- 项目知识库（KnowledgeView）  → store_dir = {filepath}/vectorstore
- 作者参考库（StylesView）       → store_dir = {styles_dir}/{name}_author_vectorstore

每个库由三部分组成：
- Chroma 持久化向量库（实际存放 embedding）
- sources/ 目录          → 保留原始文本，用于重建 / 替换 / 查看来源
- manifest.json          → 文件级元数据（file_id / 标签 / 作者 / 切片数 / 状态）

向 Chroma 写入的每个 chunk 都带 metadata: file_id / filename
删除单文件时通过 collection.delete(where={"file_id": ...}) 精确移除该文件的全部向量。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import time
import traceback
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from novel_generator.vectorstore_utils import (
    _vectorstore_deps,
    _store_cache,
    split_text_for_vectorstore,
)
from novel_generator.knowledge import advanced_split_content

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────
# 配置
# ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LibraryConfig:
    store_dir: str                  # Chroma 持久化目录
    collection_name: str            # Chroma collection 名
    splitter: str = "paragraph"     # "paragraph" or "sentence"
    label: str = "library"          # 用于日志


def _manifest_path(cfg: LibraryConfig) -> str:
    return os.path.join(cfg.store_dir, "manifest.json")


def _sources_dir(cfg: LibraryConfig) -> str:
    return os.path.join(cfg.store_dir, "sources")


# ────────────────────────────────────────────────────────────────────
# Manifest 读写
# ────────────────────────────────────────────────────────────────────

def _load_manifest(cfg: LibraryConfig) -> dict:
    path = _manifest_path(cfg)
    if not os.path.exists(path):
        return {"version": 1, "files": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "files" not in data:
            return {"version": 1, "files": []}
        return data
    except Exception:
        logger.warning(f"[{cfg.label}] manifest 解析失败，重置")
        return {"version": 1, "files": []}


def _save_manifest(cfg: LibraryConfig, data: dict) -> None:
    os.makedirs(cfg.store_dir, exist_ok=True)
    path = _manifest_path(cfg)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _find_record(manifest: dict, file_id: str) -> Optional[dict]:
    for rec in manifest.get("files", []):
        if rec.get("file_id") == file_id:
            return rec
    return None


# ────────────────────────────────────────────────────────────────────
# Chroma 帮助
# ────────────────────────────────────────────────────────────────────

def _wrap_embedding_adapter(embedding_adapter):
    from langchain_core.embeddings import Embeddings as LCEmbeddings
    from novel_generator.common import call_with_retry

    class _Wrapper(LCEmbeddings):
        def embed_documents(self, texts):
            return call_with_retry(
                func=embedding_adapter.embed_documents,
                max_retries=3,
                fallback_return=[],
                texts=texts,
            )

        def embed_query(self, query: str):
            return call_with_retry(
                func=embedding_adapter.embed_query,
                max_retries=3,
                fallback_return=[],
                query=query,
            )

    return _Wrapper()


def _open_store(cfg: LibraryConfig, embedding_adapter, *, create: bool = False):
    Chroma, Settings, _ = _vectorstore_deps()
    if not create and not os.path.exists(cfg.store_dir):
        return None
    os.makedirs(cfg.store_dir, exist_ok=True)
    cache_key = (os.path.abspath(cfg.store_dir), cfg.collection_name)
    cached = _store_cache.get(cache_key)
    if cached is not None:
        return cached
    store = Chroma(
        persist_directory=cfg.store_dir,
        embedding_function=_wrap_embedding_adapter(embedding_adapter),
        client_settings=Settings(anonymized_telemetry=False),
        collection_name=cfg.collection_name,
    )
    _store_cache[cache_key] = store
    return store


def _evict_store(cfg: LibraryConfig) -> None:
    cache_key = (os.path.abspath(cfg.store_dir), cfg.collection_name)
    _store_cache.pop(cache_key, None)


def _collection_count(store) -> int:
    try:
        return store._collection.count()
    except Exception:
        return 0


# ────────────────────────────────────────────────────────────────────
# 文件切分
# ────────────────────────────────────────────────────────────────────

def _split(cfg: LibraryConfig, text: str) -> list[str]:
    if cfg.splitter == "paragraph":
        return [p for p in advanced_split_content(text) if str(p).strip()]
    return [s for s in split_text_for_vectorstore(text) if str(s).strip()]


def _decode_bytes(data: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "gbk", "gb18030", "big5", "shift_jis", "latin-1"):
        try:
            text = data.decode(enc)
            if text.strip():
                return text
        except (UnicodeDecodeError, UnicodeError):
            continue
    return data.decode("utf-8", errors="replace")


# ────────────────────────────────────────────────────────────────────
# 公共 API
# ────────────────────────────────────────────────────────────────────

def import_file(
    cfg: LibraryConfig,
    embedding_adapter,
    *,
    file_bytes: bytes,
    original_filename: str,
    tags: Optional[list[str]] = None,
    author: str = "",
) -> dict:
    """导入文件：写 source、切分、嵌入、写 manifest。返回 manifest 记录。"""
    if not file_bytes:
        raise ValueError("文件内容为空")

    text = _decode_bytes(file_bytes)
    if not text.strip():
        raise ValueError("文件内容解码后为空")

    chunks = _split(cfg, text)
    if not chunks:
        raise ValueError("文件切分后没有有效片段")

    file_id = uuid.uuid4().hex[:16]
    content_hash = hashlib.sha256(file_bytes).hexdigest()

    # 保存原始文本
    os.makedirs(_sources_dir(cfg), exist_ok=True)
    src_path = os.path.join(_sources_dir(cfg), f"{file_id}.txt")
    with open(src_path, "w", encoding="utf-8") as f:
        f.write(text)

    record = {
        "file_id": file_id,
        "filename": original_filename or f"{file_id}.txt",
        "original_filename": original_filename,
        "tags": list(tags or []),
        "author": author or "",
        "size_bytes": len(file_bytes),
        "char_count": len(text),
        "chunks": len(chunks),
        "imported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "content_hash": content_hash,
        "status": "indexing",
        "error": "",
    }

    manifest = _load_manifest(cfg)
    manifest.setdefault("files", []).append(record)
    _save_manifest(cfg, manifest)

    try:
        _index_chunks(cfg, embedding_adapter, file_id, record["filename"], chunks)
        record["status"] = "ok"
    except Exception as e:
        record["status"] = "error"
        record["error"] = str(e)
        logger.warning(f"[{cfg.label}] 索引失败 file_id={file_id}: {e}")
        traceback.print_exc()

    _save_manifest(cfg, manifest)
    return record


def _index_chunks(
    cfg: LibraryConfig,
    embedding_adapter,
    file_id: str,
    filename: str,
    chunks: list[str],
) -> None:
    """将切片插入到 Chroma，附 metadata。"""
    Chroma, Settings, Document = _vectorstore_deps()
    documents = [
        Document(
            page_content=str(c),
            metadata={"file_id": file_id, "filename": filename, "chunk_idx": i},
        )
        for i, c in enumerate(chunks)
    ]

    store = _open_store(cfg, embedding_adapter, create=True)
    if store is None:
        # 首次创建
        os.makedirs(cfg.store_dir, exist_ok=True)
        Chroma.from_documents(
            documents,
            embedding=_wrap_embedding_adapter(embedding_adapter),
            persist_directory=cfg.store_dir,
            client_settings=Settings(anonymized_telemetry=False),
            collection_name=cfg.collection_name,
        )
    else:
        store.add_documents(documents)


def list_files(cfg: LibraryConfig) -> list[dict]:
    """返回 manifest 中所有文件记录（按导入时间倒序）。"""
    manifest = _load_manifest(cfg)
    files = list(manifest.get("files", []))
    files.sort(key=lambda r: r.get("imported_at", ""), reverse=True)
    return files


def stats(cfg: LibraryConfig, embedding_adapter=None) -> dict:
    """库整体统计。embedding_adapter 缺失时只返回 manifest 统计。"""
    files = list_files(cfg)
    file_count = len(files)
    manifest_chunks = sum(int(r.get("chunks") or 0) for r in files)
    error_count = sum(1 for r in files if r.get("status") == "error")
    indexing_count = sum(1 for r in files if r.get("status") == "indexing")

    vector_count = None
    orphan_warning = ""
    if embedding_adapter is not None and os.path.exists(cfg.store_dir):
        try:
            store = _open_store(cfg, embedding_adapter)
            if store is not None:
                vector_count = _collection_count(store)
                if vector_count is not None and abs(vector_count - manifest_chunks) > 5:
                    orphan_warning = (
                        f"清单记录 {manifest_chunks} 条，向量库实际 {vector_count} 条。"
                        "可能存在旧导入残留，建议执行「重建索引」。"
                    )
        except Exception as e:
            logger.warning(f"[{cfg.label}] 读取向量库统计失败: {e}")

    return {
        "exists": os.path.exists(cfg.store_dir),
        "file_count": file_count,
        "manifest_chunks": manifest_chunks,
        "vector_count": vector_count,
        "error_count": error_count,
        "indexing_count": indexing_count,
        "orphan_warning": orphan_warning,
        "store_dir": cfg.store_dir,
    }


def delete_file(cfg: LibraryConfig, embedding_adapter, file_id: str) -> dict:
    """删除单个文件的向量、源文件与 manifest 条目。"""
    manifest = _load_manifest(cfg)
    rec = _find_record(manifest, file_id)
    if rec is None:
        raise KeyError(file_id)

    # 删 Chroma 向量
    if os.path.exists(cfg.store_dir):
        try:
            store = _open_store(cfg, embedding_adapter)
            if store is not None:
                store._collection.delete(where={"file_id": file_id})
        except Exception as e:
            logger.warning(f"[{cfg.label}] 删除向量失败 file_id={file_id}: {e}")

    # 删源文件
    src_path = os.path.join(_sources_dir(cfg), f"{file_id}.txt")
    if os.path.exists(src_path):
        try:
            os.remove(src_path)
        except OSError:
            pass

    manifest["files"] = [r for r in manifest.get("files", []) if r.get("file_id") != file_id]
    _save_manifest(cfg, manifest)
    return rec


def update_metadata(cfg: LibraryConfig, file_id: str, *,
                    filename: Optional[str] = None,
                    tags: Optional[list[str]] = None,
                    author: Optional[str] = None) -> dict:
    """重命名 / 改标签 / 改作者。不重建向量；只更新 manifest 与向量 metadata.filename（best effort）。"""
    manifest = _load_manifest(cfg)
    rec = _find_record(manifest, file_id)
    if rec is None:
        raise KeyError(file_id)

    if filename is not None:
        rec["filename"] = filename
    if tags is not None:
        rec["tags"] = list(tags)
    if author is not None:
        rec["author"] = author
    _save_manifest(cfg, manifest)
    return rec


def replace_file(
    cfg: LibraryConfig,
    embedding_adapter,
    *,
    file_id: str,
    file_bytes: bytes,
    original_filename: Optional[str] = None,
) -> dict:
    """替换指定文件的内容：删旧向量 + 删旧源 + 用相同 file_id 重新导入。"""
    manifest = _load_manifest(cfg)
    rec = _find_record(manifest, file_id)
    if rec is None:
        raise KeyError(file_id)

    if not file_bytes:
        raise ValueError("文件内容为空")
    text = _decode_bytes(file_bytes)
    if not text.strip():
        raise ValueError("文件内容解码后为空")

    chunks = _split(cfg, text)
    if not chunks:
        raise ValueError("文件切分后没有有效片段")

    # 删旧向量
    try:
        store = _open_store(cfg, embedding_adapter)
        if store is not None:
            store._collection.delete(where={"file_id": file_id})
    except Exception as e:
        logger.warning(f"[{cfg.label}] 删除旧向量失败 file_id={file_id}: {e}")

    # 覆盖源文件
    os.makedirs(_sources_dir(cfg), exist_ok=True)
    src_path = os.path.join(_sources_dir(cfg), f"{file_id}.txt")
    with open(src_path, "w", encoding="utf-8") as f:
        f.write(text)

    # 更新 manifest
    rec["filename"] = original_filename or rec.get("filename", f"{file_id}.txt")
    rec["original_filename"] = original_filename or rec.get("original_filename", "")
    rec["size_bytes"] = len(file_bytes)
    rec["char_count"] = len(text)
    rec["chunks"] = len(chunks)
    rec["imported_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    rec["content_hash"] = hashlib.sha256(file_bytes).hexdigest()
    rec["status"] = "indexing"
    rec["error"] = ""
    _save_manifest(cfg, manifest)

    try:
        _index_chunks(cfg, embedding_adapter, file_id, rec["filename"], chunks)
        rec["status"] = "ok"
    except Exception as e:
        rec["status"] = "error"
        rec["error"] = str(e)

    _save_manifest(cfg, manifest)
    return rec


def clear_library(cfg: LibraryConfig) -> None:
    """彻底清空：删除整个 store_dir。"""
    _evict_store(cfg)
    if os.path.exists(cfg.store_dir):
        try:
            shutil.rmtree(cfg.store_dir)
        except Exception as e:
            logger.warning(f"[{cfg.label}] 清空失败: {e}")
            raise


def rebuild_library(cfg: LibraryConfig, embedding_adapter) -> dict:
    """重建：删除 Chroma 目录但保留 sources + manifest，按 manifest 重新嵌入。"""
    manifest = _load_manifest(cfg)
    files = list(manifest.get("files", []))

    # 删除 Chroma 数据目录（不删 sources & manifest）
    if os.path.exists(cfg.store_dir):
        Chroma, _, _ = _vectorstore_deps()
        try:
            store = _open_store(cfg, embedding_adapter)
            if store is not None:
                try:
                    store.delete_collection()
                except Exception:
                    pass
        except Exception:
            pass
        _evict_store(cfg)
        # 物理清理 chroma 数据目录中除 manifest.json 与 sources/ 之外的内容
        for entry in os.listdir(cfg.store_dir):
            if entry in ("manifest.json", "sources"):
                continue
            full = os.path.join(cfg.store_dir, entry)
            try:
                if os.path.isdir(full):
                    shutil.rmtree(full)
                else:
                    os.remove(full)
            except Exception as e:
                logger.warning(f"[{cfg.label}] 清理目录 {full} 失败: {e}")

    ok = 0
    failed = 0
    for rec in files:
        file_id = rec.get("file_id")
        src_path = os.path.join(_sources_dir(cfg), f"{file_id}.txt")
        if not file_id or not os.path.exists(src_path):
            rec["status"] = "error"
            rec["error"] = "源文件缺失，无法重建（先重新导入）"
            failed += 1
            continue
        try:
            with open(src_path, "r", encoding="utf-8") as f:
                text = f.read()
            chunks = _split(cfg, text)
            rec["chunks"] = len(chunks)
            _index_chunks(cfg, embedding_adapter, file_id, rec.get("filename") or file_id, chunks)
            rec["status"] = "ok"
            rec["error"] = ""
            ok += 1
        except Exception as e:
            rec["status"] = "error"
            rec["error"] = str(e)
            failed += 1
            logger.warning(f"[{cfg.label}] 重建 file_id={file_id} 失败: {e}")

    manifest["files"] = files
    _save_manifest(cfg, manifest)
    return {"ok": ok, "failed": failed, "total": len(files)}


def search(
    cfg: LibraryConfig,
    embedding_adapter,
    *,
    query: str,
    k: int = 6,
    file_id: Optional[str] = None,
) -> list[dict]:
    """检索：返回带 filename / snippet / score 的 hits。"""
    if not query.strip():
        return []
    if not os.path.exists(cfg.store_dir):
        return []

    store = _open_store(cfg, embedding_adapter)
    if store is None:
        return []

    where = {"file_id": file_id} if file_id else None
    try:
        if where:
            docs_with_scores = store.similarity_search_with_relevance_scores(query, k=k, filter=where)
        else:
            docs_with_scores = store.similarity_search_with_relevance_scores(query, k=k)
    except Exception as e:
        logger.warning(f"[{cfg.label}] search 失败: {e}")
        return []

    hits: list[dict] = []
    for doc, score in docs_with_scores:
        meta = getattr(doc, "metadata", {}) or {}
        hits.append({
            "file_id": meta.get("file_id", ""),
            "filename": meta.get("filename", ""),
            "chunk_idx": meta.get("chunk_idx", -1),
            "score": float(score) if score is not None else 0.0,
            "snippet": doc.page_content[:600],
        })
    return hits


def get_source_text(cfg: LibraryConfig, file_id: str) -> Optional[str]:
    """读取已导入文件的原始文本（用于「查看原文」）。"""
    src_path = os.path.join(_sources_dir(cfg), f"{file_id}.txt")
    if not os.path.exists(src_path):
        return None
    with open(src_path, "r", encoding="utf-8") as f:
        return f.read()
