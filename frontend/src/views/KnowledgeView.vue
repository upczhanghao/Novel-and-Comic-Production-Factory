<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { knowledgeApi } from '@/api/client'
import { useConfigStore } from '@/stores/config'
import { useProjectStore } from '@/stores/project'
import { useFeedbackStore } from '@/stores/feedback'
import { confirmDialog } from '@/stores/confirm'

interface FileRecord {
  file_id: string
  filename: string
  original_filename?: string
  tags: string[]
  author?: string
  size_bytes: number
  char_count: number
  chunks: number
  imported_at: string
  status: 'ok' | 'indexing' | 'error'
  error?: string
}

interface SearchHit {
  file_id: string
  filename: string
  chunk_idx: number
  score: number
  snippet: string
}

interface Stats {
  exists: boolean
  file_count: number
  manifest_chunks: number
  vector_count: number | null
  error_count: number
  indexing_count: number
  orphan_warning: string
  store_dir: string
}

const configStore = useConfigStore()
const projectStore = useProjectStore()
const feedback = useFeedbackStore()

const embConfig = ref('')
const files = ref<FileRecord[]>([])
const stats = ref<Stats | null>(null)
const loading = ref(false)
const importing = ref(false)
const rebuilding = ref(false)

// 导入
const importTags = ref('')
const importFileInput = ref<HTMLInputElement | null>(null)

// 列表过滤
const filterTag = ref('')
const searchKeyword = ref('')

// 检索
const queryText = ref('')
const queryFileId = ref('')
const searching = ref(false)
const hits = ref<SearchHit[]>([])

// 查看原文
const sourcePreview = ref<{ filename: string; text: string } | null>(null)

// 编辑文件
const editing = ref<FileRecord | null>(null)
const editForm = ref({ filename: '', tags: '', author: '' })

// 替换文件
const replacingId = ref('')

// ── 计算属性 ──────────────────────────────────────────────────────────────
const hasEmbedding = computed(() => configStore.embeddingChoices.length > 0)
const hasProject = computed(() => !!projectStore.filepath)

const allTags = computed(() => {
  const set = new Set<string>()
  files.value.forEach((f) => (f.tags || []).forEach((t) => set.add(t)))
  return Array.from(set).sort()
})

const filteredFiles = computed(() => {
  const kw = searchKeyword.value.trim().toLowerCase()
  return files.value.filter((f) => {
    if (filterTag.value && !(f.tags || []).includes(filterTag.value)) return false
    if (kw && !(f.filename || '').toLowerCase().includes(kw) && !(f.author || '').toLowerCase().includes(kw)) return false
    return true
  })
})

// ── 数据加载 ──────────────────────────────────────────────────────────────
async function loadAll() {
  if (!hasProject.value) return
  loading.value = true
  try {
    const [fRes, sRes] = await Promise.all([
      knowledgeApi.files(projectStore.filepath),
      knowledgeApi.stats(projectStore.filepath, embConfig.value),
    ])
    files.value = fRes.data.files || []
    stats.value = sRes.data
  } catch (e: unknown) {
    feedback.error('加载知识库失败', (e as Error).message)
  } finally {
    loading.value = false
  }
}

// ── 操作 ──────────────────────────────────────────────────────────────────
async function importFile() {
  const file = importFileInput.value?.files?.[0]
  if (!file) {
    feedback.warning('请先选择文件')
    return
  }
  if (!hasEmbedding.value) {
    feedback.warning('请先在「配置 → Embedding」中创建并选择 Embedding')
    return
  }
  importing.value = true
  try {
    const fd = new FormData()
    fd.append('emb_config_name', embConfig.value)
    fd.append('filepath', projectStore.filepath)
    fd.append('file', file)
    if (importTags.value.trim()) fd.append('tags', importTags.value.trim())
    const res = await knowledgeApi.import(fd)
    feedback.success(res.data.message || '导入完成')
    if (importFileInput.value) importFileInput.value.value = ''
    importTags.value = ''
    await loadAll()
  } catch (e: unknown) {
    feedback.error('导入失败', (e as Error).message)
  } finally {
    importing.value = false
  }
}

async function deleteFile(rec: FileRecord) {
  if (!(await confirmDialog(`确认删除「${rec.filename}」？该操作会从向量库中精确移除该文件的所有片段。`))) return
  try {
    await knowledgeApi.deleteFile(rec.file_id, projectStore.filepath, embConfig.value)
    feedback.success(`已删除「${rec.filename}」`)
    await loadAll()
  } catch (e: unknown) {
    feedback.error('删除失败', (e as Error).message)
  }
}

