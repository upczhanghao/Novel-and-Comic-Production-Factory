<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { logsApi } from '@/api/client'
import { useFeedbackStore } from '@/stores/feedback'
import axios from 'axios'

const feedback = useFeedbackStore()

type Tab = 'logs' | 'prompts'
const activeTab = ref<Tab>('logs')

// ── 运行日志 ──────────────────────────────────────────────────────────────────
interface LogEntry {
  raw: string
  timestamp: string
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL' | 'OTHER'
  module: string
  message: string
  stack: string[]
  hint: string
}

const logRaw = ref('')
const logTailLines = ref(500)
const logLoading = ref(false)

const filterLevel = ref<'all' | 'success' | 'error' | 'warning'>('all')
const filterModule = ref('all')
const filterKeyword = ref('')

// Heuristic: map technical error → user-actionable hint.
function deriveHint(text: string): string {
  const t = text.toLowerCase()
  if (t.includes('connection refused') || t.includes('connectionerror') || t.includes('econnrefused'))
    return '连接被拒绝：检查模型 API 地址是否正确，或本地服务是否已启动。'
  if (t.includes('timeout') || t.includes('timed out'))
    return '请求超时：可在「模型配置」增大 timeout，或检查代理网络是否畅通。'
  if (t.includes('proxy') || t.includes('proxyerror') || t.includes('failed to connect to proxy'))
    return '代理错误：在「模型配置 → 代理设置」中检查代理地址 / 端口，或暂时禁用代理重试。'
  if (t.includes('401') || t.includes('unauthorized') || t.includes('invalid api key') || t.includes('incorrect api key'))
    return 'API Key 无效：请在「模型配置」重新填写正确的 API Key 并测试连通性。'
  if (t.includes('403') || t.includes('forbidden'))
    return '权限被拒：检查 API Key 的可用区域/项目，或后端 NovelWriter Token 是否匹配。'
  if (t.includes('429') || t.includes('rate limit') || t.includes('quota'))
    return '调用频率/额度超限：稍后重试，或降低并发数（参数面板中的「批量并发数」）。'
  if (t.includes('5') && (t.includes('500') || t.includes('502') || t.includes('503') || t.includes('504')))
    return '模型服务端错误：稍候重试；如持续出现，切换到备用模型配置。'
  if (t.includes('json') && (t.includes('decode') || t.includes('parse')))
    return '模型返回的 JSON 解析失败：尝试在 Prompt 中加入「严格 JSON 输出」指令，或降低模型温度。'
  if (t.includes('out of memory') || t.includes('cuda') || t.includes('oom'))
    return '显存/内存不足：减小批量并发或一次生成的章节数。'
  if (t.includes('chroma') || t.includes('vector_store') || t.includes('embedding'))
    return '向量库错误：尝试在「知识库 / 作者参考库」点击「重建索引」。'
  if (t.includes('file not found') || t.includes('no such file') || t.includes('errno 2'))
    return '文件缺失：确认项目目录是否正确；可在「文件管理」核对生成产物是否齐全。'
  if (t.includes('permission denied') || t.includes('errno 13'))
    return '没有写入权限：检查项目目录权限或换一个可写路径。'
  if (t.includes('disk') && t.includes('full'))
    return '磁盘空间不足：清理 trash 目录或删除旧项目。'
  if (t.includes('unicode') || t.includes('codec'))
    return '编码错误：确认上传文件为 UTF-8；如来自 Word，请先另存为纯文本。'
  return ''
}

function detectModule(line: string): string {
  // Heuristic: look for "module:xxx" or known prefixes
  const m = line.match(/\b(novel_generator|knowledge|manju|images|brainstorm|config|generate|styles|consistency|projects)\b/i)
  if (m) return m[1].toLowerCase()
  return 'system'
}

