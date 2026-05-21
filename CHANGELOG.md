# Changelog

本项目所有显著变更记录于此。
格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [2.4.2] - 2026-05-22

### Performance — 后端性能优化（5 项）

经过对 FastAPI 后端的同步 I/O / 扫描 / 向量库生命周期的系统审计，落地了以下不破坏 API 兼容的性能修复：

- **SSE 线程池容量 4 → 16**（`api/sse_utils.py:15`）。所有 LLM 生成 / Embedding 测试 / 图片测试共用同一个 `ThreadPoolExecutor`，原值导致超过 4 个并发请求就开始排队。提到 16 后单机并发能力翻 4 倍，对单用户桌面级使用绰绰有余。
- **prompt history 改尾读**（`api/routers/logs.py`）。原实现用 `deque(f, maxlen=N)` 按行遍历整个 jsonl 文件，文件膨胀到几十 MB 就会前端超时；新实现 `_tail_lines()` 用 `seek + read` 反向截取末尾字节窗口，无搜索时只读末尾 256 KB，有搜索时上限 8 MB。50 MB 文件实测：无搜索 37 ms，关键字搜索 1.4 s（旧版 5–15 s）。
- **Chroma 向量库进程级缓存**（`novel_generator/vectorstore_utils.py` + `api/library_service.py`）。原实现每个章节生成 / 知识库检索都重新构造 `Chroma(...)`，sqlite 打开 + collection 加载约 100 ms。新增 `_store_cache: dict[(abs_dir, collection_name)] -> Chroma` 进程级字典，连续 N 章生成只加载一次。`clear_vector_store` / `clear_library` / `rebuild_library` 通过 `_invalidate_store_cache` / `_evict_store` 显式失效。
- **Embedding adapter 缓存**：审计中确认 `embedding_adapters.py:298-349` 已实现，无需新增。
- **`_save_projects` 原子写**：审计中确认已使用 `atomic_write_json`（tmp + rename），无需新增。

### Changed — 文件管理脱离项目耦合

`/files` 路由原本要求先激活项目才能打开，与「运行日志」「模型配置」等系统级模块的体验不一致。本版改为真正全局：

- 后端 9 个 `/api/files*` 端点改用新增的 `resolve_files_root()`（`api/security.py`），filepath 为空时回落到工作区 `output/` 目录，`safe_join` 仍保留路径穿越防护。
- 前端 `/files` 路由 meta 加 `requiresProject: false`，不再被项目守卫拦截。无项目时树第一层就是 `output/` 下的各项目目录，可直接进入查看。

### UI Polish — 浅色侧边栏可读性修复

v2.2.0 暗色 → 浅色侧边栏迁移留下的若干视觉回退一并修掉：

- `.mode-toggle` / `.sidebar-search` / `ConfigHealthIndicator` 按钮在浅色背景上原本几乎看不到边框，统一改为白底 `#d4d4d8` 边框 + hover `--color-leather-light` + 焦点环。
- `ProjectBar` 把「📁 路径 · 已同步 · 更新 X 分钟前」从 pb-main 内联挤压改为下方独立行，宽度变化时不再被「新建/发现/删除」按钮遮挡。
- `studio-workspace` / `studio-content` 加 `overflow-x: hidden` + 子容器 `min-width: 0`，消除窄窗口下页面右侧需要横向滚动才能看到的问题。

### Files
- 后端：`api/sse_utils.py`、`api/routers/logs.py`、`api/routers/files.py`、`api/security.py`、`api/library_service.py`、`novel_generator/vectorstore_utils.py`、`api_server.py`（version bump）
- 前端：`frontend/src/router/index.ts`、`frontend/src/App.vue`、`frontend/src/components/ProjectBar.vue`、`frontend/src/components/ConfigHealthIndicator.vue`、`frontend/src/styles/main.css`

---

## [2.4.1] - 2026-05-21

### Fixed — `config.example.json` 与 `create_config()` 默认值同步

**问题**：v2.1.0 之后多轮变更（S14 模型名修正、F1 image 参数从 `size`/`quality` 切到 `aspect_ratio`/`resolution`、`create_config()` 默认值重排）累积下来，`config.example.json` 已经与运行时实际生成的默认 `config.json` 漂移：
- `gpt-5.4-mini-2026-03-17` 假模型名（S14 仅修了 templates.ts，漏了示例文件）
- `embedding_configs` 下空字符串 key 的垃圾条目（一旦被 `cp` 成 config.json 会污染下拉菜单）
- `gpt-image-2` 错字（应为 `gpt-image-1`）
- `image_configs` 仍用 F1 之前的 `size`/`quality`，与新 schema 不一致
- `choose_configs` 引用的 `"DeepSeek"` 在自身 `llm_configs` 里不存在，是悬空引用

