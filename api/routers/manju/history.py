# api/routers/manju/history.py
# -*- coding: utf-8 -*-
"""A5: 漫剧版本历史的服务端持久化。

每个项目的快照写入 `manju/history/{kind}.json`，按 kind 分文件。
单文件保留最近 MAX_PER_KIND 条；payload 任意 JSON。
"""

import json
import logging
import os
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .parser import _work_dir

router = APIRouter(tags=["manju"])
logger = logging.getLogger(__name__)

ALLOWED_KINDS = {"script", "characters", "scenes", "storyboards"}
MAX_PER_KIND = 20


def _history_dir(filepath: str) -> str:
    path = os.path.join(_work_dir(filepath), "history")
    os.makedirs(path, exist_ok=True)
    return path


def _history_path(filepath: str, kind: str) -> str:
    if kind not in ALLOWED_KINDS:
        raise HTTPException(status_code=400, detail=f"未知的 kind: {kind}")
    return os.path.join(_history_dir(filepath), f"{kind}.json")


def _read_kind(filepath: str, kind: str) -> list[dict]:
    p = _history_path(filepath, kind)
    if not os.path.exists(p):
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as exc:
        logger.warning("读取漫剧历史失败 %s: %s", p, exc)
        return []


def _write_kind(filepath: str, kind: str, items: list[dict]):
    p = _history_path(filepath, kind)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


class SnapshotCreate(BaseModel):
    kind: str
    label: str | None = None
    payload: Any


@router.get("/manju/history")
def list_history(filepath: str = Query(...), kind: str = Query(...)):
    items = _read_kind(filepath, kind)
    items_sorted = sorted(items, key=lambda s: s.get("ts", 0), reverse=True)
    return {"snapshots": items_sorted}


@router.post("/manju/history")
def create_snapshot(filepath: str, body: SnapshotCreate):
    if body.kind not in ALLOWED_KINDS:
        raise HTTPException(status_code=400, detail=f"未知的 kind: {body.kind}")
    items = _read_kind(filepath, body.kind)
    snap = {
        "ts": int(time.time() * 1000),
        "kind": body.kind,
        "label": body.label or "",
        "payload": body.payload,
    }
    items.append(snap)
    if len(items) > MAX_PER_KIND:
        items = items[-MAX_PER_KIND:]
    _write_kind(filepath, body.kind, items)
    return {"snapshot": snap}


@router.delete("/manju/history/{kind}/{ts}")
def delete_snapshot(kind: str, ts: int, filepath: str = Query(...)):
    items = _read_kind(filepath, kind)
    new_items = [s for s in items if s.get("ts") != ts]
    if len(new_items) == len(items):
        raise HTTPException(status_code=404, detail="未找到指定快照")
    _write_kind(filepath, kind, new_items)
    return {"message": "已删除"}


@router.delete("/manju/history/{kind}")
def clear_kind(kind: str, filepath: str = Query(...)):
    if kind not in ALLOWED_KINDS:
        raise HTTPException(status_code=400, detail=f"未知的 kind: {kind}")
    p = _history_path(filepath, kind)
    if os.path.exists(p):
        os.remove(p)
    return {"message": "已清空"}