function openEdit(rec: FileRecord) {
  editing.value = rec
  editForm.value = {
    filename: rec.filename || '',
    tags: (rec.tags || []).join(', '),
    author: rec.author || '',
  }
}

async function saveEdit() {
  if (!editing.value) return
  const target = editing.value
  try {
    await knowledgeApi.updateFile(target.file_id, projectStore.filepath, {
      filename: editForm.value.filename || target.filename,
      tags: editForm.value.tags.split(',').map((s) => s.trim()).filter(Boolean),
      author: editForm.value.author,
    })
    feedback.success('已更新')
    editing.value = null
    await loadAll()
  } catch (e: unknown) {
    feedback.error('更新失败', (e as Error).message)
  }
}

async function viewSource(rec: FileRecord) {
  try {
    const res = await knowledgeApi.source(rec.file_id, projectStore.filepath)
    sourcePreview.value = { filename: rec.filename, text: res.data.text }
  } catch (e: unknown) {
    feedback.error('读取原文失败', (e as Error).message)
  }
}

function triggerReplace(rec: FileRecord) {
  replacingId.value = rec.file_id
  const el = document.getElementById(`replace-input-${rec.file_id}`) as HTMLInputElement | null
  el?.click()
}

async function onReplaceFile(e: Event, rec: FileRecord) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  if (!(await confirmDialog(`确认用「${file.name}」替换「${rec.filename}」？旧向量将被删除并重新嵌入。`))) {
    (e.target as HTMLInputElement).value = ''
    return
  }
  try {
    const fd = new FormData()
    fd.append('filepath', projectStore.filepath)
    fd.append('emb_config_name', embConfig.value)
    fd.append('file', file)
    const res = await knowledgeApi.replaceFile(rec.file_id, fd)
    feedback.success(res.data.message || '已替换')
    await loadAll()
  } catch (err: unknown) {
    feedback.error('替换失败', (err as Error).message)
  } finally {
    (e.target as HTMLInputElement).value = ''
    replacingId.value = ''
  }
}

async function doSearch() {
  if (!queryText.value.trim()) return
  if (!hasEmbedding.value) {
    feedback.warning('请先选择 Embedding 配置')
    return
  }
  searching.value = true
  hits.value = []
  try {
    const res = await knowledgeApi.search(
      projectStore.filepath,
      queryText.value.trim(),
      embConfig.value,
      6,
      queryFileId.value || undefined,
    )
    hits.value = res.data.hits || []
    if (!hits.value.length) feedback.info('没有命中任何片段')
  } catch (e: unknown) {
    feedback.error('检索失败', (e as Error).message)
  } finally {
    searching.value = false
  }
}

async function clearLibrary() {
  if (!(await confirmDialog('确认清空整个知识库？该操作会删除所有源文件与向量。'))) return
  try {
    await knowledgeApi.clear(projectStore.filepath)
    feedback.success('知识库已清空')
    await loadAll()
  } catch (e: unknown) {
    feedback.error('清空失败', (e as Error).message)
  }
}

async function rebuildLibrary() {
  if (!hasEmbedding.value) {
    feedback.warning('请先选择 Embedding 配置')
    return
  }
  if (!(await confirmDialog('确认重建索引？将删除向量库后基于已保存源文件重新嵌入，可能需要数十秒到几分钟。'))) return
  rebuilding.value = true
  try {
    const res = await knowledgeApi.rebuild(projectStore.filepath, embConfig.value)
    feedback.success(res.data.message)
    await loadAll()
  } catch (e: unknown) {
    feedback.error('重建失败', (e as Error).message)
  } finally {
    rebuilding.value = false
  }
}

