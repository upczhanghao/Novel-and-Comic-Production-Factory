# Changelog

本项目所有显著变更记录于此。
格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

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