**改动**：
- **`config.example.json`** 重写为 `config_manager.create_config()` 默认值的镜像：4 个 LLM（DeepSeek V3 / GPT 5 / MirrorStages-LLM / Gemini 2.5 Pro）+ 1 embedding（OpenAI）+ 2 image_configs（OpenAI-Images / MirrorStages-Images），补齐 `last_interface_format` 与 `webdav_config` 顶层段。API Key 字段使用 `YOUR_*_API_KEY` 占位符（运行时默认仍为 `""`），便于阅读但不会被误当成真实配置。
- **`config_manager.py:create_config()`** image_configs 默认值同步改 F1 schema：`aspect_ratio: "9:16"` + `resolution: "1080p"`，不再写 `size`/`quality`。运行时行为不变（`api/image_service.py:normalize_image_config` 兼容旧 schema），但全新安装直接落新字段，不再走 `infer_aspect_resolution()` 反推路径。

### Notes — 部署文件审计

同步审计了 v2.1.0 之后的所有 deployment 文件，结论是 **无需改动**：
- `start_api.sh` / `start_web.sh`：`ensure_runtime_files()` 已正确仅 seed `projects.json` + `xp_presets.json`（`config.json` 由 Python 端 `load_config()` → `create_config()` 在缺失时自动生成）；`output / styles / prompts / vectorstore` 已建。
- `Dockerfile` / `docker-compose.yml`：`/app/data` 命名卷 + 4 个 bind mount 已覆盖所有 v2.4.0 持久化路径（含 v2.3.0 漫剧 history 落在 `output/<project>/manju/history/`）。CMD 中 `{ ... }` 块 + `exec uvicorn` 修复（v2.1.0）保留。
- **新服务器部署不需要 `cp config.example.json config.json`** —— `README.md:170` 已正确写明「首次启动无需提前创建 config.json / projects.json / xp_presets.json」。`config.example.json` 在仓库中除 `README.md:353` 项目结构图外没有任何脚本引用，仅作文档参考。

### Files
- 主要修改：`config.example.json`、`config_manager.py`

## [2.4.0] - 2026-05-21

### Improved — F2 全局按钮响应式反馈

**问题**：项目里 341 个 `<button>`，多数只有 hover 色变，没有 `:active` 按下动效，也没有 `:focus-visible` 键盘焦点环；async 按钮（保存 / 删除 / 测试）点击后到 toast 弹出之间的几百毫秒里没有任何视觉反馈，用户容易重复点击。

**改动**：

**Layer 1 — 全局 CSS 兜底**（`frontend/src/styles/main.css`）：
- 所有 `<button>` + `a[class*="px-*"]` 加 120ms 颜色 / 边框 / transform 过渡；按下时 `transform: translateY(1px) scale(0.985)` 给即时按压感
- `:focus-visible` 加 3px 蓝色焦点环（仅键盘聚焦时显示，鼠标点击不会出现）
- `[data-busy="true"]` / `[aria-busy="true"]` 自动覆盖一个旋转 spinner（700ms 一圈），文字变透明，事件被锁住 — 任何按钮加上这个属性即可获得 loading 态
- `[data-flash="ok"]` / `[data-flash="err"]` 触发 800ms 一次的脉冲光晕，绿 / 红表示成功 / 失败
- `prefers-reduced-motion: reduce` 时所有动效降级为无过渡

**Layer 2 — `useAsyncAction` 组合式 + `<AsyncButton>` 组件**：
- `useAsyncAction()` 把一段 async 函数包成 `{ busy, flash, run }`，调用期间 busy=true、结束后 flash 显示 ok/err 一次脉冲，自动防双击
- `<AsyncButton :action="fn">` 是即开即用的封装：自动绑定 data-busy / data-flash，附带 4 种 variant（默认 / primary / ghost / danger）和 3 种 size
- 也可以手动给现有按钮加 `:data-busy="busyRef" :data-flash="flashRef"`，复用同一套 CSS

