# ── Stage 1: 构建前端 ─────────────────────────────────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi
COPY frontend/ .
RUN npm run build

# ── Stage 2: Python 后端 + 前端产物 ──────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    NOVELWRITER_HOST=0.0.0.0 \
    NOVELWRITER_PORT=7860 \
    NOVELWRITER_CONFIG_FILE=/app/data/config.json \
    NOVELWRITER_PROJECTS_FILE=/app/data/projects.json \
    NOVELWRITER_XP_PRESETS_FILE=/app/data/xp_presets.json

# 安装系统依赖。部分 Python 包需要编译环境；curl 用于健康检查兜底。
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# 下载指定的 NLTK 资源。失败不阻断镜像构建，运行时仍可由业务代码按需下载/处理。
RUN python -c "import nltk; nltk.download('punkt_tab')" || true

# 复制项目文件
COPY . .

# 复制前端构建产物
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# 创建数据目录，并提供容器首次启动所需的 JSON 文件。
RUN mkdir -p /app/data /app/output /app/styles /app/prompts /app/vectorstore && \
    test -f /app/data/projects.json || printf '{"active_project":"","projects":{}}\n' > /app/data/projects.json && \
    test -f /app/data/xp_presets.json || printf '[]\n' > /app/data/xp_presets.json

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/api/health')" || exit 1

CMD ["sh", "-c", "mkdir -p /app/data /app/output /app/styles /app/prompts /app/vectorstore && { test -f \"$NOVELWRITER_PROJECTS_FILE\" || printf '{\"active_project\":\"\",\"projects\":{}}\\n' > \"$NOVELWRITER_PROJECTS_FILE\"; } && { test -f \"$NOVELWRITER_XP_PRESETS_FILE\" || printf '[]\\n' > \"$NOVELWRITER_XP_PRESETS_FILE\"; } && exec uvicorn api_server:app --host \"$NOVELWRITER_HOST\" --port \"$NOVELWRITER_PORT\""]