const parsedLogs = computed<LogEntry[]>(() => {
  if (!logRaw.value) return []
  const lines = logRaw.value.split('\n')
  const entries: LogEntry[] = []
  // Standard line: YYYY-MM-DD HH:MM:SS LEVEL message
  const headRe = /^(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})\s+(?:\[?(DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL)\]?)?\s*(.*)$/
  let current: LogEntry | null = null
  for (const line of lines) {
    const m = line.match(headRe)
    if (m) {
      if (current) entries.push(current)
      const lvlRaw = (m[2] || 'INFO').toUpperCase()
      const lvl = (lvlRaw === 'WARN' ? 'WARNING' : lvlRaw) as LogEntry['level']
      const msg = m[3] || ''
      current = {
        raw: line,
        timestamp: m[1],
        level: ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].includes(lvl) ? lvl : 'OTHER',
        module: detectModule(msg),
        message: msg,
        stack: [],
        hint: '',
      }
    } else if (current) {
      // continuation (e.g. traceback)
      current.stack.push(line)
    } else if (line.trim()) {
      entries.push({
        raw: line,
        timestamp: '',
        level: 'OTHER',
        module: detectModule(line),
        message: line,
        stack: [],
        hint: '',
      })
    }
  }
  if (current) entries.push(current)
  // Derive hint from message + stack
  for (const e of entries) {
    if (e.level === 'ERROR' || e.level === 'CRITICAL' || e.stack.some((s) => /traceback|error/i.test(s))) {
      const full = [e.message, ...e.stack].join('\n')
      e.hint = deriveHint(full)
    }
  }
  return entries
})

const modules = computed(() => {
  const set = new Set<string>()
  for (const e of parsedLogs.value) set.add(e.module)
  return ['all', ...Array.from(set).sort()]
})

const filteredLogs = computed(() => {
  const kw = filterKeyword.value.trim().toLowerCase()
  return parsedLogs.value.filter((e) => {
    if (filterModule.value !== 'all' && e.module !== filterModule.value) return false
    if (filterLevel.value === 'error' && !(e.level === 'ERROR' || e.level === 'CRITICAL')) return false
    if (filterLevel.value === 'warning' && e.level !== 'WARNING') return false
    if (filterLevel.value === 'success' && (e.level === 'ERROR' || e.level === 'CRITICAL' || e.level === 'WARNING')) return false
    if (kw && !(e.message.toLowerCase().includes(kw) || e.stack.some((l) => l.toLowerCase().includes(kw)))) return false
    return true
  })
})

const logCounts = computed(() => {
  let err = 0
  let warn = 0
  let ok = 0
  for (const e of parsedLogs.value) {
    if (e.level === 'ERROR' || e.level === 'CRITICAL') err++
    else if (e.level === 'WARNING') warn++
    else ok++
  }
  return { err, warn, ok }
})

async function loadLogs() {
  logLoading.value = true
  try {
    const res = await logsApi.get(logTailLines.value)
    logRaw.value = res.data.content || ''
  } catch (e: unknown) {
    logRaw.value = `❌ ${(e as Error).message}`
  } finally {
    logLoading.value = false
  }
}

async function clearLogs() {
  if (!confirm('确认清空运行日志？')) return
  try {
    await logsApi.clear()
    logRaw.value = ''
    feedback.success('✅ 已清空运行日志')
  } catch (e: unknown) {
    feedback.error('清空失败', (e as Error).message)
  }
}

async function copyEntry(e: LogEntry) {
  const text = [e.raw, ...e.stack].join('\n')
  try {
    await navigator.clipboard.writeText(text)
    feedback.success('✅ 已复制错误堆栈')
  } catch {
    feedback.warning('剪贴板不可用')
  }
}

async function copyAll() {
  try {
    await navigator.clipboard.writeText(logRaw.value)
    feedback.success('✅ 已复制完整日志')
  } catch {
    feedback.warning('剪贴板不可用')
  }
}

// ── Prompt 历史 ───────────────────────────────────────────────────────────────
interface PromptRecord {
  timestamp: string
  model: string
  prompt: string
  response: string
  prompt_len: number
  response_len: number
  reasoning?: string
  reasoning_len?: number
  status?: string
  elapsed?: number
}

const promptRecords = ref<PromptRecord[]>([])
const promptTotal = ref(0)
const promptTail = ref(50)
const promptSearch = ref('')
const promptStatusFilter = ref<'all' | 'done' | 'error' | 'pending'>('all')
const promptLoading = ref(false)
const expandedIndex = ref<Set<number>>(new Set())
const expandedReasoning = ref<Set<number>>(new Set())
const expandedResponse = ref<Set<number>>(new Set())

async function loadPrompts() {
  promptLoading.value = true
  try {
    const res = await axios.get('/api/logs/prompts', {
      params: { tail: promptTail.value, search: promptSearch.value },
    })
    promptRecords.value = res.data.records
    promptTotal.value = res.data.total
    expandedIndex.value = new Set()
    expandedReasoning.value = new Set()
    expandedResponse.value = new Set()
  } catch {
    promptRecords.value = []
  } finally {
    promptLoading.value = false
  }
}

