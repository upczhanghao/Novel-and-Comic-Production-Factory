# Novel and Comic Production Factory

一个面向小说创作、漫剧制作和 AI 图片生成的本地化创作工作台。项目当前采用 **Vue 3 + TypeScript + Vite** 前端、**FastAPI + SSE** 后端，生产模式由 FastAPI 直接托管前端构建产物，支持本地一键脚本启动和 Docker Compose 部署。

## 核心功能

| 模块 | 作用 |
| --- | --- |
| 创作工坊 | 从题材设定、小说架构、章节目录、详细细纲到正文生成、定稿、去 AI 痕迹、续写扩展的一体化小说生产流程 |
| 漫剧制作 | 导入小说 TXT，生成漫剧剧本、角色信息、角色卡提示词、章节场景图提示词、章节分镜图提示词，并支持制片数据、连续性检查、分镜生图和队列导入 |
| 图片生成 | 使用图片模型根据提示词生成图片，管理待生成提示词队列和生成记录，支持删除任务并同步更新本地记录文件 |
| 模型配置 | 配置 LLM、Embedding、图片生成模型、网络代理和默认配置选择 |
| 指令配置 | 配置漫剧制作相关 AI 指令模板，包括小说改编、角色信息与角色卡、场景图、分镜图提示词生成 |
| 提示词方案 | 管理小说创作各阶段提示词预设，内置网络小说、悬疑推理、玄幻升级流、科幻群像、古言权谋等方案 |
| 文风与 DNA | 分析并保存文风模板、叙事 DNA、作者参考库，供架构、目录、章节和漫剧流程复用 |
| 知识库 | 导入外部参考资料并向量化检索，在生成章节时注入相关资料 |
| 创意讨论 | 多模式 AI 头脑风暴，可注入当前项目上下文和用户画像 |
| 用户画像 | 维护全局创作偏好，支持从文本中提取偏好并在生成时参考 |
| 一致性检查 | 检查章节、设定和角色状态之间的矛盾 |
| 文件管理 / 阅读器 / 日志 | 管理项目文件、阅读章节正文、查看运行日志和提示词历史 |

## 技术栈

- 前端：Vue 3、TypeScript、Vite、Pinia、Vue Router、Tailwind CSS
- 后端：FastAPI、Uvicorn、SSE 流式输出
- LLM 适配：OpenAI 兼容接口、DeepSeek、Gemini、Azure OpenAI、Azure AI、Ollama、ML Studio、硅基流动、火山引擎、Grok、MirrorStages 等
- Embedding 适配：OpenAI 兼容接口、Azure OpenAI、Ollama、ML Studio、Gemini、硅基流动、MirrorStages 等
- 图片生成：OpenAI / MirrorStages 兼容图片接口
- 向量库：ChromaDB

## 环境要求

本地脚本启动需要：

- Python 3.11 或更高版本，推荐 Python 3.12
- Node.js 18 或更高版本，推荐 Node.js 20
- npm
- 可用的 LLM API Key
- 如需知识库、文风参考库或叙事 DNA 检索，需要配置可用的 Embedding 模型
- 如需图片生成，需要配置图片生成模型

Docker 启动需要：

- Docker
- Docker Compose v2

## 快速启动

### macOS / Linux 一键启动

```bash
git clone <你的仓库地址>
cd Novel-and-Comic-Production-Factory

chmod +x start_api.sh start_web.sh
./start_api.sh
```

启动后访问：

```text
http://localhost:7860
```

`start_api.sh` 会自动完成以下工作：

- 创建 `.venv` 虚拟环境
- 安装或更新 Python 依赖
- 安装前端依赖
- 按需构建 `frontend/dist`
- 初始化 `output/`、`styles/`、`prompts/`、`vectorstore/`、`projects.json`、`xp_presets.json`
- 启动 FastAPI 后端并托管 Vue 前端页面

### 开发模式

```bash
./start_api.sh --dev
```

开发模式会同时启动：

- 后端：`http://127.0.0.1:7860`
- 前端 Vite：`http://127.0.0.1:5173`

开发模式下，前端代理默认连接 `http://localhost:7860`。如果只想修改前端页面端口：

```bash
NOVELWRITER_FRONTEND_PORT=5174 ./start_api.sh --dev
```