**Layer 3 — 关键路径接入**：
- `ImageConfigPanel.vue` / `LLMConfigPanel.vue` / `EmbeddingConfigPanel.vue`：保存 / 删除按钮接入 `useAsyncAction`，保存成功后绿脉冲，失败红脉冲；测试按钮在 SSE 期间显示 spinner（之前只是改文字）
- `ProjectBar.vue`：发现 / 删除 / 创建项目按钮加 `:data-busy`，长扫描操作可看到 spinner

未受影响的 300+ 个按钮自动获得 Layer 1 的兜底效果（按下动画 + 焦点环）。"Fire-and-forget" 但已有标签切换的按钮（`'保存中...'` / `'生成中...'`）保留原 UX，因为文字反馈比 spinner 更具体。

### Files
- 新增：`frontend/src/composables/useAsyncAction.ts`、`frontend/src/components/AsyncButton.vue`
- 主要修改：`frontend/src/styles/main.css`、`frontend/src/components/config/{Image,LLM,Embedding}ConfigPanel.vue`、`frontend/src/components/ProjectBar.vue`

### Changed — F1 图片参数：比例 + 分辨率档位 取代裸 size/quality

**问题**：原图片配置面板让用户手填 `size`（如 `1024x1536`）+ 选 `quality`（low/medium/high），有两个痛点：
1. 用户不知道 OpenAI gpt-image-1 只接受三档离散 size（`1024x1024 / 1024x1536 / 1536x1024`），输入 `1080x1920` 会直接 502
2. `quality` 与 `size` 之间没有显式的语义联系，用户不清楚高分辨率是否一定要 high quality

**改动**：
- **新增 `api/image_params.py`** — 把「比例 + 分辨率档位」派生为 provider 实际接受的 `size + quality`：
  - 7 档比例：`1:1 / 9:16 / 16:9 / 4:3 / 3:4 / 3:2 / 2:3`
  - 5 档分辨率：`480p / 720p / 1080p / 2k / 4k`
  - OpenAI / Mirrorstages（同样兼容 OpenAI Images Generations API，参考 https://www.mirrorstages.com/docs/api/images-generations.html）→ 比例向最近的离散 size 对齐，档位映射到 quality（480p/720p→low, 1080p→medium, 2k/4k→high）
  - dall-e-3 → quality 退化为 standard / hd
- **`normalize_image_config`** 同时持久化 `aspect_ratio` / `resolution` 与派生的 `size` / `quality`（向后兼容）：旧配置无新字段时由 `infer_aspect_resolution()` 自动反推
- **schemas** `ImageConfigCreate` / `TestImageConfigRequest` 新增 `aspect_ratio` + `resolution` 字段，移除前端必填
- **`/config/image/test`** 端点改为接收新参数，旧 `size/quality` 仍可由 `normalize_image_config` 兼容回填
- **前端 `ImageConfigPanel.vue`** UI 重做：两个下拉（图片比例 / 分辨率档位）+ 实时「实际请求参数」预览胶囊（橙色高亮，显示派生出的 size + quality），用户编辑参数时即时反馈
- **推荐模板** `api/data/recommended_templates.json` + `frontend/src/components/config/templates.ts` 改用新字段
- **schemas 清理**：移除 M14 已废弃的 `ManjuImageConfigRequest`（自 PUT /manju/image-config 端点移除后即为死代码）

### Files
- 新增：`api/image_params.py`
- 主要修改：`api/image_service.py`、`api/schemas.py`、`api/routers/config.py`、`api/data/recommended_templates.json`、`frontend/src/components/config/ImageConfigPanel.vue`、`frontend/src/composables/useConfigValidation.ts`、`frontend/src/components/config/templates.ts`

## [2.3.0] - 2026-05-21

### Refactored — A 系列架构级第二轮（A3–A8 拆分/合并）

本轮完成 v2.2.0 推迟的 6 项高风险架构改造。分三个独立 commit 落地：

**Round 1 — A3 后端拆分**
- **A3 拆分 `api/routers/manju.py`**（1772 行 → 5 模块包）：
  - `manju/parser.py`（392）：TXT 解码 / 章节解析 / 结构化 I/O / 路径辅助
  - `manju/prompts.py`（167）：图像 prompt 构建 / 视觉风格 / 角色卡
  - `manju/pipeline.py`（474）：剧本改编 SSE / LLM 适配
  - `manju/export.py`（286）：导出文件名 / 附件头 / 章节重新可导入归一化
  - `manju/images.py`（241）：图片记录管理 / URL 附加
  - `manju/routes.py`（571）：22 个 `@router` 端点 + `_sse_response`
  - `__init__.py` 仅 `from .routes import router` 重新导出，调用方零改动