async function clearPrompts() {
  if (!confirm('确认清空所有 Prompt 历史？')) return
  try {
    await axios.delete('/api/logs/prompts')
    promptRecords.value = []
    promptTotal.value = 0
  } catch { /* ignore */ }
}

const filteredPrompts = computed(() => {
  if (promptStatusFilter.value === 'all') return promptRecords.value
  return promptRecords.value.filter((r) => (r.status || 'done') === promptStatusFilter.value)
})

function togglePrompt(i: number) {
  if (expandedIndex.value.has(i)) expandedIndex.value.delete(i)
  else expandedIndex.value.add(i)
}
function toggleReasoning(i: number) {
  if (expandedReasoning.value.has(i)) expandedReasoning.value.delete(i)
  else expandedReasoning.value.add(i)
}
function toggleResponse(i: number) {
  if (expandedResponse.value.has(i)) expandedResponse.value.delete(i)
  else expandedResponse.value.add(i)
}
function isPromptExpanded(i: number) { return expandedIndex.value.has(i) }
function isReasoningExpanded(i: number) { return expandedReasoning.value.has(i) }
function isResponseExpanded(i: number) { return expandedResponse.value.has(i) }

const copiedIndex = ref<number | null>(null)
async function copyText(text: string, i: number) {
  try {
    await navigator.clipboard.writeText(text)
    copiedIndex.value = i
    setTimeout(() => { copiedIndex.value = null }, 1500)
  } catch { /* ignore */ }
}

function preview(text: string, len = 200) {
  return text.length > len ? text.slice(0, len) + '…' : text
}
function fmtLen(n: number) {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : `${n}`
}

function levelBadge(level: LogEntry['level']) {
  switch (level) {
    case 'ERROR':
    case 'CRITICAL': return 'bg-red-100 text-red-700 border-red-200'
    case 'WARNING': return 'bg-yellow-100 text-yellow-700 border-yellow-200'
    case 'DEBUG': return 'bg-gray-100 text-gray-600 border-gray-200'
    default: return 'bg-emerald-50 text-emerald-700 border-emerald-200'
  }
}

onMounted(() => {
  loadLogs()
  loadPrompts()
})
</script>