如果要修改开发模式后端端口，需要同步调整 `frontend/vite.config.ts` 中的代理目标。

### 跳过前端构建

如果已经构建过前端，可跳过构建检查：

```bash
./start_api.sh --skip-build
```

如需强制重新构建：

```bash
NOVELWRITER_FORCE_BUILD=1 ./start_api.sh
```

### Windows 启动

推荐使用 WSL 或 Git Bash 运行：

```bash
./start_api.sh
```

也可以手动启动：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

cd frontend
npm install
npm run build
cd ..

python -m uvicorn api_server:app --host 127.0.0.1 --port 7860
```

## Docker Compose 部署

```bash
docker compose up -d --build
```

访问：

```text
http://服务器IP:7860
```

查看日志：

```bash
docker compose logs -f
```

停止服务：

```bash
docker compose down
```

修改宿主机端口：

```bash
NOVELWRITER_PORT=18080 docker compose up -d --build
```

Docker Compose 默认持久化方式：

| 容器路径 | 宿主机 / 卷 | 内容 |
| --- | --- | --- |
| `/app/data` | `novelwriter_data` 命名卷 | `config.json`、`projects.json`、`xp_presets.json` |
| `/app/output` | `./output` | 项目输出、章节、漫剧数据、图片记录 |
| `/app/styles` | `./styles` | 文风模板、叙事 DNA、作者参考库索引元数据 |
| `/app/prompts` | `./prompts` | 提示词方案 |
| `/app/vectorstore` | `./vectorstore` | 向量库数据 |

首次启动无需提前创建 `config.json`、`projects.json` 或 `xp_presets.json`。

## 手动 Docker 运行

```bash
docker build -t novel-and-comic-production-factory .

docker run -d \
  --name novel-writer \
  -p 7860:7860 \
  -v novelwriter_data:/app/data \
  -v ./output:/app/output \
  -v ./styles:/app/styles \
  -v ./prompts:/app/prompts \
  -v ./vectorstore:/app/vectorstore \
  novel-and-comic-production-factory
