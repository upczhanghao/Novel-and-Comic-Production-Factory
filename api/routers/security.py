# api/routers/security.py
# -*- coding: utf-8 -*-
"""限流配置查询与热更，以及实时统计。"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from api.rate_limit import get_limiter

router = APIRouter(tags=["security"])


class BucketPatch(BaseModel):
    per_min: Optional[int] = None
    path_prefixes: Optional[list[str]] = None


class RateLimitsPatch(BaseModel):
    enabled: Optional[bool] = None
    buckets: Optional[dict[str, BucketPatch]] = None
    exempt_path_prefixes: Optional[list[str]] = None


@router.get("/security/rate-limits")
def get_rate_limits():
    limiter = get_limiter()
    return {
        "config": limiter.get_config(),
        "stats": limiter.stats(),
    }


@router.put("/security/rate-limits")
def update_rate_limits(patch: RateLimitsPatch):
    try:
        cfg = get_limiter().update_config(patch.model_dump(exclude_none=True))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"配置更新失败：{e}")
    return {"config": cfg}