**Round 2 — A7+A8 前端去重**
- **A7 抽 `useLibrary(adapter)` 组合式**：KnowledgeView 与 StylesView 的作者参考库共享同一套库管理逻辑（load / import / delete / search / rebuild / clear / source preview）。两个 view 各自提供 `computed<LibraryAdapter>`（knowledge 按 filepath；author-ref 按 styleName），自动随作用域切换。模板与 CSS 各自保留。
- **A8 抽 `usePromptTemplateEditor(opts)` + `extractVariables` / `highlightVariables`**：PresetsView 与 InstructionConfigView 共享变量分析、HTML 高亮、编辑器状态（selectedKey / editorContent / hasChanges / save / reset / copy / applyDefault）。`classPrefix` 选项同时支持 `pv-var` 与 `ic-var ok|unknown` 两套样式。

**Round 3 — A6+A4+A5 数据流与持久化**
- **A6 合并 `xp_presets` 进 ProfileView**：ProfileView 增加「命名片段」tab，承接全部 CRUD；`GlobalParamsCard` 简化为只读多选 + 「管理片段 →」跳转 `/profile?tab=snippets`。后端 `xp_presets.json` 保持不变，从 UX 层消除「XP 预设」与 PresetsView「提示词方案」的命名冲突。
- **A4 漫剧分镜图走 images.py 派发**：`/manju/images/generate` 改用 `images_dir(filepath)`（原 `_work_dir + group_by_project=False`），分镜图与人物卡图统一存入 `<project>/images/<project>/`，自动出现在 ImageView 的 RecordsTab，不再丢失到 `manju/images/` 死角。
- **A5 `useManjuHistory` 服务端持久化**：新增 `api/routers/manju/history.py`（4 个端点：list/create/delete/clear），快照写入 `manju/history/{kind}.json`，每 kind 上限 20 条。前端 `useManjuHistory.ts` 重写为异步 API，调用方接口不变（`snapshot/list/get/remove/clear`）。替换 localStorage 后单浏览器配额受限的问题，且支持多设备同步与备份。

### Files

新增：
- `api/routers/manju/{parser,prompts,pipeline,export,images,history,routes}.py`、`api/routers/manju/__init__.py`
- `frontend/src/composables/useLibrary.ts`、`frontend/src/composables/usePromptTemplateEditor.ts`

删除：
- `api/routers/manju.py`（拆分为包）

主要修改：
- `frontend/src/views/{Knowledge,Styles,Presets,InstructionConfig,Profile}View.vue`
- `frontend/src/components/workshop/GlobalParamsCard.vue`
- `frontend/src/composables/useManjuHistory.ts`
- `frontend/src/api/client.ts`

## [2.2.0] - 2026-05-21

### Improved — A 审计打磨（A 系列架构级第一轮）

本轮处理 A 系列中低风险的 8 项；高风险的 5 项（A3 拆 manju.py / A4 漫剧分镜统一图像流 / A5 漫剧历史服务端持久化 / A6 合并 xp_presets 进 ProfileView / A7+A8 抽 LibraryManager+PromptTemplateEditor 去重）改期 v2.3.0。