```

## 常用环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `NOVELWRITER_HOST` | `127.0.0.1`，Docker 中为 `0.0.0.0` | 后端监听地址 |
| `NOVELWRITER_PORT` | `7860` | 后端监听端口；Docker Compose 中也控制宿主机映射端口 |
| `NOVELWRITER_FRONTEND_PORT` | `5173` | 开发模式 Vite 前端端口 |
| `NOVELWRITER_PYTHON` | 自动查找 | 指定 Python 可执行文件 |
| `NOVELWRITER_USE_SYSTEM_PYTHON` | `0` | 设为 `1` 时不创建 `.venv`，直接使用系统 Python |
| `NOVELWRITER_SKIP_BUILD` | `0` | 设为 `1` 时跳过前端构建 |
| `NOVELWRITER_FORCE_BUILD` | `0` | 设为 `1` 时强制重新构建前端 |
| `NOVELWRITER_CONFIG_FILE` | `config.json` | 配置文件路径 |
| `NOVELWRITER_PROJECTS_FILE` | `projects.json` | 项目索引文件路径 |
| `NOVELWRITER_XP_PRESETS_FILE` | `xp_presets.json` | XP 预设文件路径 |
| `NOVELWRITER_CORS_ORIGINS` | 本地默认白名单 | 额外 CORS 白名单，多个地址用英文逗号分隔 |
| `NOVELWRITER_API_TOKEN` | 空 | 设置后，除 `/api/health` 外的 API 需要携带 `X-NovelWriter-Token` 或 Bearer Token |
| `NOVELWRITER_SAVE_PROMPT_HISTORY` | `0` | 设为 `1` 时保存提示词历史 |

## 首次使用流程

### 1. 打开模型配置

进入「模型配置」页面，至少配置一个 LLM。建议同时配置：

- LLM 配置：用于小说生成、漫剧脚本、角色卡、场景图、分镜图、创意讨论等文本任务
- Embedding 配置：用于知识库、作者参考库、文风参考检索
- 图片配置：用于图片生成模块和漫剧分镜单图生成

配置保存后，各模块的下拉框会默认选择可用配置。

### 2. 创建或选择项目

顶部项目栏用于创建、激活和切换项目。每个项目会有自己的输出目录，默认位于 `output/` 下。

项目目录中常见文件包括：

- `project_config.json`：项目参数
- `Novel_architecture.txt`：小说架构
- `Novel_directory.txt`：章节目录
- `chapters/` 或章节正文文件：生成的正文
- `manju/`：漫剧制作数据
- `images/`：图片生成结果、提示词队列和生成记录

### 3. 使用创作工坊生成小说

推荐流程：

1. 在「基础参数」中选择 LLM、Embedding、提示词方案、文风和叙事 DNA。
2. 生成小说架构，包括核心种子、世界观、角色、剧情弧。
3. 生成章节目录。
4. 生成详细细纲，可选择精简或详细模式。
5. 逐章生成正文，必要时使用知识库、作者参考库、文风和叙事 DNA。
6. 定稿润色，自动维护前文摘要和角色状态。
7. 使用去 AI 痕迹模块进行单章或批量优化。
8. 使用阅读器查看和编辑最终章节。

### 4. 使用漫剧制作模块

推荐流程：

1. 进入「漫剧制作」，导入小说 TXT。
2. 选择 LLM、章节范围、每章分镜数量、视觉风格和额外约束，并保存设置。
3. 生成漫剧剧本，把小说改编为适合竖屏漫剧的脚本。
4. 生成角色信息和角色卡提示词，角色卡默认生成单张全身角色图提示词。
5. 生成章节场景图提示词，沉淀地点、光影和氛围。
6. 生成章节分镜图提示词，把剧情拆成可执行镜头。
7. 使用提示词增强、连续性检查、队列导入或单镜生图继续制作。
8. 如需修改 AI 指令，进入「指令配置」调整对应模板。

### 5. 使用图片生成模块

1. 在「模型配置」中添加图片配置，支持 `openai` 和 `mirrorstages` provider。
2. 在「图片生成」中输入提示词，或从漫剧模块导入待生成提示词。
3. 生成后会写入生成记录。
4. 待生成提示词和生成记录都可以直接删除，删除操作会同步更新项目内的记录 JSON 文件。

## 模型配置示例

### OpenAI 兼容 LLM

```text
接口格式: OpenAI
Base URL: https://api.openai.com/v1
模型名: gpt-4o-mini
API Key: 你的 API Key
Temperature: 0.7
Max Tokens: 8192
Timeout: 600
```

许多兼容 OpenAI API 的服务也可使用这一格式，只需替换 `Base URL` 和 `模型名`。

### DeepSeek

```text
接口格式: DeepSeek 或 OpenAI
Base URL: https://api.deepseek.com/v1
模型名: deepseek-chat
API Key: 你的 DeepSeek API Key
Temperature: 0.7
Max Tokens: 8192
Timeout: 600
```

### Ollama 本地模型

先安装并拉取模型：

```bash
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

LLM：

```text
接口格式: Ollama
Base URL: http://localhost:11434/v1
模型名: qwen2.5:7b
API Key: ollama
```

Embedding：

```text
接口格式: Ollama
Base URL: http://localhost:11434
模型名: nomic-embed-text
```

### 图片生成配置

OpenAI：

```text
Provider: openai
Base URL: https://api.openai.com/v1
Model: gpt-image-1
Size: 1024x1536
Quality: medium
Output Format: png
```

MirrorStages：

```text
Provider: mirrorstages
Base URL: https://api.mirrorstages.com/openai/v1
Model: gpt-image-2
Size: 1024x1536
Quality: medium
Output Format: png
```

## 项目结构