// ── 工具函数 ──────────────────────────────────────────────────────────────
function fmtBytes(n: number): string {
  if (!n) return '0 B'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(2)} MB`
}

function statusBadge(s: string) {
  if (s === 'ok') return { text: '已索引', cls: 'bg-green-100 text-green-800' }
  if (s === 'indexing') return { text: '索引中', cls: 'bg-amber-100 text-amber-800' }
  return { text: '失败', cls: 'bg-red-100 text-red-800' }
}

// ── 生命周期 ──────────────────────────────────────────────────────────────
onMounted(async () => {
  await Promise.all([configStore.loadAll(), projectStore.loadActive()])
  if (configStore.embeddingChoices.length) embConfig.value = configStore.embeddingChoices[0]
  await loadAll()
})

watch(() => configStore.embeddingChoices.slice(), (choices) => {
  if (!choices.length) {
    embConfig.value = ''
    return
  }
  if (!embConfig.value || !choices.includes(embConfig.value)) {
    embConfig.value = choices[0]
  }
})

watch(() => projectStore.filepath, () => loadAll())
</script>

<template>
  <div class="module-page compact space-y-5">
    <h2 class="text-2xl font-bold" style="color: var(--color-ink)">📚 知识库</h2>

    <!-- Embedding 缺失引导 -->
    <div v-if="!hasEmbedding" class="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      <div class="font-semibold mb-1">⚠️ 尚未配置 Embedding</div>
      <div>知识库依赖 Embedding 完成向量化检索。请到 <router-link to="/config" class="underline">配置 → Embedding</router-link> 创建一个 Embedding 配置后再继续。</div>
    </div>

    <div class="module-toolbar">
      <div>
        <div class="module-kicker">Knowledge Base</div>
        <div class="module-subtitle">项目级 RAG 检索库：每个文件单独管理、独立向量化、可重建可替换。</div>
      </div>
      <div>
        <label class="block text-xs text-[var(--color-ink-light)] mb-1">Embedding 配置</label>
        <select v-model="embConfig" class="border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm w-full max-w-xs">
          <option v-for="c in configStore.embeddingChoices" :key="c" :value="c">{{ c }}</option>
        </select>
      </div>
    </div>

    <!-- 统计概览 -->
    <div v-if="stats" class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <div class="rounded-md border border-[var(--color-parchment-darker)] bg-white px-4 py-3">
        <div class="text-xs text-[var(--color-ink-light)]">文件数</div>
        <div class="text-2xl font-semibold">{{ stats.file_count }}</div>
      </div>
      <div class="rounded-md border border-[var(--color-parchment-darker)] bg-white px-4 py-3">
        <div class="text-xs text-[var(--color-ink-light)]">清单切片</div>
        <div class="text-2xl font-semibold">{{ stats.manifest_chunks }}</div>
      </div>
      <div class="rounded-md border border-[var(--color-parchment-darker)] bg-white px-4 py-3">
        <div class="text-xs text-[var(--color-ink-light)]">向量库实际</div>
        <div class="text-2xl font-semibold">{{ stats.vector_count ?? '—' }}</div>
      </div>
      <div class="rounded-md border border-[var(--color-parchment-darker)] bg-white px-4 py-3">
        <div class="text-xs text-[var(--color-ink-light)]">异常 / 索引中</div>
        <div class="text-2xl font-semibold">{{ stats.error_count }} / {{ stats.indexing_count }}</div>
      </div>
    </div>
    <div v-if="stats?.orphan_warning" class="rounded-md border border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-900">
      ⚠️ {{ stats.orphan_warning }}
      <button class="ml-2 underline" @click="rebuildLibrary" type="button">立即重建</button>
    </div>

    <!-- 导入 -->
    <div class="module-panel p-5 space-y-3">
      <h3 class="module-panel-title">导入文件</h3>
      <p class="text-sm text-[var(--color-ink-light)]">支持 .txt 文件。每个文件单独切分、嵌入并标记元数据，可独立删除/替换/重命名。</p>
      <div class="grid md:grid-cols-3 gap-3">
        <div class="md:col-span-2">
          <label class="block text-xs text-[var(--color-ink-light)] mb-1">选择文件</label>
          <input ref="importFileInput" type="file" accept=".txt,.md"
            class="text-sm w-full file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:font-medium file:cursor-pointer" />
        </div>
        <div>
          <label class="block text-xs text-[var(--color-ink-light)] mb-1">标签（逗号分隔）</label>
          <input v-model="importTags" type="text" placeholder="例如：背景资料, 人物设定"
            class="border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm w-full" />
        </div>
      </div>
      <div class="module-action-row">
        <button @click="importFile" :disabled="importing || !hasEmbedding"
          class="px-4 py-2 rounded-md text-sm font-semibold disabled:opacity-50"
          style="background-color: var(--color-leather); color: var(--color-parchment)" type="button">
          {{ importing ? '导入中…' : '▶ 导入并索引' }}
        </button>
      </div>
    </div>

    <!-- 文件列表 -->
    <div class="module-panel p-5 space-y-3">
      <div class="flex flex-wrap items-center gap-3">
        <h3 class="module-panel-title flex-1">文件列表</h3>
        <input v-model="searchKeyword" type="text" placeholder="搜索文件名 / 作者"
          class="border border-[var(--color-parchment-darker)] rounded-md px-3 py-1.5 text-sm w-48" />
        <select v-model="filterTag" class="border border-[var(--color-parchment-darker)] rounded-md px-3 py-1.5 text-sm">
          <option value="">全部标签</option>
          <option v-for="t in allTags" :key="t" :value="t">{{ t }}</option>
        </select>
        <button @click="loadAll" class="text-sm text-[var(--color-leather)] underline" type="button">🔄 刷新</button>
      </div>

      <div v-if="loading" class="text-sm text-[var(--color-ink-light)] py-6 text-center">加载中…</div>
      <div v-else-if="!filteredFiles.length" class="text-sm text-[var(--color-ink-light)] py-6 text-center">
        {{ files.length ? '没有匹配的文件' : '还没有文件，上传一个开始构建知识库' }}
      </div>
      <div v-else class="overflow-auto">
        <table class="w-full text-sm">
          <thead class="text-xs text-[var(--color-ink-light)] border-b border-[var(--color-parchment-darker)]">
            <tr>
              <th class="text-left py-2 px-2">文件名</th>
              <th class="text-left py-2 px-2">标签</th>
              <th class="text-left py-2 px-2">作者</th>
              <th class="text-right py-2 px-2">大小</th>
              <th class="text-right py-2 px-2">切片</th>
              <th class="text-left py-2 px-2">导入时间</th>
              <th class="text-center py-2 px-2">状态</th>
              <th class="text-right py-2 px-2">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="f in filteredFiles" :key="f.file_id" class="border-b border-[var(--color-parchment-darker)] hover:bg-[var(--color-parchment-light)]">
              <td class="py-2 px-2">
                <div class="font-medium truncate max-w-[20ch]" :title="f.filename">{{ f.filename }}</div>
                <div v-if="f.error" class="text-xs text-red-600 truncate max-w-[24ch]" :title="f.error">{{ f.error }}</div>
              </td>
              <td class="py-2 px-2">
                <span v-for="t in f.tags" :key="t" class="inline-block bg-[var(--color-parchment-darker)] text-[var(--color-ink-light)] rounded px-1.5 py-0.5 text-xs mr-1">{{ t }}</span>
              </td>
              <td class="py-2 px-2 text-[var(--color-ink-light)]">{{ f.author || '—' }}</td>
              <td class="py-2 px-2 text-right text-[var(--color-ink-light)]">{{ fmtBytes(f.size_bytes) }}</td>
              <td class="py-2 px-2 text-right">{{ f.chunks }}</td>
              <td class="py-2 px-2 text-[var(--color-ink-light)] text-xs">{{ f.imported_at }}</td>
              <td class="py-2 px-2 text-center">
                <span class="px-2 py-0.5 rounded text-xs" :class="statusBadge(f.status).cls">{{ statusBadge(f.status).text }}</span>
              </td>
              <td class="py-2 px-2">
                <div class="flex gap-2 justify-end">
                  <button @click="viewSource(f)" class="text-xs text-[var(--color-leather)] hover:underline" type="button">原文</button>
                  <button @click="openEdit(f)" class="text-xs text-blue-600 hover:underline" type="button">编辑</button>
                  <button @click="triggerReplace(f)" class="text-xs text-amber-600 hover:underline" type="button">替换</button>
                  <input :id="`replace-input-${f.file_id}`" type="file" accept=".txt,.md" class="hidden" @change="(e) => onReplaceFile(e, f)" />
                  <button @click="deleteFile(f)" class="text-xs text-red-600 hover:underline" type="button">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="module-action-row pt-2 border-t border-[var(--color-parchment-darker)]">
        <button @click="rebuildLibrary" :disabled="rebuilding || !hasEmbedding || !files.length"
          class="px-3 py-1.5 rounded-md text-sm border border-[var(--color-parchment-darker)] hover:bg-[var(--color-parchment-light)] disabled:opacity-50" type="button">
          {{ rebuilding ? '重建中…' : '🔄 重建索引' }}
        </button>
        <button @click="clearLibrary" :disabled="!files.length"
          class="px-3 py-1.5 rounded-md text-sm border border-red-200 text-red-600 hover:bg-red-50 disabled:opacity-50" type="button">
          🗑️ 清空知识库
        </button>
      </div>
    </div>

    <!-- 检索 -->
    <div class="module-panel p-5 space-y-3">
      <h3 class="module-panel-title">检索（RAG 预览）</h3>
      <p class="text-sm text-[var(--color-ink-light)]">在导入后用真实查询验证命中片段，确认知识库可用。</p>
      <div class="grid md:grid-cols-3 gap-3">
        <input v-model="queryText" @keyup.enter="doSearch" type="text" placeholder="输入查询语句"
          class="md:col-span-2 border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm w-full" />
        <select v-model="queryFileId" class="border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm">
          <option value="">所有文件</option>
          <option v-for="f in files" :key="f.file_id" :value="f.file_id">{{ f.filename }}</option>
        </select>
      </div>
      <div class="module-action-row">
        <button @click="doSearch" :disabled="searching || !queryText.trim() || !hasEmbedding"
          class="px-4 py-2 rounded-md text-sm font-semibold disabled:opacity-50"
          style="background-color: var(--color-leather); color: var(--color-parchment)" type="button">
          {{ searching ? '检索中…' : '🔍 检索' }}
        </button>
      </div>

      <div v-if="hits.length" class="space-y-2">
        <div v-for="(h, i) in hits" :key="i" class="rounded-md border border-[var(--color-parchment-darker)] bg-[var(--color-parchment-light)] p-3 text-sm">
          <div class="flex items-center justify-between text-xs text-[var(--color-ink-light)] mb-1">
            <span>📄 {{ h.filename || '(未知文件)' }} · chunk #{{ h.chunk_idx }}</span>
            <span>相关度 {{ h.score.toFixed(3) }}</span>
          </div>
          <pre class="whitespace-pre-wrap text-[var(--color-ink)]">{{ h.snippet }}</pre>
        </div>
      </div>
    </div>

    <!-- 编辑对话框 -->
    <div v-if="editing" class="fixed inset-0 z-40 flex items-center justify-center bg-black/40" @click.self="editing = null">
      <div class="bg-white rounded-lg shadow-xl w-full max-w-md p-5 space-y-3">
        <h4 class="font-semibold">编辑文件元数据</h4>
        <div>
          <label class="block text-xs text-[var(--color-ink-light)] mb-1">显示文件名</label>
          <input v-model="editForm.filename" class="border rounded px-3 py-2 text-sm w-full" />
        </div>
        <div>
          <label class="block text-xs text-[var(--color-ink-light)] mb-1">标签（逗号分隔）</label>
          <input v-model="editForm.tags" class="border rounded px-3 py-2 text-sm w-full" />
        </div>
        <div>
          <label class="block text-xs text-[var(--color-ink-light)] mb-1">作者</label>
          <input v-model="editForm.author" class="border rounded px-3 py-2 text-sm w-full" />
        </div>
        <div class="flex justify-end gap-2 pt-2">
          <button @click="editing = null" class="px-3 py-1.5 text-sm border rounded" type="button">取消</button>
          <button @click="saveEdit" class="px-3 py-1.5 text-sm rounded text-white" style="background-color: var(--color-leather)" type="button">保存</button>
        </div>
      </div>
    </div>

    <!-- 原文预览对话框 -->
    <div v-if="sourcePreview" class="fixed inset-0 z-40 flex items-center justify-center bg-black/40" @click.self="sourcePreview = null">
      <div class="bg-white rounded-lg shadow-xl w-full max-w-3xl max-h-[80vh] flex flex-col p-5">
        <div class="flex items-center justify-between mb-3">
          <h4 class="font-semibold truncate">📄 {{ sourcePreview.filename }}</h4>
          <button @click="sourcePreview = null" class="text-sm text-[var(--color-ink-light)]" type="button">✕</button>
        </div>
        <pre class="flex-1 overflow-auto text-sm whitespace-pre-wrap bg-[var(--color-parchment-light)] p-3 rounded">{{ sourcePreview.text }}</pre>
      </div>
    </div>

    <p class="text-xs text-[var(--color-ink-light)] italic">作者参考库已移至「文风与叙事DNA」页面，绑定到具体文风。</p>
  </div>
</template>
