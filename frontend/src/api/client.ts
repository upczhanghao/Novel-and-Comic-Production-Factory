import axios from 'axios'
import { useTasksStore } from '@/stores/tasks'
import { useFeedbackStore } from '@/stores/feedback'

function apiToken(): string {
  return localStorage.getItem('novelwriter_api_token') || import.meta.env.VITE_NOVELWRITER_API_TOKEN || ''
}

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = apiToken()
  if (token) config.headers['X-NovelWriter-Token'] = token
  return config
})

// ── 响应拦截器：统一错误处理 ──────────────────────────────────────────────────
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const raw = err.response?.data?.detail ?? err.message ?? '请求失败'
    const msg = Array.isArray(raw) ? raw.map((e: any) => e.msg ?? JSON.stringify(e)).join('; ') : String(raw)
    return Promise.reject(new Error(msg))
  }
)

// ── Projects ─────────────────────────────────────────────────────────────────
export const projectsApi = {
  list: () => api.get('/projects'),
  create: (name: string, filepath = '') => api.post('/projects', { name, filepath }),
  activate: (name: string) => api.post(`/projects/${encodeURIComponent(name)}/activate`),
  update: (name: string, data: Record<string, unknown>) =>
    api.put(`/projects/${encodeURIComponent(name)}`, data),
  delete: (name: string) => api.delete(`/projects/${encodeURIComponent(name)}`),
  active: () => api.get('/projects/active'),
  discover: () => api.post('/projects/discover'),
}

// ── Config ───────────────────────────────────────────────────────────────────
export const configApi = {
  health: () => api.get('/config/health'),
  recommendedTemplates: () => api.get('/config/recommended-templates'),
  listLLM: () => api.get('/config/llm'),
  saveLLM: (data: Record<string, unknown>) => api.post('/config/llm', data),
  deleteLLM: (name: string) => api.delete(`/config/llm/${encodeURIComponent(name)}`),
  listEmbedding: () => api.get('/config/embedding'),
  saveEmbedding: (data: Record<string, unknown>) => api.post('/config/embedding', data),
  deleteEmbedding: (name: string) =>
    api.delete(`/config/embedding/${encodeURIComponent(name)}`),
  listImage: () => api.get('/config/image'),
  saveImage: (data: Record<string, unknown>) => api.post('/config/image', data),
  deleteImage: (name: string) => api.delete(`/config/image/${encodeURIComponent(name)}`),
  testLLM: () => `/config/llm/test`,
  testEmbedding: () => `/config/embedding/test`,
  testImage: () => `/config/image/test`,
  setLLMDefault: (slot: string, configName: string) =>
    api.put('/config/llm/default', { slot, config_name: configName }),
  setEmbeddingDefault: (configName: string) =>
    api.put('/config/embedding/default', { config_name: configName }),
  setImageDefault: (configName: string) =>
    api.put('/config/image/default', { config_name: configName }),
  getProxy: () => api.get('/config/proxy'),
  saveProxy: (data: { proxy_url: string; proxy_port: string; enabled: boolean }) =>
    api.put('/config/proxy', data),
  getUserProfile: () => api.get('/config/user_profile'),
  saveUserProfile: (profile: string, enabled = true) => api.put('/config/user_profile', { profile, enabled }),
  extractPreferences: (text: string, llm_config_name: string) =>
    api.post('/config/user_profile/extract', { text, llm_config_name }),
  appendProfile: (preferences: string) =>
    api.post('/config/user_profile/append', { preferences }),
  listManjuInstructions: () => api.get('/config/instructions/manju'),
  saveManjuInstruction: (key: string, content: string) =>
    api.put(`/config/instructions/manju/${encodeURIComponent(key)}`, { content }),
  resetManjuInstruction: (key: string) =>
    api.post(`/config/instructions/manju/${encodeURIComponent(key)}/reset`),
  getDefaultStyle: () => api.get('/config/default-style'),
  saveDefaultStyle: (data: Record<string, string>) => api.put('/config/default-style', data),
}