- **A1 ChapterStep 加载已有章节入口**：新增「已有章节」下拉，调用 `GET /generate/chapters` 列出全部已保存章节（草稿 / 终稿），点击直接载入；保存后自动刷新列表。原「📂 加载」按钮仍保留。
- **A2 useChapterCursor 统一章节游标**：新增 `composables/useChapterCursor.ts`，把 `chapterNum / savedChapterNum / outlineBatchStart / humanizerStart/End` 收到单一来源；`setCursor(num)` 同时把 humanizer 范围拉到当前章。`loadChapter` 与 chapterNum watch 自动调用，消除「ChapterStep 选第 5 章但 HumanizerStep 还停留在 1-1」式的多源不同步。
- **A9 服务端 /config/health + 顶栏指示器**：新增 `GET /config/health` 端点（聚合 LLM/Embedding/Image 三类配置健康度），新增 `<ConfigHealthIndicator>` 60 秒轮询 + 红/黄/绿点；点击弹出每组状态详情和「前往」配置页链接。替代散落各 view 的 banner。
- **A10 推荐模板服务端 manifest**：把 8 个推荐配置从前端硬编码搬到 `api/data/recommended_templates.json`，新增 `GET /config/recommended-templates` 端点；前端 `templates.ts` 改用 `useRecommendedTemplates()` 组合式（共享缓存 + 网络失败兜底为 `FALLBACK_TEMPLATES`）。模型名更新不再需要重发布前端。
- **A11 路由项目守卫**：`router.beforeEach` 强制检查 active project；未选择时跳转 `/no-project` 占位页（列出已有项目 / 提供新建表单），跳转后保留 `?to=` 自动跳回。`/config /presets /instructions /styles /knowledge /profile /logs /no-project` 标记 `requiresProject: false` 不受守卫约束。
- **A12 build-time 禁用 alert/confirm**：新增 `frontend/scripts/check-no-blocking-dialogs.mjs`，扫描 .vue/.ts 文件中除 `stores/confirm.ts` 与 `ConfirmDialog.vue` 外的 `alert()`/`confirm()` 调用，违例时构建失败。捕获并修复了 `GlobalParamsCard.vue` 残留的 2 处 `alert()`，改为 `feedback.error()`。
- **A13 命令面板**（前序 M26 已交付，本轮归档）：`<CommandPalette>` 已上线，⌘K / Ctrl+K 唤起。
- **A14 路由 meta 单一数据源**：路由 meta 增加 `NavMeta` 接口（title / icon / group / level / hidden / bottomNav / requiresProject），`App.vue` 与 `CommandPalette.vue` 全部从 `navRoutes` 派生导航与命令列表，消除两份 14 项的硬编码数组。

### Files
- 新增：`frontend/src/composables/useChapterCursor.ts`、`frontend/src/components/ConfigHealthIndicator.vue`、`frontend/src/views/NoProjectView.vue`、`frontend/scripts/check-no-blocking-dialogs.mjs`、`api/data/recommended_templates.json`
- 主要修改：`frontend/src/router/index.ts`、`frontend/src/App.vue`、`frontend/src/components/CommandPalette.vue`、`frontend/src/components/workshop/ChapterStep.vue`、`frontend/src/composables/useWorkshopState.ts`、`frontend/src/components/config/templates.ts`、`frontend/src/components/config/RecommendedTemplates.vue`、`frontend/src/components/workshop/GlobalParamsCard.vue`、`frontend/src/api/client.ts`、`api/routers/config.py`、`frontend/package.json`

## [2.1.3] - 2026-05-21

### Improved — P1 审计打磨（M1–M35 中等摩擦点修复）

**Workshop（M2/M4/M5）**
- M2: StyleSelector 增加「应用到全部步骤 / 单独配置」开关；关闭后切换文风只写入当前步骤，不再静默覆盖架构/蓝图层
- M4: StreamOutput 新增 `userDirty` 状态，「未保存」徽标只在用户编辑了生成结果后出现，避免误报
- M5: useWorkshopState 扩展 JSON 解析失败时把异常详情写入 `state.error` 并保留原始返回，不再静默吞错

**Manju / Image（M8–M15）**
- M8: ManjuView 12 处 `dataMsg.value = '✅/❌…'` 改用 `feedback.success/error`，统一通知中心
- M9: 漫剧状态加载失败显式弹错（含错误信息），不再 swallow
- M10: 拆分 `canRunScript` / `canRunDownstream`，"AI 改写台本"按钮在无图片配置时仍可运行
- M11: 批量生图遇 429 自动指数退避重试 3 次（1s/2s/4s），并在确认对话框中提示
- M12: 一致性检查直接使用入库的 `prompt_positive` 评估质量标记，避免重新构建提示词导致的偏移
- M13: 图片批量删除请求改为 `ImageBatchDeleteRequest` Pydantic 模型，单次最多 500 条
- M14: 移除已弃用的 `PUT /manju/image-config` 端点和对应前端 client 方法
- M15: 漫剧各阶段（剧本改编 / 角色 / 场景 / 分镜）SSE 运行中显示「停止」按钮，调用 `AbortController`