```text
Novel-and-Comic-Production-Factory/
├── api_server.py                 # FastAPI 后端入口，生产模式托管 Vue dist
├── web_server.py                 # 旧版 Gradio 应用兼容保留，当前主要入口不是它
├── start_api.sh                  # macOS/Linux/WSL 一键启动脚本
├── start_web.sh                  # 兼容旧入口，转发到 start_api.sh
├── Dockerfile                    # 前端构建 + 后端运行的多阶段镜像
├── docker-compose.yml            # Docker Compose 部署配置
├── requirements.txt              # Python 依赖
├── config.example.json           # 配置文件示例
├── config_manager.py             # 配置管理
├── llm_adapters.py               # LLM 适配器
├── embedding_adapters.py         # Embedding 适配器
├── prompt_definitions.py         # 小说创作提示词方案管理
├── default_style_templates.py    # 默认文风模板
├── api/
│   ├── image_service.py          # 图片生成、记录与队列管理
│   ├── manju_instruction_templates.py
│   └── routers/                  # FastAPI 功能路由
├── novel_generator/              # 小说生成、细纲、定稿、去 AI 痕迹、知识库等核心逻辑
├── frontend/
│   └── src/
│       ├── views/                # 页面模块
│       ├── components/           # 通用组件和创作工坊步骤组件
│       ├── stores/               # Pinia 状态
│       └── styles/               # 全局样式
├── prompts/                      # 提示词方案 JSON
├── styles/                       # 文风模板 JSON
├── output/                       # 本地项目输出，运行时生成
└── vectorstore/                  # 向量库数据，运行时生成
```

## 数据与备份

建议备份以下内容：

- `config.json`：模型配置、代理配置、图片配置
- `projects.json`：项目列表和当前激活项目
- `xp_presets.json`：XP 预设
- `output/`：小说、漫剧、图片和项目配置
- `styles/`：文风模板和叙事 DNA
- `prompts/`：自定义提示词方案
- `vectorstore/`：知识库和作者参考库向量数据

Docker Compose 部署时，`config.json`、`projects.json`、`xp_presets.json` 在 `novelwriter_data` 命名卷中。迁移服务器时需要同时迁移该命名卷和宿主机挂载目录。

## 常见问题

### 页面打不开

先确认服务是否启动：

```bash
curl http://127.0.0.1:7860/api/health
```

如果返回 `{"status":"ok","version":"2.0.0"}`，说明后端正常。再检查端口、防火墙、反向代理或 Docker 端口映射。

### 生产模式打开后只有 API，没有前端页面

说明 `frontend/dist` 不存在。执行：

```bash
NOVELWRITER_FORCE_BUILD=1 ./start_api.sh
```

或手动构建：

```bash
cd frontend
npm install
npm run build
cd ..
python -m uvicorn api_server:app --host 127.0.0.1 --port 7860
```

### 生成失败或提示模型配置错误

检查「模型配置」中的：

- API Key 是否填写
- Base URL 是否以正确路径结尾，例如 OpenAI 兼容接口通常是 `/v1`
- 模型名是否存在
- 接口格式是否与服务匹配
- 代理设置是否影响请求

### 知识库或作者参考库不可用

需要先配置可用的 Embedding 模型。若使用 Ollama，需要确保本地 Ollama 服务正在运行，并且已经拉取 Embedding 模型。

### Docker 中配置保存后重启丢失

确认使用的是当前 `docker-compose.yml`，并且存在 `novelwriter_data:/app/data` 卷挂载。不要把单个 `config.json` 文件直接挂载到容器中，否则首次启动时容易出现文件和目录冲突。

### 开启 API Token 后前端请求 401

如果设置了 `NOVELWRITER_API_TOKEN`，浏览器端需要在本地存储中写入同样的 token，键名为：

```text
novelwriter_api_token
```

也可以在自定义前端构建时通过 `VITE_NOVELWRITER_API_TOKEN` 注入。

## 服务器部署建议

Docker Compose 是推荐部署方式。若使用 systemd 直接部署，建议先用脚本完成依赖和前端构建，再让 systemd 启动 Uvicorn：

```ini
[Unit]
Description=Novel and Comic Production Factory
After=network.target

[Service]
Type=simple
WorkingDirectory=/path/to/Novel-and-Comic-Production-Factory
Environment=NOVELWRITER_HOST=127.0.0.1
Environment=NOVELWRITER_PORT=7860
ExecStart=/path/to/Novel-and-Comic-Production-Factory/.venv/bin/python -m uvicorn api_server:app --host 127.0.0.1 --port 7860
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Nginx 反向代理示例：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:7860;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_buffering off;
    }
}
```

## 致谢

部分早期代码参考了 [AI_NovelGenerator](https://github.com/YILING0013/AI_NovelGenerator)。

## License

AGPL-3.0
