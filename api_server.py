# api_server.py
# -*- coding: utf-8 -*-
"""
Storia FastAPI 后端入口
替代 web_server.py（Gradio）

启动命令：
    uvicorn api_server:app --host 127.0.0.1 --port 7860 --reload
"""

import logging
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.security import default_cors_origins
from api.rate_limit import get_limiter

__version__ = "2.4.4"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

_logger = logging.getLogger(__name__)

app = FastAPI(
    title="Storia API",
    description="小说 · 漫剧 · 图片一站式生产 REST + SSE API",
    version=__version__,
)


class SPAStaticFiles(StaticFiles):
    """Serve Vue history-mode routes by falling back to index.html."""

    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise

# CORS —— 开发阶段允许本地前端（:3000）访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=default_cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers_and_optional_api_token(request: Request, call_next):
    """Add baseline security headers and support opt-in API token protection."""
    token = os.getenv("NOVELWRITER_API_TOKEN", "").strip()
    if (
        token
        and request.method != "OPTIONS"
        and request.url.path.startswith("/api")
        and request.url.path != "/api/health"
    ):
        supplied = request.headers.get("X-NovelWriter-Token", "")
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            supplied = auth.removeprefix("Bearer ").strip()
        if supplied != token:
            return JSONResponse({"detail": "未授权访问"}, status_code=401)

    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    return response


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """滑动窗口限流。仅作用于 /api/*，OPTIONS 预检直接放行。"""
    path = request.url.path
    if request.method == "OPTIONS" or not path.startswith("/api"):
        return await call_next(request)
    # 取首跳 IP，兼容 Cloudflare / nginx 反代
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        client_id = fwd.split(",")[0].strip()
    else:
        client_id = request.client.host if request.client else "unknown"
    allowed, info = get_limiter().check_and_record(path, client_id)
    if not allowed:
        retry = (info or {}).get("retry_after", 60)
        return JSONResponse(
            {"detail": "请求过于频繁，请稍后再试"},
            status_code=429,
            headers={"Retry-After": str(retry)},
        )
    return await call_next(request)

# ── 全局异常脱敏 ──────────────────────────────────────────────────────────────
# HTTPException 信任开发者写的 detail，原样返回；未捕获异常只返回通用提示，详情落日志。

@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    _logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "服务器内部错误，请稍后再试"}, status_code=500)


# ── 挂载路由 ─────────────────────────────────────────────────────────────────

from api.routers import (
    projects, config, presets, generate,
    styles, knowledge, files, logs, consistency, xp_presets,
    brainstorm, manju, images, security, usage,
)

app.include_router(projects.router, prefix="/api")
app.include_router(config.router, prefix="/api")
app.include_router(presets.router, prefix="/api")
app.include_router(generate.router, prefix="/api")
app.include_router(styles.router, prefix="/api")
app.include_router(knowledge.router, prefix="/api")
app.include_router(files.router, prefix="/api")
app.include_router(logs.router, prefix="/api")
app.include_router(consistency.router, prefix="/api")
app.include_router(xp_presets.router, prefix="/api")
app.include_router(brainstorm.router, prefix="/api")
app.include_router(manju.router, prefix="/api")
app.include_router(images.router, prefix="/api")
app.include_router(security.router, prefix="/api")
app.include_router(usage.router, prefix="/api")

# ── 健康检查 ──────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok"}


# ── 生产模式：serve Vue 构建产物 ───────────────────────────────────────────────

_frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/", SPAStaticFiles(directory=_frontend_dist, html=True), name="static")
    logging.getLogger(__name__).info(f"Serving frontend from {_frontend_dist}")
else:
    logging.getLogger(__name__).info(
        "Frontend dist not found. Run 'cd frontend && npm run build' to build the UI."
    )