**Config（M16/M20/M21/M23/M24/M25）**
- M16: StylesView 加载文风详情改为 `Promise.all` 并发，消除 N+1 串行等待
- M20: ConfigView 应用推荐模板前，若表单已编辑则弹确认对话框
- M21: StylesView "设为全局默认" 改为红框警告按钮 + 二次确认（含影响范围说明）
- M23: InstructionConfigView「返回漫剧」按钮仅当 `document.referrer` 来自 /manju 时显示
- M24: 图片配置「测试连接」改用表单中实际的 `size/quality`，不再强行降级为 1024x1024/low
- M25: OnboardingWizard 第 1 步明确列出 LLM（必需）/ Embedding（可选）/ 图片（可选）三类配置及跳过后果

**Shell（M26–M35）**
- M26: 移除 `window.__nwFeedback`/`__nwTasks` 桥接；`api/client.ts` 直接 `import` 两个 store（已确认无循环依赖），HMR 后不再丢失反馈
- M27: 新增 `stores/confirm.ts` + `<ConfirmDialog />` 组件；全项目 29 处 `confirm()` 替换为 Promise 风格 `confirmDialog()`
- M28: `bottomLinks` 根据 `ui.isBeginner` 动态派生（新手 3 项 / 高级 4 项）
- M29: 移动端 topbar 搜索按钮改为放大镜图标（`AppIcon` 新增 `search`）
- M30: OnboardingWizard "进入工作台" 按钮 disabled 时旁边显示「还需：xxx」徽标
- M31: 删除从未引用的 `composables/useAutoSelect.ts`（53 行死代码）
- M32: feedback store 加入 5 秒内同文消息聚合（显示 `×N` 计数）；FeedbackCenter 新增「清除全部」按钮
- M33: generate store 新增 `invalidateForPath(path)`；FilesView 保存被追踪的 `Novel_architecture.txt` 等文件后自动刷新生成缓存
- M34: LogsView `detectModule` 优先解析 `[logger.name]` 格式，中文日志不再全部归为 system
- M35: LogsView 错误提示中的「模型配置」改为可点击按钮，`router.push('/config')`

### Deferred — 架构级问题
以下 P1 项涉及更大范围的重构或数据迁移，未在本次打磨内解决，待后续 A 类（架构）专项处理：
- M17: StylesView 1060 行 author reference 面板拆分
- M18: PresetsView 与 InstructionConfigView 模板编辑代码重叠
- M19: `xp_presets/` 与 `prompts/` 命名冲突 — 需数据迁移
- M22: ProfileView 与 xp_presets 数据模型耦合

## [2.1.2] - 2026-05-21

### Polish — P2 审计打磨 (28 项轻量优化)

**Workshop (L1–L9)**
- L1: StyleSelector 收起后可再次展开（按钮文案动态切换）
- L2: 草稿恢复横幅时间格式支持「N 天前 / 具体日期」，不再把 2 天前显示成 "1 小时前"
- L3: StyleSelector 空状态中的「文风与DNA」变为真实路由链接
- L4: 切换项目 toast 文案改为「已切换到…正在加载内容」，反映实际异步过程
- L5: 一致性检查进度信息前缀显示章节号
- L6: PreflightCheck 同时检查 `generateStore` 中已加载的架构/蓝图内容，刷新后不误报
- L7: `doGenerateArch` 设置 `startedAt`/`endedAt`，ResultSummary 显示耗时
- L8: BatchGenerate 描述去掉错误的「步骤3」指代，改为「上方所选」
- L9: 细纲批次按钮在全部章节已生成时显示「✓ 全部章节细纲已生成」而非破损的「N+1 - N 章」

**Manju (L10–L16)**
- L10: 移除与 ManjuSteps 重复的 pipelineSteps 旧栅格
- L11: PromptTemplatePreview 标签更准确，说明花括号占位符由 AI 填充
- L12: ContinuityIssues 新增 `hasRun` prop，空态可区分「未运行」与「无问题」
- L13: 经 S18 的 keep-alive 项目 key 修复后，切换到 /images 再返回保留分镜表单状态
- L14: ImageView 标签页（队列 / 记录）持久化到 localStorage
- L15: ManjuSteps「导出」步骤的完成态接受 `hasExport` prop，分镜表生成后默认显示已就绪
- L16: importMsg/settingsMsg 颜色判定从 `startsWith('✅')` 改为 `startsWith('❌')`，后端中性消息不再误判为红色

