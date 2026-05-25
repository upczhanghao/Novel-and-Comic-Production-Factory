# api/routers/usage.py
# -*- coding: utf-8 -*-
"""Token 使用统计接口。"""

from fastapi import APIRouter, Query

from api.usage_meter import get_meter

router = APIRouter(tags=["usage"])


@router.get("/usage/stats")
def usage_stats():
    return get_meter().stats()


@router.get("/usage/history")
def usage_history(limit: int = Query(100, ge=1, le=500)):
    return {"items": get_meter().history(limit=limit)}