// ── Presets ──────────────────────────────────────────────────────────────────
export const presetsApi = {
  list: () => api.get('/presets'),
  activate: (name: string) => api.post(`/presets/${encodeURIComponent(name)}/activate`),
  save: (name: string, description = '') => api.post('/presets', { name, description }),
  delete: (name: string) => api.delete(`/presets/${encodeURIComponent(name)}`),
  getPrompts: () => api.get('/presets/prompts'),
  updatePrompt: (key: string, content: string) =>
    api.put(`/presets/prompts/${encodeURIComponent(key)}`, { content }),
  resetPrompt: (key: string) =>
    api.post(`/presets/prompts/${encodeURIComponent(key)}/reset`),
}

// ── Generate (SSE) ────────────────────────────────────────────────────────────

export interface SSEHandle {
  abort: () => void
}

/**
 * 创建一个 EventSource 连接到 SSE 端点（POST via fetch）。
 * 同步返回 SSEHandle，可通过 abort() 取消操作。
 */
export function postSSE(
  url: string,
  body: Record<string, unknown>,
  onProgress: (msg: string, value?: number, content?: string) => void,
  onResult: (content: string) => void,
  onError: (msg: string) => void,
  onDone: () => void,
): SSEHandle {
  const controller = new AbortController()
  let operationId = ''

  const handle: SSEHandle = {
    abort: () => {
      // 通知后端取消
      if (operationId) {
        fetch('/api/generate/cancel', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(apiToken() ? { 'X-NovelWriter-Token': apiToken() } : {}),
          },
          body: JSON.stringify({ operation_id: operationId }),
        }).catch(() => {})
      }
      controller.abort()
    },
  }

  // 异步处理 SSE 流（fire-and-forget）
  ;(async () => {
    try {
      const res = await fetch(`/api${url}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(apiToken() ? { 'X-NovelWriter-Token': apiToken() } : {}),
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        onError(err.detail ?? res.statusText)
        onDone()
        return
      }

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      const parse = (raw: string) => {
        const lines = raw.split('\n')
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const json = line.slice(6).trim()
          if (!json) continue
          try {
            const event = JSON.parse(json)
            if (event.type === 'started') operationId = event.operation_id ?? ''
            else if (event.type === 'progress') onProgress(event.message ?? '', event.value, event.content)
            else if (event.type === 'result') onResult(event.content ?? '')
            else if (event.type === 'error') onError(event.message ?? '未知错误')
            else if (event.type === 'done') onDone()
          } catch {
            // ignore malformed event
          }
        }
      }

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() ?? ''
        for (const part of parts) parse(part + '\n\n')
      }
      if (buffer) parse(buffer)
    } catch (e: unknown) {
      // AbortError is normal when user cancels
      if (e instanceof DOMException && e.name === 'AbortError') {
        onDone()
      } else {
        onError((e as Error).message ?? '请求失败')
        onDone()
      }
    }
  })()

  return handle
}

/**
 * 在 postSSE 之上自动接入全局 TaskBar 与 FeedbackCenter。
 * 调用方仍可继续传 onProgress / onResult / onError / onDone 做自己的本地处理。
 */
export function postSSETracked(
  url: string,
  body: Record<string, unknown>,
  opts: {
    taskId: string
    taskLabel: string
    onProgress?: (msg: string, value?: number, content?: string) => void
    onResult?: (content: string) => void
    onError?: (msg: string) => void
    onDone?: () => void
    silentError?: boolean
  },
): SSEHandle {
  // M26: 直接使用 store（stores 不 import client，无循环依赖）。Pinia 未初始化时降级为 undefined。
  let tasksMod: ReturnType<typeof useTasksStore> | undefined
  let fbMod: ReturnType<typeof useFeedbackStore> | undefined
  try {
    tasksMod = useTasksStore()
    fbMod = useFeedbackStore()
  } catch {
    // pinia 尚未挂载（罕见边界）；继续以无 store 模式工作
  }
  let handle: SSEHandle | null = null
  const abort = () => handle?.abort()
  const task = tasksMod?.register(opts.taskId, opts.taskLabel, abort)

  handle = postSSE(
    url,
    body,
    (msg, value, content) => {
      if (task && tasksMod) tasksMod.update(opts.taskId, msg, value)
      opts.onProgress?.(msg, value, content)
    },
    (content) => { opts.onResult?.(content) },
    (msg) => {
      tasksMod?.finish(opts.taskId, 'error')
      if (!opts.silentError) fbMod?.error(`${opts.taskLabel} 失败`, msg)
      opts.onError?.(msg)
    },
    () => {
      if (task && task.status === 'running') {
        tasksMod?.finish(opts.taskId, 'done')
      }
      opts.onDone?.()
    },
  )
  return handle!
}

export const generateApi = {
  architecture: (body: Record<string, unknown>) => `/generate/architecture`,
  blueprint: (body: Record<string, unknown>) => `/generate/blueprint`,
  chapter: (body: Record<string, unknown>) => `/generate/chapter`,
  finalize: (body: Record<string, unknown>) => `/generate/finalize`,
  expand: (body: Record<string, unknown>) => `/generate/expand`,
  status: (filepath: string) => api.get(`/generate/status`, { params: { filepath } }),
  chapters: (filepath: string) => api.get(`/generate/chapters`, { params: { filepath } }),
  getChapter: (num: number, filepath: string) =>
    api.get(`/generate/chapter/${num}`, { params: { filepath } }),
  saveChapter: (num: number, content: string, filepath: string) =>
    api.put(`/generate/chapter/${num}`, { content }, { params: { filepath } }),
  saveArchitecture: (content: string, filepath: string) =>
    api.put(`/generate/architecture`, { content, filepath }),
  saveComponent: (component: string, content: string, filepath: string) =>
    api.put(`/generate/architecture/component/${component}`, { content, filepath }),
  saveBlueprint: (content: string, filepath: string) =>
    api.put(`/generate/blueprint`, { content, filepath }),
  saveCharacterDynamics: (content: string, filepath: string) =>
    api.put(`/generate/character_dynamics`, { content, filepath }),
  exportNovel: (filepath: string) =>
    api.get(`/generate/export`, { params: { filepath }, responseType: 'blob' }),
  partialSteps: (filepath: string) =>
    api.get(`/generate/architecture/partial`, { params: { filepath } }),
  assembleArch: (body: Record<string, unknown>) =>
    api.post(`/generate/architecture/assemble`, body),
  continueArch: (body: Record<string, unknown>) => `/generate/architecture/continue`,
  contStepSeed: () => `/generate/architecture/continue/step/seed`,
  contStepWorld: () => `/generate/architecture/continue/step/world`,
  continueStepCharacters: () => `/generate/architecture/continue/step/characters`,
  continueStepArcs: () => `/generate/architecture/continue/step/arcs`,
  continueStepCharState: () => `/generate/architecture/continue/step/char_state`,
  assembleContinuation: (body: Record<string, unknown>) =>
    api.post(`/generate/architecture/continue/assemble`, body),
  compressContext: (body: { llm_config_name: string; filepath: string; include_world_building?: boolean }) =>
    api.post(`/generate/compress-context`, body, { timeout: 600000 }),
  humanize: () => `/generate/humanize`,
  batchHumanize: () => `/generate/humanize/batch`,
  reviseStep: () => `/generate/architecture/step/revise`,
  detailedOutline: () => `/generate/detailed_outline`,
  getDetailedOutline: (filepath: string) =>
    api.get(`/generate/detailed_outline`, { params: { filepath } }),
  saveDetailedOutline: (content: string, filepath: string) =>
    api.put(`/generate/detailed_outline`, { content, filepath }),
  stepCoreSeed: () => `/generate/architecture/step/core_seed`,
  stepCharacters: () => `/generate/architecture/step/characters`,
  stepWorld: () => `/generate/architecture/step/world`,
  stepPlot: () => `/generate/architecture/step/plot`,
}

// ── XP Presets ───────────────────────────────────────────────────────────────
export const xpPresetsApi = {
  list: () => api.get('/xp-presets'),
  create: (name: string, content: string) => api.post('/xp-presets', { name, content }),
  update: (name: string, data: { name?: string; content?: string }) =>
    api.put(`/xp-presets/${encodeURIComponent(name)}`, data),
  delete: (name: string) => api.delete(`/xp-presets/${encodeURIComponent(name)}`),
}

// ── Styles ───────────────────────────────────────────────────────────────────
export const stylesApi = {
  list: () => api.get('/styles'),
  get: (name: string) => api.get(`/styles/${encodeURIComponent(name)}`),
  save: (name: string, data: Record<string, unknown>) =>
    api.put(`/styles/${encodeURIComponent(name)}`, data),
  delete: (name: string) => api.delete(`/styles/${encodeURIComponent(name)}`),
  rollbackCalibration: (name: string) =>
    api.post(`/styles/${encodeURIComponent(name)}/rollback-calibration`),
  analyzeUrl: () => `/styles/analyze`,
  analyzeDNAUrl: () => `/styles/analyze-dna`,
  mergeUrl: () => `/styles/merge`,
  calibrateUrl: () => `/styles/calibrate`,
  calibrateNarrativeUrl: () => `/styles/calibrate-narrative`,
  importAuthorRef: (name: string, formData: FormData) =>
    api.post(`/styles/${encodeURIComponent(name)}/author-reference/import`, formData, {
      headers: { 'Content-Type': undefined },
    }),
  clearAuthorRef: (name: string) =>
    api.delete(`/styles/${encodeURIComponent(name)}/author-reference`),
  authorRefStatus: (name: string) =>
    api.get(`/styles/${encodeURIComponent(name)}/author-reference/status`),
  authorRefFiles: (name: string) =>
    api.get(`/styles/${encodeURIComponent(name)}/author-reference/files`),
  authorRefStats: (name: string, emb_config_name = '') =>
    api.get(`/styles/${encodeURIComponent(name)}/author-reference/stats`, {
      params: { emb_config_name },
    }),
  deleteAuthorRefFile: (name: string, fileId: string, emb_config_name = '') =>
    api.delete(`/styles/${encodeURIComponent(name)}/author-reference/files/${encodeURIComponent(fileId)}`, {
      params: { emb_config_name },
    }),
  updateAuthorRefFile: (name: string, fileId: string, data: { filename?: string; tags?: string[]; author?: string }) =>
    api.put(`/styles/${encodeURIComponent(name)}/author-reference/files/${encodeURIComponent(fileId)}`, data),
  replaceAuthorRefFile: (name: string, fileId: string, formData: FormData) =>
    api.post(`/styles/${encodeURIComponent(name)}/author-reference/files/${encodeURIComponent(fileId)}/replace`, formData, {
      headers: { 'Content-Type': undefined },
    }),
  searchAuthorRef: (name: string, query: string, emb_config_name = '', k = 6, file_id?: string) =>
    api.get(`/styles/${encodeURIComponent(name)}/author-reference/search`, {
      params: { query, emb_config_name, k, ...(file_id ? { file_id } : {}) },
    }),
  authorRefSource: (name: string, fileId: string) =>
    api.get(`/styles/${encodeURIComponent(name)}/author-reference/files/${encodeURIComponent(fileId)}/source`),
  rebuildAuthorRef: (name: string, emb_config_name = '') =>
    api.post(`/styles/${encodeURIComponent(name)}/author-reference/rebuild`, { emb_config_name }, { timeout: 300000 }),
}

// ── Knowledge ─────────────────────────────────────────────────────────────────
export const knowledgeApi = {
  import: (formData: FormData) =>
    api.post('/knowledge/import', formData, {
      headers: { 'Content-Type': undefined },
    }),
  clear: (filepath: string) =>
    api.delete('/knowledge', { params: { filepath } }),
  files: (filepath: string) => api.get('/knowledge/files', { params: { filepath } }),
  stats: (filepath: string, emb_config_name = '') =>
    api.get('/knowledge/stats', { params: { filepath, emb_config_name } }),
  deleteFile: (fileId: string, filepath: string, emb_config_name = '') =>
    api.delete(`/knowledge/files/${encodeURIComponent(fileId)}`, {
      params: { filepath, emb_config_name },
    }),
  updateFile: (fileId: string, filepath: string, data: { filename?: string; tags?: string[]; author?: string }) =>
    api.put(`/knowledge/files/${encodeURIComponent(fileId)}`, data, { params: { filepath } }),
  replaceFile: (fileId: string, formData: FormData) =>
    api.post(`/knowledge/files/${encodeURIComponent(fileId)}/replace`, formData, {
      headers: { 'Content-Type': undefined },
    }),
  search: (filepath: string, query: string, emb_config_name = '', k = 6, file_id?: string) =>
    api.get('/knowledge/search', {
      params: { filepath, query, emb_config_name, k, ...(file_id ? { file_id } : {}) },
    }),
  source: (fileId: string, filepath: string) =>
    api.get(`/knowledge/files/${encodeURIComponent(fileId)}/source`, { params: { filepath } }),
  rebuild: (filepath: string, emb_config_name = '') =>
    api.post('/knowledge/rebuild', { filepath, emb_config_name }, { timeout: 300000 }),
}

// ── Files ────────────────────────────────────────────────────────────────────
export const filesApi = {
  list: (filepath: string) => api.get('/files', { params: { filepath } }),
  tree: (filepath: string) => api.get('/files/tree', { params: { filepath } }),
  recent: (filepath: string, limit = 20) =>
    api.get('/files/recent', { params: { filepath, limit } }),
  content: (filepath: string, path: string) =>
    api.get('/files/content', { params: { filepath, path } }),
  write: (filepath: string, path: string, content: string) =>
    api.put('/files/content', { filepath, path, content }),
  deleteItem: (filepath: string, path: string) =>
    api.delete('/files/item', { params: { filepath, path } }),
  batchDelete: (filepath: string, paths: string[]) =>
    api.post('/files/batch-delete', { filepath, paths }),
  search: (filepath: string, query: string, caseSensitive = false, limit = 200) =>
    api.get('/files/search', { params: { filepath, query, case_sensitive: caseSensitive, limit } }),
  downloadUrl: (filepath: string, path: string) =>
    `/api/files/download?filepath=${encodeURIComponent(filepath)}&path=${encodeURIComponent(path)}`,
  archive: (filepath: string, paths?: string[]) =>
    api.post('/files/archive', { filepath, paths: paths ?? null }, { responseType: 'blob', timeout: 300000 }),
}

// ── Logs ─────────────────────────────────────────────────────────────────────
export const logsApi = {
  get: (tail = 200) => api.get('/logs', { params: { tail } }),
  clear: () => api.delete('/logs'),
  getPrompts: (tail = 50, search = '') =>
    api.get('/logs/prompts', { params: { tail, search } }),
  clearPrompts: () => api.delete('/logs/prompts'),
}

// ── Consistency ───────────────────────────────────────────────────────────────
export const consistencyApi = {
  checkUrl: () => `/consistency/check`,
}

// ── Images ──────────────────────────────────────────────────────────────────
export const imagesApi = {
  generate: (body: Record<string, unknown>) => api.post('/images/generate', body, { timeout: 300000 }),
  list: (filepath: string) => api.get('/images/list', { params: { filepath } }),
  prompts: (filepath: string) => api.get('/images/prompts', { params: { filepath } }),
  importPrompts: (body: Record<string, unknown>) => api.post('/images/prompts/import', body),
  deletePrompt: (id: string, filepath: string) =>
    api.delete(`/images/prompts/${encodeURIComponent(id)}`, { params: { filepath } }),
  deleteRecord: (id: string, filepath: string, deleteFile = true) =>
    api.delete(`/images/records/${encodeURIComponent(id)}`, { params: { filepath, delete_file: deleteFile } }),
  batchDeleteRecords: (ids: string[], filepath: string, deleteFile = true) =>
    api.post('/images/records/batch-delete', { ids, filepath, delete_file: deleteFile }),
  batchDeletePrompts: (ids: string[], filepath: string) =>
    api.post('/images/prompts/batch-delete', { ids, filepath }),
}

// ── Brainstorm ───────────────────────────────────────────────────────────────
export const brainstormApi = {
  chatUrl: () => `/brainstorm/chat`,
}

// ── 漫剧制作 ─────────────────────────────────────────────────────────────────
export const manjuApi = {
  importNovel: (formData: FormData) =>
    api.post('/manju/import', formData, {
      headers: { 'Content-Type': undefined },
      timeout: 120000,
    }),
  status: (filepath: string) => api.get('/manju/status', { params: { filepath } }),
  saveSettings: (body: Record<string, unknown>) => api.put('/manju/settings', body),
  saveCharacters: (body: Record<string, unknown>) => api.put('/manju/characters/structured', body),
  saveStoryboards: (body: Record<string, unknown>) => api.put('/manju/storyboards/structured', body),
  regenerateShot: (body: Record<string, unknown>) => api.post('/manju/storyboards/regenerate-shot', body, { timeout: 180000 }),
  saveStyle: (body: Record<string, unknown>) => api.post('/manju/styles', body),
  generateImage: (body: Record<string, unknown>) => api.post('/manju/images/generate', body, { timeout: 300000 }),
  enhancePrompts: (body: Record<string, unknown>) => api.post('/manju/prompts/enhance', body, { timeout: 180000 }),
  continuityCheck: (filepath: string) => api.get('/manju/continuity-check', { params: { filepath } }),
  stats: (filepath: string) => api.get('/manju/stats', { params: { filepath } }),
  createQueue: (body: Record<string, unknown>) => api.post('/manju/queue', body),
  updateQueue: (batchId: string, filepath: string, status: string) =>
    api.put(`/manju/queue/${encodeURIComponent(batchId)}`, null, { params: { filepath, status } }),
  exportUrl: (kind: string, format: string, filepath: string) =>
    `/api/manju/export?kind=${encodeURIComponent(kind)}&format=${encodeURIComponent(format)}&filepath=${encodeURIComponent(filepath)}`,
  exportContentUrl: (kind: string, format: string, filepath: string) =>
    `/api/manju/export-content?kind=${encodeURIComponent(kind)}&format=${encodeURIComponent(format)}&filepath=${encodeURIComponent(filepath)}`,
  importImagePrompts: (body: Record<string, unknown>) => api.post('/manju/image-prompts/import', body),
  scriptUrl: () => `/manju/script`,
  scriptExportUrl: (filepath: string) => `/api/manju/script/export?filepath=${encodeURIComponent(filepath)}`,
  charactersUrl: () => `/manju/characters`,
  scenesUrl: () => `/manju/scenes`,
  storyboardsUrl: () => `/manju/storyboards`,
  // A5: 历史快照
  historyList: (filepath: string, kind: string) =>
    api.get('/manju/history', { params: { filepath, kind } }),
  historyCreate: (filepath: string, body: { kind: string; label?: string; payload: unknown }) =>
    api.post('/manju/history', body, { params: { filepath } }),
  historyDelete: (filepath: string, kind: string, ts: number) =>
    api.delete(`/manju/history/${encodeURIComponent(kind)}/${ts}`, { params: { filepath } }),
  historyClear: (filepath: string, kind: string) =>
    api.delete(`/manju/history/${encodeURIComponent(kind)}`, { params: { filepath } }),
}

// ── Security (rate limits) ───────────────────────────────────────────────────
export const securityApi = {
  getRateLimits: () => api.get('/security/rate-limits'),
  updateRateLimits: (data: Record<string, unknown>) => api.put('/security/rate-limits', data),
}
