# api_server.py
# -*- coding: utf-8 -*-
"""
NovelWriter FastAPI 后端入口
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

__version__ = "2.4.2"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

app = FastAPI(
    title="NovelWriter API",
    description="AI 小说生成器 REST + SSE API",
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

# ── 挂载路由 ─────────────────────────────────────────────────────────────────

from api.routers import (
    projects, config, presets, generate,
    styles, knowledge, files, logs, consistency, xp_presets,
    brainstorm, manju, images,
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

# ── 健康检查 ──────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "version": __version__}


# ── 生产模式：serve Vue 构建产物 ───────────────────────────────────────────────

_frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/", SPAStaticFiles(directory=_frontend_dist, html=True), name="static")
    logging.getLogger(__name__).info(f"Serving frontend from {_frontend_dist}")
else:
    logging.getLogger(__name__).info(
        "Frontend dist not found. Run 'cd frontend && npm run build' to build the UI."
    )