**Config (L17–L22)**
- L17: LLM/Embedding/Image 配置面板的健康状态徽标加 tooltip 说明仅保存在本地浏览器
- L18: StylesView 概念说明三栏移入可折叠 `<details>`，默认收起减少首屏视觉负担
- L19: PresetsView 重置/删除 confirm 提示语补充「此操作不可撤销」
- L20: Base URL 末尾 `/` 警告文案改为「通常不需要，系统会自动拼接路径」（不再暗示路径拼接错误）
- L21: `get_style` 读取扩展 JSON 字段时增加 try/except，文件损坏时不影响主响应
- L22: RecommendedTemplates 模板卡片加 `aria-label`，屏幕阅读器可读

**Shell (L23–L28)**
- L23: 路由列表三处重复属架构级整改（A14），不在 P2 范围内
- L24: 抽取 `tasks.clearFinished()` 方法替代 TaskBar 内联闭包
- L25: 移动端 FeedbackCenter 底部偏移从 90px 提升到 140px，避开 TaskBar + 底部导航
- L26: FilesView 内部 refs 抽 composable 属代码组织级，不在 P2 范围内
- L27: FilesView 副标题补充「仅显示 .txt / .json / .md 文件」说明白名单
- L28: LogsView Prompt 历史顶部加灰色说明「整个工作区，不按项目隔离」

---

## [2.1.1] - 2026-05-21

### Fixed — P0 审计修复 (22 项关键工作流/数据丢失问题)

**Workshop (S1–S6)**
- S1: 批量生成完成后不再自动导出，改为用户勾选 opt-in
- S2: SSE 取消时正确重置 `running` 状态，防止 UI 卡死
- S3: 保存章节时锁定目标章号，避免生成中途切换导致覆盖错误章节
- S4: 新增「加载章节」按钮，可回看已生成章节内容
- S5: Ctrl+S 快捷键适配当前步骤（章节/蓝图/架构组件），不再调用已废弃的 `saveArchitecture`
- S6: 续写面板添加 `id="continue-anchor"`，`goto()` 导航可正确定位并展开 `<details>`

**Manju/Image (S7–S13)**
- S7: 漫剧生图结果持久化到 `image_records`，刷新后不丢失
- S8: 分镜表内联预览/重新生成组件 `ShotImageInline`
- S9: 批量生图支持 `shot_ids` 过滤，可只重新生成选中分镜
- S10: 分镜图片点击可在新窗口预览大图
- S11: 导出区域添加 `id="manju-export"` 锚点
- S12: `regenerateShot` 添加 try/catch + feedback.error 错误提示
- S13: 图片配置选择器内联到分镜操作列

**Config (S14–S17)**
- S14: OpenAI 模板模型 ID 修正 `gpt-5.4-mini` → `gpt-4.1-mini`
- S15: 应用模板时完整重置表单（`{ ...empty(), ...v }`），不再残留旧字段
- S16: `extract_user_preferences` 失败时返回结构化错误而非 500
- S17: `set_default_style` 使用 Pydantic schema 校验，拒绝非法字段

**Shell (S18–S22)**
- S18: `<component :key>` 绑定 `activeProject`，切换项目时清除 keep-alive 缓存
- S19: 引导向导「前往配置」使用 `router.push` 替代失效的 `<a href>`
- S20: 切换/删除项目时清空 generate store 缓存（懒导入避免循环依赖）
- S21: 新增 `hasActiveProject` computed，供组件统一判断项目就绪
- S22: LogsView prompt 接口从裸 `axios` 迁移到 `logsApi` 客户端封装

---

## [2.1.0] - 2026-05-21

### Added — 项目浏览器
- 后端 `api/routers/files.py` 新增多端点：`/files/tree` 嵌套目录树、`/files/recent` 按修改时间排序、`/files/content` (GET/PUT) 内联读写、`/files/item` (DELETE) 与 `/files/batch-delete` 移动到回收站、`/files/search` 全文检索、`/files/download` 与 `/files/archive` 单文件 / zip 流式下载。
- 前端 `views/FilesView.vue` 重写为「结构树 / 最近修改 / 全文搜索」三栏；支持编辑、删除、批量下载、单文件预览。
- 新增递归组件 `components/FileTreeNode.vue`，替换原内联 `defineComponent` + render 函数写法，消除 TS7022/7024/2528 报错。

