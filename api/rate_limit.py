# api/rate_limit.py
# -*- coding: utf-8 -*-
"""轻量级滑动窗口限流器 + 实时统计。

设计取舍
--------
单进程 uvicorn 部署，限流状态存内存即可；多进程/多副本场景需要换 Redis。
配置（每分钟阈值、桶分类规则）落 ``rate_limits.json``，UI 可热更，无需重启。
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from utils import atomic_write_json

_RATE_LIMITS_FILE = os.getenv(
    "NOVELWRITER_RATE_LIMITS_FILE",
    "rate_limits.json",
)

_DEFAULTS = {
    "enabled": True,
    "buckets": {
        # 每个桶：{"per_min": int, "path_prefixes": [str, ...]}
        # 顺序敏感：第一个匹配前缀的桶生效；都不匹配回落到 "default"
        "generate": {
            "per_min": 10,
            "path_prefixes": [
                "/api/generate/",
                "/api/manju/generate",
                "/api/images/generate",
                "/api/config/llm/test",
                "/api/config/embedding/test",
                "/api/config/image/test",
                "/api/knowledge/import",
                "/api/knowledge/files/",  # replace 也走这里
            ],
        },
        "default": {
            "per_min": 60,
            "path_prefixes": ["/api/"],
        },
    },
    # 永远豁免（健康检查、限流自身的查询、用量查询）
    "exempt_path_prefixes": [
        "/api/health",
        "/api/security/rate-limits",
        "/api/usage/",
    ],
}

_WINDOW_SECONDS = 60


@dataclass
class _Counter:
    # 按秒分桶的滑动窗口；每秒内的请求数 + 拒绝数
    hits: deque = field(default_factory=lambda: deque(maxlen=_WINDOW_SECONDS))
    rejects: deque = field(default_factory=lambda: deque(maxlen=_WINDOW_SECONDS))
    total_hits: int = 0
    total_rejects: int = 0
    last_reject_at: float = 0.0


class RateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._config: dict = {}
        # key = (bucket_name, client_id) -> _Counter
        self._counters: dict[tuple[str, str], _Counter] = {}
        # 全局每桶聚合（不分 IP），用于 UI 概览
        self._bucket_totals: dict[str, _Counter] = {}
        self._load()

    # ── 配置 ───────────────────────────────────────────────────────────
    def _load(self) -> None:
        with self._lock:
            self._config = self._read_file()

    def _read_file(self) -> dict:
        if os.path.exists(_RATE_LIMITS_FILE):
            try:
                with open(_RATE_LIMITS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # 浅合并，保证新增字段不会丢
                merged = {**_DEFAULTS, **data}
                merged["buckets"] = {**_DEFAULTS["buckets"], **(data.get("buckets") or {})}
                return merged
            except Exception:
                pass
        return json.loads(json.dumps(_DEFAULTS))  # deepcopy

    def get_config(self) -> dict:
        with self._lock:
            return json.loads(json.dumps(self._config))

    def update_config(self, patch: dict) -> dict:
        """合并写入并落盘。仅允许更新已知字段。"""
        with self._lock:
            cfg = self._config
            if "enabled" in patch:
                cfg["enabled"] = bool(patch["enabled"])
            if "buckets" in patch and isinstance(patch["buckets"], dict):
                for name, b in patch["buckets"].items():
                    if not isinstance(b, dict):
                        continue
                    bucket = cfg["buckets"].setdefault(name, {"per_min": 60, "path_prefixes": []})
                    if "per_min" in b:
                        per_min = int(b["per_min"])
                        bucket["per_min"] = max(0, min(per_min, 100000))
                    if "path_prefixes" in b and isinstance(b["path_prefixes"], list):
                        bucket["path_prefixes"] = [str(p) for p in b["path_prefixes"] if p]
            if "exempt_path_prefixes" in patch and isinstance(patch["exempt_path_prefixes"], list):
                cfg["exempt_path_prefixes"] = [str(p) for p in patch["exempt_path_prefixes"] if p]
            atomic_write_json(cfg, _RATE_LIMITS_FILE, indent=2)
            return json.loads(json.dumps(cfg))

    # ── 分类 ───────────────────────────────────────────────────────────
    def classify(self, path: str) -> Optional[str]:
        """返回桶名；None 表示豁免（不计数也不限流）。"""
        cfg = self._config
        for p in cfg.get("exempt_path_prefixes", []):
            if path.startswith(p):
                return None
        buckets = cfg.get("buckets", {})
        # 按字典插入顺序匹配；default 放最后
        ordered = [(k, v) for k, v in buckets.items() if k != "default"]
        ordered.append(("default", buckets.get("default", {"per_min": 60, "path_prefixes": ["/api/"]})))
        for name, spec in ordered:
            for prefix in spec.get("path_prefixes", []):
                if path.startswith(prefix):
                    return name
        return None

    # ── 计数 ───────────────────────────────────────────────────────────
    def _trim(self, counter: _Counter, now_sec: int) -> None:
        cutoff = now_sec - _WINDOW_SECONDS
        while counter.hits and counter.hits[0][0] <= cutoff:
            counter.hits.popleft()
        while counter.rejects and counter.rejects[0][0] <= cutoff:
            counter.rejects.popleft()

    def _bucket_total(self, name: str) -> _Counter:
        c = self._bucket_totals.get(name)
        if c is None:
            c = _Counter()
            self._bucket_totals[name] = c
        return c

    def check_and_record(self, path: str, client_id: str) -> tuple[bool, Optional[dict]]:
        """返回 (allowed, info)。info 在被拒时附带 retry_after 等。"""
        with self._lock:
            cfg = self._config
            if not cfg.get("enabled", True):
                return True, None
            bucket = self.classify(path)
            if bucket is None:
                return True, None
            spec = cfg["buckets"].get(bucket, {})
            limit = int(spec.get("per_min", 0) or 0)
            now = time.time()
            now_sec = int(now)
            counter = self._counters.setdefault((bucket, client_id), _Counter())
            total = self._bucket_total(bucket)
            self._trim(counter, now_sec)
            self._trim(total, now_sec)

            current = sum(c for _, c in counter.hits)
            if limit > 0 and current >= limit:
                counter.rejects.append((now_sec, 1))
                counter.total_rejects += 1
                counter.last_reject_at = now
                total.rejects.append((now_sec, 1))
                total.total_rejects += 1
                return False, {"bucket": bucket, "limit": limit, "retry_after": 60}

            counter.hits.append((now_sec, 1))
            counter.total_hits += 1
            total.hits.append((now_sec, 1))
            total.total_hits += 1
            return True, {"bucket": bucket, "limit": limit, "current": current + 1}

    # ── 统计 ───────────────────────────────────────────────────────────
    def stats(self) -> dict:
        """供 UI 展示：每桶最近 60s 命中/拒绝、累计、Top IP。"""
        with self._lock:
            now_sec = int(time.time())
            cfg = self._config
            buckets_out = {}
            for name, spec in cfg.get("buckets", {}).items():
                total = self._bucket_total(name)
                self._trim(total, now_sec)
                hits_60s = sum(c for _, c in total.hits)
                rejects_60s = sum(c for _, c in total.rejects)
                buckets_out[name] = {
                    "per_min": int(spec.get("per_min", 0) or 0),
                    "hits_60s": hits_60s,
                    "rejects_60s": rejects_60s,
                    "total_hits": total.total_hits,
                    "total_rejects": total.total_rejects,
                    "path_prefixes": list(spec.get("path_prefixes", [])),
                }

            # Top 5 IP（按最近 60s 命中数）
            ip_agg: dict[str, dict] = {}
            for (bucket, cid), counter in self._counters.items():
                self._trim(counter, now_sec)
                hits = sum(c for _, c in counter.hits)
                rejects = sum(c for _, c in counter.rejects)
                if hits == 0 and rejects == 0:
                    continue
                row = ip_agg.setdefault(cid, {"client": cid, "hits_60s": 0, "rejects_60s": 0, "buckets": {}})
                row["hits_60s"] += hits
                row["rejects_60s"] += rejects
                row["buckets"][bucket] = {"hits_60s": hits, "rejects_60s": rejects}
            top_clients = sorted(ip_agg.values(), key=lambda r: r["hits_60s"], reverse=True)[:10]

            return {
                "enabled": cfg.get("enabled", True),
                "window_seconds": _WINDOW_SECONDS,
                "buckets": buckets_out,
                "top_clients": top_clients,
                "exempt_path_prefixes": list(cfg.get("exempt_path_prefixes", [])),
            }


_limiter = RateLimiter()


def get_limiter() -> RateLimiter:
    return _limiter
