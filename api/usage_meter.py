# api/usage_meter.py
# -*- coding: utf-8 -*-
"""LLM / 图片接口 token 用量统计 — 内存滑动窗口 + JSONL 持久化 + 重启重放当日累计。

设计要点：
- 不阻塞主线程：record_usage 在锁内只做 dict/deque 操作 + 一次小行追加 IO；落盘失败仅打印警告。
- 重启不丢"今日累计"：进程启动 replay 当日 JSONL（按本地时区分日）。
- 不存 prompt/response 文本，仅存元信息和 token 数；可与 prompt_history.jsonl 隐私开关解耦。
- 多线程安全：单 threading.Lock。
- 风格对齐 rate_limit.py：内存为主、JSON 为辅、重启自愈。
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# 路径与配置
# ---------------------------------------------------------------------------

_USAGE_LOG_FILE = os.environ.get(
    "NOVELWRITER_USAGE_LOG",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "usage_history.jsonl"),
)

_WINDOW_60S = 60
_WINDOW_1H = 60 * 60
_RECENT_LIMIT = 500  # 内存里保留最近 N 条调用记录用于 history 接口


@dataclass
class _Bucket:
    """按秒分桶的滑动窗口计数（tokens & calls）。"""
    calls: deque = field(default_factory=lambda: deque(maxlen=_WINDOW_1H))
    prompt_tokens: deque = field(default_factory=lambda: deque(maxlen=_WINDOW_1H))
    completion_tokens: deque = field(default_factory=lambda: deque(maxlen=_WINDOW_1H))
    # 累计（lifetime）
    total_calls: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    # 当日（按本地日期 key 滚动）
    today_date: str = ""
    today_calls: int = 0
    today_prompt_tokens: int = 0
    today_completion_tokens: int = 0


def _today_key() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _push_window(buckets: deque, now: int, value: int) -> None:
    """在按秒分桶的 deque 上累加；同一秒合并。"""
    if buckets and buckets[-1][0] == now:
        ts, total = buckets[-1]
        buckets[-1] = (ts, total + value)
    else:
        buckets.append((now, value))


def _sum_window(buckets: deque, now: int, span: int) -> int:
    cutoff = now - span
    return sum(v for ts, v in buckets if ts > cutoff)


class UsageMeter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        # 维度键：('config'|'model'|'provider'|'kind', name) -> _Bucket
        self._buckets: dict[tuple[str, str], _Bucket] = defaultdict(_Bucket)
        # 全局总桶
        self._total: _Bucket = _Bucket()
        # 最近调用流水（用于 /api/usage/history）
        self._recent: deque[dict] = deque(maxlen=_RECENT_LIMIT)
        # 启动时重放当日 JSONL，恢复 today_* 计数（窗口数据不重放，避免延迟启动卡顿）
        self._replay_today()

    # ── 公开 API ────────────────────────────────────────────────────────

    def record(self, *, kind: str, provider: str, config_name: str, model: str,
               prompt_tokens: int, completion_tokens: int,
               total_tokens: int | None = None,
               elapsed_ms: int = 0,
               source: str = "exact",
               note: str = "") -> None:
        """记录一次调用。

        kind: "chat" | "image" | "embedding"
        source: "exact"（来自 SDK usage）| "estimated"（tiktoken/字符估算）| "missing"（厂商未返回）
        """
        if total_tokens is None:
            total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)
        prompt_tokens = max(0, int(prompt_tokens or 0))
        completion_tokens = max(0, int(completion_tokens or 0))
        total_tokens = max(0, int(total_tokens))

        now = int(time.time())
        today = _today_key()
        record = {
            "ts": now,
            "iso": datetime.now().isoformat(timespec="seconds"),
            "kind": kind or "chat",
            "provider": provider or "",
            "config_name": config_name or "",
            "model": model or "",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "elapsed_ms": int(elapsed_ms or 0),
            "source": source or "exact",
        }
        if note:
            record["note"] = note

        with self._lock:
            for key in (
                ("kind", record["kind"]),
                ("provider", record["provider"] or "(unknown)"),
                ("config", record["config_name"] or "(default)"),
                ("model", record["model"] or "(unknown)"),
            ):
                self._touch(self._buckets[key], now, today, prompt_tokens, completion_tokens)
            self._touch(self._total, now, today, prompt_tokens, completion_tokens)
            self._recent.append(record)

        # JSONL 持久化（在锁外）
        try:
            os.makedirs(os.path.dirname(_USAGE_LOG_FILE), exist_ok=True)
            with open(_USAGE_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as exc:
            # 永远不让落盘失败影响主流程
            print(f"[usage_meter] persist failed: {exc}")

    def stats(self) -> dict[str, Any]:
        """返回当前统计快照。"""
        now = int(time.time())
        today = _today_key()
        with self._lock:
            # 滚动当日（午夜过后）：先把不是 today 的桶清零 today_*
            self._roll_today_if_needed(today)

            def snapshot(b: _Bucket) -> dict:
                return {
                    "calls_60s": _sum_window(b.calls, now, _WINDOW_60S),
                    "prompt_tokens_60s": _sum_window(b.prompt_tokens, now, _WINDOW_60S),
                    "completion_tokens_60s": _sum_window(b.completion_tokens, now, _WINDOW_60S),
                    "calls_1h": _sum_window(b.calls, now, _WINDOW_1H),
                    "prompt_tokens_1h": _sum_window(b.prompt_tokens, now, _WINDOW_1H),
                    "completion_tokens_1h": _sum_window(b.completion_tokens, now, _WINDOW_1H),
                    "today_calls": b.today_calls,
                    "today_prompt_tokens": b.today_prompt_tokens,
                    "today_completion_tokens": b.today_completion_tokens,
                    "total_calls": b.total_calls,
                    "total_prompt_tokens": b.total_prompt_tokens,
                    "total_completion_tokens": b.total_completion_tokens,
                }

            by_dim: dict[str, list[dict[str, Any]]] = {"kind": [], "provider": [], "config": [], "model": []}
            for (dim, name), b in self._buckets.items():
                snap = snapshot(b)
                snap["name"] = name
                by_dim[dim].append(snap)
            for dim_list in by_dim.values():
                dim_list.sort(key=lambda r: r["today_prompt_tokens"] + r["today_completion_tokens"], reverse=True)

            return {
                "now": now,
                "today": today,
                "total": snapshot(self._total),
                "by_dim": by_dim,
            }

    def history(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            n = max(1, min(int(limit or 100), _RECENT_LIMIT))
            return list(self._recent)[-n:][::-1]  # 最新在前

    # ── 内部 ────────────────────────────────────────────────────────────

    def _touch(self, b: _Bucket, now: int, today: str,
               prompt_tokens: int, completion_tokens: int) -> None:
        _push_window(b.calls, now, 1)
        _push_window(b.prompt_tokens, now, prompt_tokens)
        _push_window(b.completion_tokens, now, completion_tokens)
        b.total_calls += 1
        b.total_prompt_tokens += prompt_tokens
        b.total_completion_tokens += completion_tokens
        if b.today_date != today:
            b.today_date = today
            b.today_calls = 0
            b.today_prompt_tokens = 0
            b.today_completion_tokens = 0
        b.today_calls += 1
        b.today_prompt_tokens += prompt_tokens
        b.today_completion_tokens += completion_tokens

    def _roll_today_if_needed(self, today: str) -> None:
        if self._total.today_date and self._total.today_date != today:
            for b in self._buckets.values():
                b.today_date = today
                b.today_calls = 0
                b.today_prompt_tokens = 0
                b.today_completion_tokens = 0
            self._total.today_date = today
            self._total.today_calls = 0
            self._total.today_prompt_tokens = 0
            self._total.today_completion_tokens = 0

    def _replay_today(self) -> None:
        """启动时重放当日 JSONL，恢复 today_* 与 total_*；不恢复秒级窗口。"""
        if not os.path.exists(_USAGE_LOG_FILE):
            return
        today = _today_key()
        try:
            with open(_USAGE_LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            return
        # 只看当日条目，按 today 字符串前缀匹配 iso
        for raw in lines[-_RECENT_LIMIT * 4 :]:
            try:
                rec = json.loads(raw)
            except Exception:
                continue
            iso = rec.get("iso", "")
            if not iso.startswith(today):
                continue
            pt = int(rec.get("prompt_tokens") or 0)
            ct = int(rec.get("completion_tokens") or 0)
            for key in (
                ("kind", rec.get("kind") or "chat"),
                ("provider", rec.get("provider") or "(unknown)"),
                ("config", rec.get("config_name") or "(default)"),
                ("model", rec.get("model") or "(unknown)"),
            ):
                b = self._buckets[key]
                b.total_calls += 1
                b.total_prompt_tokens += pt
                b.total_completion_tokens += ct
                if b.today_date != today:
                    b.today_date = today
                b.today_calls += 1
                b.today_prompt_tokens += pt
                b.today_completion_tokens += ct
            self._total.total_calls += 1
            self._total.total_prompt_tokens += pt
            self._total.total_completion_tokens += ct
            if self._total.today_date != today:
                self._total.today_date = today
            self._total.today_calls += 1
            self._total.today_prompt_tokens += pt
            self._total.today_completion_tokens += ct
            # 只把最近 N 条放到 _recent 用于 history 接口
            self._recent.append(rec)


# ── 单例 ───────────────────────────────────────────────────────────────────

_meter: UsageMeter | None = None
_meter_lock = threading.Lock()


def get_meter() -> UsageMeter:
    global _meter
    if _meter is None:
        with _meter_lock:
            if _meter is None:
                _meter = UsageMeter()
    return _meter


def record_usage(**kwargs: Any) -> None:
    """便捷顶层 API；任何异常都吞掉，绝不影响主流程。"""
    try:
        get_meter().record(**kwargs)
    except Exception as exc:
        print(f"[usage_meter] record failed: {exc}")


def extract_openai_usage(response: Any) -> dict[str, int] | None:
    """从 OpenAI / OpenAI 兼容接口的非流式响应里提 usage。"""
    if response is None:
        return None
    payload = response.model_dump() if hasattr(response, "model_dump") else (response if isinstance(response, dict) else None)
    if not isinstance(payload, dict):
        return None
    u = payload.get("usage") or {}
    if not isinstance(u, dict):
        return None
    pt = int(u.get("prompt_tokens") or u.get("input_tokens") or 0)
    ct = int(u.get("completion_tokens") or u.get("output_tokens") or 0)
    tt = int(u.get("total_tokens") or (pt + ct))
    if pt == 0 and ct == 0 and tt == 0:
        return None
    return {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt}


def extract_gemini_usage(response: Any) -> dict[str, int] | None:
    """Gemini SDK：response.usage_metadata"""
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return None
    pt = int(getattr(meta, "prompt_token_count", 0) or 0)
    ct = int(getattr(meta, "candidates_token_count", 0) or 0)
    tt = int(getattr(meta, "total_token_count", 0) or (pt + ct))
    if pt == 0 and ct == 0 and tt == 0:
        return None
    return {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt}


def extract_langchain_usage(message: Any) -> dict[str, int] | None:
    """LangChain AIMessage 的 usage_metadata / response_metadata.token_usage"""
    if message is None:
        return None
    meta = getattr(message, "usage_metadata", None) or {}
    if isinstance(meta, dict) and meta:
        pt = int(meta.get("input_tokens") or 0)
        ct = int(meta.get("output_tokens") or 0)
        tt = int(meta.get("total_tokens") or (pt + ct))
        if pt or ct or tt:
            return {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt}
    rm = getattr(message, "response_metadata", None) or {}
    if isinstance(rm, dict):
        u = rm.get("token_usage") or {}
        if isinstance(u, dict):
            pt = int(u.get("prompt_tokens") or 0)
            ct = int(u.get("completion_tokens") or 0)
            tt = int(u.get("total_tokens") or (pt + ct))
            if pt or ct or tt:
                return {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt}
    return None