### Added — 阅读器增强
- `views/ReaderView.vue` 重写：章节列表 / 标题目录 (TOC) / 全文搜索三个侧边栏。
- 支持单章与全部章节两种阅读模式；全文搜索使用 6 并发批量抓取，每章限 5 处命中。
- 键盘快捷键：`←` / `→` 或 `K` / `J` 切换章节，`+` / `-` 调整字号，`/` 聚焦搜索；字号持久化到 localStorage。
- 新增章节复制按钮。

### Added — 日志面板增强
- `views/LogsView.vue` 重写：日志按 `时间戳 / 级别 / 模块 / 消息 / 栈追踪` 结构化解析。
- 支持按级别 (成功 / 警告 / 错误)、模块、关键字过滤。
- 错误栈一键复制；`deriveHint()` 将常见技术错误映射为用户可操作的提示。
- Prompt 历史新增状态筛选 (`done` / `error` / `pending`)。

### Added — 工坊 / 漫剧 / 图像 / 配置 / 知识库 UX 改进
- 新增组件：`CommandPalette`、`FeedbackCenter`、`OnboardingWizard`、`TaskBar`。
- 工坊：`WorkshopStepper` 分步引导、`CarryForward` 跨步带料、`DraftRestoreBanner` 草稿恢复、`PreflightCheck` 启动前检查、`QuickRevise` 快速修订、`ResultSummary` 结果汇总、`StyleSelector` 风格选择、`InputExamples` 示例。
- 配置视图拆分为 `LLMConfigPanel` / `EmbeddingConfigPanel` / `ImageConfigPanel` / `ProxyConfigPanel` / `RecommendedTemplates` 子面板。
- 图像：`PromptEditor`、`PromptBreakdown`、`QueueTab`、`RecordsTab`、`RecordCard`、`ImageErrorBanner`。
- 漫剧：`BatchToolbar`、`ContinuityIssues`、`EnhanceDiff`、`ManjuSteps`、`PromptTemplatePreview`、`ShotImageInline`、`VersionHistory`。
- 新增 composables：`useAutoSelect`、`useConfigHealth`、`useConfigValidation`、`useDraftAutosave`、`useImageError`、`useImageFilters`、`useManjuHistory`、`useUndoStack`。
- 新增 store：`feedback`、`tasks`、`ui`。
- 后端新增 `api/library_helpers.py` + `api/library_service.py` 知识库服务层；`api/routers/knowledge.py` / `config.py` / `styles.py` / `images.py` 端点扩展；`prompt_definitions.py` 增补漫剧与图像 prompt 模板。

### Changed — 项目识别
- `web_server.discover_projects` 现在不只识别 `Novel_architecture.txt`，还识别含 `manju/`、`images/`、`project_config.json` 的目录。
- 扫描时跳过 `trash` / `images` / `__pycache__`。
- 将原本歧义的返回三元表达式改写为显式 `if/else`，消除空列表 vs. 项目数据混淆。

### Fixed
- `FilesView.loadContent`：当文件来自搜索结果而不在 `files.value` 中时，构造一个最小 `FileEntry` 以保留工具栏。
- `FilesView.batchDownload`：`URL.revokeObjectURL` 延迟 5s 触发，避免 Safari 提前撤销 Blob URL。
- `FileTreeNode.vue`：使用 `withDefaults` 处理 `depth` 默认值，移除多余的 `defineProps`/`defineEmits` 导入。

### Deployment
- `Dockerfile` CMD 修复优先级 bug：当 `projects.json` 与 `xp_presets.json` 中只有一个存在时，`&&`/`||` 链会短路跳过 uvicorn 启动；现用 `{ ... }` 包裹每段初始化，逻辑独立。
- `Dockerfile` CMD 改为 `exec uvicorn ...`，让 uvicorn 接管 PID 1，容器停止时 SIGTERM 直达进程。
- `.dockerignore` 增补 `server.log`，避免本地大日志被复制进镜像构建上下文。

### Repo hygiene
- 重写 `.gitignore`，从版本控制中移除 `__pycache__/`、`*.pyc`、`frontend/dist/`、`output/`、`app.log`、`server.log`、`prompt_history.jsonl`、`projects.json`、`.DS_Store`。
- 这些文件在运行时按需生成；前端构建产物由 Dockerfile 多阶段构建或 `npm run build` 生成。

---

## [2.0.0] - 早期版本

- 从 Gradio 迁移到 FastAPI + Vue 3 架构。
- 引入项目、风格、预设、知识库、图像、漫剧、日志等模块。
- 见 `git log` 获取早期历史。