<template>
  <div class="module-page space-y-4">
    <h2 class="text-2xl font-bold" style="color: var(--color-ink)">📜 日志</h2>

    <div class="module-toolbar">
      <div>
        <div class="module-kicker">Diagnostics</div>
        <div class="module-subtitle">运行日志支持级别/模块筛选与"下一步建议"；Prompt 历史可按状态过滤。</div>
      </div>
      <div class="studio-segment">
        <button
          v-for="tab in [{ key: 'logs', label: '运行日志' }, { key: 'prompts', label: 'Prompt 历史' }]"
          :key="tab.key"
          @click="activeTab = tab.key as Tab"
          class="px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px"
          :class="activeTab === tab.key ? 'border-[var(--color-leather)] text-[var(--color-leather)]' : 'border-transparent text-[var(--color-ink-light)] hover:text-[var(--color-ink)]'"
          type="button"
        >
          {{ tab.label }}
          <span v-if="tab.key === 'prompts' && promptTotal > 0"
            class="ml-1 px-1.5 py-0.5 rounded-full text-xs font-normal"
            style="background-color: var(--color-parchment-dark); color: var(--color-ink-light)">{{ promptTotal }}</span>
        </button>
      </div>
    </div>

    <!-- ── 运行日志 ──────────────────────────────────────────────────────────── -->
    <div v-if="activeTab === 'logs'" class="space-y-3">
      <div class="module-action-row flex-wrap">
        <label class="text-sm text-[var(--color-ink-light)]">最后</label>
        <input v-model.number="logTailLines" type="number" min="50" max="5000"
          class="w-20 border border-[var(--color-parchment-darker)] rounded-md px-2 py-1 text-sm" />
        <label class="text-sm text-[var(--color-ink-light)]">行</label>

        <label class="text-sm text-[var(--color-ink-light)] ml-2">状态</label>
        <select v-model="filterLevel" class="border border-[var(--color-parchment-darker)] rounded-md px-2 py-1 text-sm">
          <option value="all">全部</option>
          <option value="success">仅成功</option>
          <option value="warning">仅警告</option>
          <option value="error">仅错误</option>
        </select>

        <label class="text-sm text-[var(--color-ink-light)] ml-2">模块</label>
        <select v-model="filterModule" class="border border-[var(--color-parchment-darker)] rounded-md px-2 py-1 text-sm">
          <option v-for="m in modules" :key="m" :value="m">{{ m === 'all' ? '全部模块' : m }}</option>
        </select>

        <input v-model="filterKeyword" placeholder="关键词过滤…"
          class="flex-1 min-w-32 border border-[var(--color-parchment-darker)] rounded-md px-2 py-1 text-sm" />

        <button @click="loadLogs" :disabled="logLoading"
          class="border border-[var(--color-parchment-darker)] rounded-md px-3 py-1.5 text-sm hover:bg-[var(--color-parchment)] disabled:opacity-50" type="button">🔄 刷新</button>
        <button @click="copyAll"
          class="border border-[var(--color-parchment-darker)] rounded-md px-3 py-1.5 text-sm hover:bg-[var(--color-parchment)]" type="button">📋 复制全部</button>
        <button @click="clearLogs"
          class="border border-red-200 text-red-600 rounded-md px-3 py-1.5 text-sm hover:bg-red-50" type="button">清空</button>
      </div>

      <div class="text-xs text-[var(--color-ink-light)]">
        共 {{ parsedLogs.length }} 条 ·
        <span class="text-emerald-700">成功 {{ logCounts.ok }}</span> ·
        <span class="text-yellow-700">警告 {{ logCounts.warn }}</span> ·
        <span class="text-red-700">错误 {{ logCounts.err }}</span>
        · 当前显示 {{ filteredLogs.length }}
      </div>

      <div v-if="logLoading" class="text-sm italic text-[var(--color-ink-light)] py-6 text-center">加载中…</div>
      <div v-else-if="!parsedLogs.length" class="text-sm italic text-[var(--color-ink-light)] py-6 text-center">日志为空</div>
      <div v-else class="space-y-1.5" style="max-height: calc(100vh - 280px); overflow-y: auto;">
        <div v-for="(e, i) in filteredLogs" :key="i"
          class="lg-entry"
          :class="{ 'lg-err': e.level === 'ERROR' || e.level === 'CRITICAL', 'lg-warn': e.level === 'WARNING' }">
          <div class="lg-head">
            <span class="lg-time" v-if="e.timestamp">{{ e.timestamp }}</span>
            <span class="lg-level" :class="levelBadge(e.level)">{{ e.level }}</span>
            <span class="lg-mod">{{ e.module }}</span>
            <span class="lg-msg">{{ e.message }}</span>
            <button v-if="e.stack.length" @click="copyEntry(e)" class="lg-copy" type="button" title="复制错误堆栈">📋 堆栈</button>
          </div>
          <pre v-if="e.stack.length" class="lg-stack">{{ e.stack.join('\n') }}</pre>
          <div v-if="e.hint" class="lg-hint">💡 下一步：{{ e.hint }}</div>
        </div>
      </div>
    </div>

    <!-- ── Prompt 历史 ───────────────────────────────────────────────────────── -->
    <div v-if="activeTab === 'prompts'" class="space-y-3">
      <div class="module-action-row flex-wrap">
        <input v-model="promptSearch" @keyup.enter="loadPrompts"
          placeholder="搜索 prompt/response 关键词…"
          class="flex-1 min-w-48 border border-[var(--color-parchment-darker)] rounded-md px-3 py-1.5 text-sm" />
        <label class="text-sm text-[var(--color-ink-light)]">状态</label>
        <select v-model="promptStatusFilter" class="border border-[var(--color-parchment-darker)] rounded-md px-2 py-1 text-sm">
          <option value="all">全部</option>
          <option value="done">成功</option>
          <option value="error">失败</option>
          <option value="pending">进行中</option>
        </select>
        <label class="text-sm text-[var(--color-ink-light)]">最新</label>
        <input v-model.number="promptTail" type="number" min="5" max="500"
          class="w-16 border border-[var(--color-parchment-darker)] rounded-md px-2 py-1 text-sm" />
        <button @click="loadPrompts" :disabled="promptLoading"
          class="border border-[var(--color-parchment-darker)] rounded-md px-3 py-1.5 text-sm hover:bg-[var(--color-parchment)] disabled:opacity-50" type="button">🔄 刷新</button>
        <button @click="clearPrompts"
          class="border border-red-200 text-red-600 rounded-md px-3 py-1.5 text-sm hover:bg-red-50" type="button">清空</button>
      </div>

      <p v-if="!promptLoading" class="text-xs text-[var(--color-ink-light)]">
        共 {{ promptTotal }} 条，当前 {{ filteredPrompts.length }}
        <span v-if="promptSearch">（已过滤）</span>
      </p>

      <div v-if="promptLoading" class="text-sm text-[var(--color-ink-light)] italic py-8 text-center">加载中…</div>

      <div v-else-if="filteredPrompts.length === 0" class="module-panel p-12 text-center">
        <p class="text-[var(--color-ink-light)] text-sm">
          {{ promptSearch || promptStatusFilter !== 'all' ? '未找到匹配记录' : '暂无 Prompt 历史。生成内容后，记录将在此显示。' }}
        </p>
      </div>

      <div v-else class="space-y-3">
        <div v-for="(record, i) in filteredPrompts" :key="i" class="module-panel overflow-hidden">
          <div class="flex items-center gap-3 px-4 py-3 cursor-pointer select-none hover:bg-[var(--color-parchment)]"
            style="background-color: var(--color-parchment)" @click="togglePrompt(i)">
            <span class="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold"
              style="background-color: var(--color-gold-dark); color: var(--color-parchment)">
              {{ filteredPrompts.length - i }}
            </span>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-xs font-medium" style="color: var(--color-leather)">{{ record.timestamp }}</span>
                <span v-if="record.model" class="px-2 py-0.5 rounded text-xs"
                  style="background-color: var(--color-parchment-dark); color: var(--color-ink-light)">{{ record.model }}</span>
                <span v-if="record.status === 'pending'" class="px-1.5 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-700 animate-pulse">等待返回…</span>
                <span v-else-if="record.status === 'error'" class="px-1.5 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700">失败</span>
                <span v-else class="px-1.5 py-0.5 rounded text-xs font-medium bg-emerald-50 text-emerald-700">完成</span>
                <span class="text-xs" style="color: var(--color-ink-light)">
                  Prompt {{ fmtLen(record.prompt_len) }}字
                  <template v-if="record.status !== 'pending'">
                    <template v-if="record.reasoning_len"> · 思考 {{ fmtLen(record.reasoning_len) }}字</template>
                    · 回复 {{ fmtLen(record.response_len) }}字
                  </template>
                  <template v-if="record.elapsed"> · {{ record.elapsed }}s</template>
                </span>
              </div>
              <p class="text-xs mt-0.5 truncate" style="color: var(--color-ink-light)">{{ preview(record.prompt, 120) }}</p>
            </div>
            <svg class="flex-shrink-0 w-4 h-4 transition-transform"
              :class="isPromptExpanded(i) ? 'rotate-180' : ''"
              style="color: var(--color-leather)" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
            </svg>
          </div>

          <Transition name="slide">
            <div v-if="isPromptExpanded(i)" class="border-t border-[var(--color-parchment-darker)]">
              <div class="px-4 pt-3 pb-2">
                <div class="flex items-center justify-between mb-1.5">
                  <span class="text-xs font-semibold uppercase tracking-wide" style="color: var(--color-leather)">Prompt</span>
                  <button @click="copyText(record.prompt, i * 3 + 1)" class="text-xs px-2 py-0.5 rounded border"
                    style="border-color: var(--color-parchment-darker); color: var(--color-ink-light)" type="button">
                    {{ copiedIndex === i * 3 + 1 ? '✓ 已复制' : '复制' }}
                  </button>
                </div>
                <pre class="code-console text-xs font-mono whitespace-pre-wrap leading-relaxed rounded-lg p-3 overflow-auto" style="max-height: 400px">{{ record.prompt }}</pre>
              </div>

              <template v-if="record.reasoning">
                <div class="flex items-center gap-2 px-4 py-2 border-t border-[var(--color-parchment-darker)]">
                  <span class="text-xs font-semibold uppercase tracking-wide" style="color: #b8860b">Reasoning</span>
                  <span class="text-xs" style="color: var(--color-ink-light)">{{ fmtLen(record.reasoning_len || 0) }} 字</span>
                  <button @click="toggleReasoning(i)" class="ml-auto text-xs px-2 py-0.5 rounded border"
                    style="border-color: var(--color-parchment-darker); color: var(--color-ink-light)" type="button">
                    {{ isReasoningExpanded(i) ? '收起思考' : '展开思考' }}
                  </button>
                  <button @click="copyText(record.reasoning!, i * 3)" class="text-xs px-2 py-0.5 rounded border"
                    style="border-color: var(--color-parchment-darker); color: var(--color-ink-light)" type="button">
                    {{ copiedIndex === i * 3 ? '✓ 已复制' : '复制' }}
                  </button>
                </div>
                <div class="px-4 pb-3">
                  <Transition name="slide">
                    <pre v-if="isReasoningExpanded(i)"
                      class="text-xs font-mono whitespace-pre-wrap leading-relaxed rounded-lg p-3 overflow-auto"
                      style="background-color: #2a2a1a; color: #d4c87a; max-height: 520px">{{ record.reasoning }}</pre>
                    <p v-else class="text-xs italic rounded-lg p-3"
                      style="background-color: var(--color-parchment); color: var(--color-ink-light)">{{ preview(record.reasoning!, 300) }}</p>
                  </Transition>
                </div>
              </template>

              <div class="flex items-center gap-2 px-4 py-2 border-t border-[var(--color-parchment-darker)]">
                <span class="text-xs font-semibold uppercase tracking-wide" style="color: var(--color-success)">Response</span>
                <span class="text-xs" style="color: var(--color-ink-light)">{{ fmtLen(record.response_len) }} 字</span>
                <button @click="toggleResponse(i)" class="ml-auto text-xs px-2 py-0.5 rounded border"
                  style="border-color: var(--color-parchment-darker); color: var(--color-ink-light)" type="button">
                  {{ isResponseExpanded(i) ? '收起回复' : '展开回复' }}
                </button>
                <button @click="copyText(record.response, i * 3 + 2)" class="text-xs px-2 py-0.5 rounded border"
                  style="border-color: var(--color-parchment-darker); color: var(--color-ink-light)" type="button">
                  {{ copiedIndex === i * 3 + 2 ? '✓ 已复制' : '复制' }}
                </button>
              </div>
              <div class="px-4 pb-3">
                <Transition name="slide">
                  <pre v-if="isResponseExpanded(i)"
                    class="text-xs font-mono whitespace-pre-wrap leading-relaxed rounded-lg p-3 overflow-auto"
                    style="background-color: #1a2e1a; color: #a8d5a2; max-height: 520px">{{ record.response }}</pre>
                  <p v-else class="text-xs italic rounded-lg p-3"
                    style="background-color: var(--color-parchment); color: var(--color-ink-light)">{{ preview(record.response, 300) }}</p>
                </Transition>
              </div>
            </div>
          </Transition>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.lg-entry { padding: 6px 10px; border-left: 3px solid transparent; background: var(--color-surface-muted, #fafafa); border-radius: 4px; font-size: 12px; }
.lg-entry.lg-err { border-left-color: #dc2626; background: #fef2f2; }
.lg-entry.lg-warn { border-left-color: #d97706; background: #fffbeb; }
.lg-head { display: flex; align-items: baseline; gap: 6px; flex-wrap: wrap; }
.lg-time { color: var(--color-ink-light); font-family: var(--font-mono, monospace); font-size: 11px; white-space: nowrap; }
.lg-level { font-size: 10px; padding: 1px 6px; border-radius: 3px; border: 1px solid transparent; font-weight: 600; letter-spacing: 0.02em; }
.lg-mod { font-size: 10px; padding: 1px 6px; border-radius: 3px; background: var(--color-parchment-dark); color: var(--color-ink-light); }
.lg-msg { color: var(--color-ink); flex: 1; word-break: break-word; }
.lg-copy { font-size: 10px; padding: 1px 6px; border-radius: 3px; border: 1px solid var(--color-parchment-darker); background: white; cursor: pointer; }
.lg-stack { margin: 6px 0 0 0; padding: 6px 10px; background: #1f1f1f; color: #f3f3f3; border-radius: 4px; font-size: 11px; white-space: pre-wrap; max-height: 220px; overflow: auto; font-family: var(--font-mono, monospace); }
.lg-hint { margin-top: 6px; padding: 6px 10px; background: #ecfeff; border: 1px dashed #67e8f9; border-radius: 4px; color: #075985; font-size: 12px; }
</style>
