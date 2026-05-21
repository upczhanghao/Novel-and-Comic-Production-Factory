<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { filesApi } from '@/api/client'
import { useProjectStore } from '@/stores/project'
import { useFeedbackStore } from '@/stores/feedback'
import { useGenerateStore } from '@/stores/generate'
import { confirmDialog } from '@/stores/confirm'
import FileTreeNode, { type FileTreeNode as FileTreeNodeT } from '@/components/FileTreeNode.vue'

interface FileEntry {
  path: string
  name: string
  size: number
  mtime: number
  directory: string
}

interface SearchHit {
  path: string
  matches: number
  snippet: string
  line: number
}

const projectStore = useProjectStore()
const feedback = useFeedbackStore()
const generateStore = useGenerateStore()

type Pane = 'tree' | 'recent' | 'search'
const pane = ref<Pane>('tree')

const files = ref<FileEntry[]>([])
const tree = ref<FileTreeNodeT | null>(null)
const recent = ref<FileEntry[]>([])
const searchHits = ref<SearchHit[]>([])
const searchQuery = ref('')
const searchCase = ref(false)
const searching = ref(false)
const expanded = ref<Set<string>>(new Set())

const selectedFile = ref<FileEntry | null>(null)
const fileContent = ref('')
const editing = ref(false)
const draft = ref('')
const loading = ref(false)
const loadingContent = ref(false)
const savingContent = ref(false)
const checked = ref<Set<string>>(new Set())

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

function formatTime(mtime?: number) {
  if (!mtime) return ''
  const d = new Date(mtime * 1000)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadAll() {
  loading.value = true
  try {
    const [listRes, treeRes, recentRes] = await Promise.all([
      filesApi.list(projectStore.filepath),
      filesApi.tree(projectStore.filepath),
      filesApi.recent(projectStore.filepath, 20),
    ])
    files.value = listRes.data.files ?? []
    tree.value = treeRes.data.tree ?? null
    recent.value = recentRes.data.files ?? []
    // 默认展开顶层
    if (tree.value) expanded.value = new Set([tree.value.path])
  } catch (e) {
    feedback.error('加载文件失败', (e as Error).message)
  } finally {
    loading.value = false
  }
}

async function loadContent(path: string) {
  if (!path) return
  const found = files.value.find((f) => f.path === path) ?? null
  selectedFile.value = found ?? { path, name: path.split('/').pop() || path, size: 0, mtime: 0, directory: '' }
  loadingContent.value = true
  editing.value = false
  try {
    const res = await filesApi.content(projectStore.filepath, path)
    fileContent.value = res.data.content
    draft.value = fileContent.value
    if (!found && res.data.size) selectedFile.value!.size = res.data.size
  } catch (e) {
    fileContent.value = `❌ 读取失败: ${(e as Error).message}`
  } finally {
    loadingContent.value = false
  }
}

function toggleExpand(path: string) {
  if (expanded.value.has(path)) expanded.value.delete(path)
  else expanded.value.add(path)
  expanded.value = new Set(expanded.value)
}

function toggleCheck(path: string) {
  if (checked.value.has(path)) checked.value.delete(path)
  else checked.value.add(path)
  checked.value = new Set(checked.value)
}

async function startEdit() {
  if (!selectedFile.value) return
  editing.value = true
  draft.value = fileContent.value
}

async function saveEdit() {
  if (!selectedFile.value) return
  savingContent.value = true
  try {
    await filesApi.write(projectStore.filepath, selectedFile.value.path, draft.value)
    fileContent.value = draft.value
    editing.value = false
    feedback.success(`✅ 已保存 ${selectedFile.value.path}`)
    await generateStore.invalidateForPath(selectedFile.value.path)
    await loadAll()
  } catch (e) {
    feedback.error('保存失败', (e as Error).message)
  } finally {
    savingContent.value = false
  }
}

async function deleteOne(path: string) {
  if (!(await confirmDialog(`确认删除「${path}」？（文件会移入 trash 目录）`))) return
  try {
    await filesApi.deleteItem(projectStore.filepath, path)
    if (selectedFile.value?.path === path) {
      selectedFile.value = null
      fileContent.value = ''
    }
    checked.value.delete(path)
    feedback.success(`✅ 已删除 ${path}`)
    await loadAll()
  } catch (e) {
    feedback.error('删除失败', (e as Error).message)
  }
}

async function batchDelete() {
  const paths = [...checked.value]
  if (!paths.length) return
  if (!(await confirmDialog(`确认删除选中的 ${paths.length} 个文件？`))) return
  try {
    const res = await filesApi.batchDelete(projectStore.filepath, paths)
    feedback.success(res.data.message ?? '✅ 已删除')
    checked.value = new Set()
    await loadAll()
  } catch (e) {
    feedback.error('批量删除失败', (e as Error).message)
  }
}

async function batchDownload() {
  const paths = [...checked.value]
  try {
    const res = await filesApi.archive(projectStore.filepath, paths.length ? paths : undefined)
    const blob = new Blob([res.data], { type: 'application/zip' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const stamp = new Date().toISOString().replace(/[:T-]/g, '').slice(0, 14)
    a.download = `project_${stamp}.zip`
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 5000)
    feedback.success(paths.length ? `✅ 已打包 ${paths.length} 个文件` : '✅ 已打包整个项目')
  } catch (e) {
    feedback.error('打包失败', (e as Error).message)
  }
}

function downloadOne(path: string) {
  const url = filesApi.downloadUrl(projectStore.filepath, path)
  window.open(url, '_blank')
}

async function runSearch() {
  if (!searchQuery.value.trim()) {
    searchHits.value = []
    return
  }
  searching.value = true
  try {
    const res = await filesApi.search(projectStore.filepath, searchQuery.value.trim(), searchCase.value, 200)
    searchHits.value = res.data.results ?? []
    if (!searchHits.value.length) feedback.info('未找到匹配项')
  } catch (e) {
    feedback.error('搜索失败', (e as Error).message)
  } finally {
    searching.value = false
  }
}

const allChecked = computed(() =>
  files.value.length > 0 && files.value.every((f) => checked.value.has(f.path)),
)

function toggleCheckAll() {
  if (allChecked.value) checked.value = new Set()
  else checked.value = new Set(files.value.map((f) => f.path))
}

onMounted(async () => {
  await projectStore.loadActive()
  await loadAll()
})

watch(() => projectStore.filepath, loadAll)
</script>

<template>
  <div class="module-page space-y-4">
    <div class="module-toolbar">
      <h2 class="text-2xl font-bold" style="color: var(--color-ink)">📁 项目浏览器</h2>
      <div>
        <div class="module-kicker">Project Browser</div>
        <div class="module-subtitle">结构树、最近修改、全文搜索；支持预览、编辑、删除、批量下载。仅显示 .txt / .json / .md 文件。</div>
      </div>
      <div class="module-action-row">
        <button @click="loadAll" class="px-3 py-1.5 rounded-md border border-[var(--color-parchment-darker)] text-sm bg-white" type="button">🔄 刷新</button>
        <button @click="batchDownload" class="px-3 py-1.5 rounded-md border border-[var(--color-parchment-darker)] text-sm bg-white" type="button">
          ⬇ {{ checked.size ? `下载选中 (${checked.size})` : '打包全部' }}
        </button>
        <button
          v-if="checked.size"
          @click="batchDelete"
          class="px-3 py-1.5 rounded-md border border-red-300 text-sm bg-red-50 text-red-700"
          type="button"
        >🗑 删除选中 ({{ checked.size }})</button>
      </div>
    </div>

    <p class="text-sm text-[var(--color-ink-light)]">路径：<code class="font-mono bg-[var(--color-parchment-dark)] px-1 rounded">{{ projectStore.filepath }}</code></p>

    <section class="module-grid two">
      <aside class="module-panel overflow-hidden flex flex-col" style="max-height: 70vh">
        <div class="fb-tabs">
          <button class="fb-tab" :class="{ active: pane === 'tree' }" @click="pane = 'tree'" type="button">结构树</button>
          <button class="fb-tab" :class="{ active: pane === 'recent' }" @click="pane = 'recent'" type="button">最近修改</button>
          <button class="fb-tab" :class="{ active: pane === 'search' }" @click="pane = 'search'" type="button">全文搜索</button>
        </div>

        <div v-if="pane === 'tree'" class="flex-1 overflow-y-auto p-2">
          <div v-if="loading" class="text-sm text-[var(--color-ink-light)] italic p-2">加载中…</div>
          <div v-else-if="!tree" class="text-sm text-[var(--color-ink-light)] italic p-2">暂无文件</div>
          <template v-else>
            <div class="flex items-center justify-between px-2 pb-1">
              <label class="text-[11px] text-[var(--color-ink-light)] flex items-center gap-1">
                <input type="checkbox" :checked="allChecked" @change="toggleCheckAll" /> 全选 ({{ files.length }})
              </label>
            </div>
            <FileTreeNode
              :node="tree"
              :expanded="expanded"
              :checked="checked"
              :selected-path="selectedFile?.path ?? ''"
              @toggle="toggleExpand"
              @check="toggleCheck"
              @open="loadContent"
              @delete="deleteOne"
              @download="downloadOne"
            />
          </template>
        </div>

        <div v-else-if="pane === 'recent'" class="flex-1 overflow-y-auto p-2">
          <div v-if="!recent.length" class="text-sm text-[var(--color-ink-light)] italic p-2">暂无记录</div>
          <button
            v-for="f in recent"
            :key="f.path"
            @click="loadContent(f.path)"
            class="w-full text-left px-2 py-1.5 hover:bg-[var(--color-parchment)] rounded-md flex items-center justify-between gap-2"
            :class="selectedFile?.path === f.path ? 'bg-[var(--color-parchment)] font-medium' : ''"
            type="button"
          >
            <span class="truncate text-sm">{{ f.path }}</span>
            <span class="text-[10px] text-[var(--color-ink-light)] whitespace-nowrap">{{ formatTime(f.mtime) }}</span>
          </button>
        </div>

        <div v-else class="flex-1 overflow-y-auto p-2 space-y-2">
          <div class="flex items-center gap-1">
            <input
              v-model="searchQuery"
              @keyup.enter="runSearch"
              placeholder="搜索关键词…"
              class="flex-1 border border-[var(--color-parchment-darker)] rounded-md px-2 py-1.5 text-sm"
            />
            <button @click="runSearch" :disabled="searching" class="px-2 py-1.5 rounded-md border text-sm bg-white" type="button">
              {{ searching ? '…' : '搜索' }}
            </button>
          </div>
          <label class="text-[11px] text-[var(--color-ink-light)] flex items-center gap-1 px-1">
            <input type="checkbox" v-model="searchCase" /> 区分大小写
          </label>
          <div v-if="!searchHits.length && searchQuery && !searching" class="text-xs text-[var(--color-ink-light)] italic p-2">无结果</div>
          <button
            v-for="h in searchHits"
            :key="h.path"
            @click="loadContent(h.path)"
            class="w-full text-left px-2 py-2 rounded-md hover:bg-[var(--color-parchment)] border border-transparent"
            :class="selectedFile?.path === h.path ? 'bg-[var(--color-parchment)] border-[var(--color-parchment-darker)]' : ''"
            type="button"
          >
            <div class="flex items-center justify-between gap-2">
              <span class="truncate text-sm font-medium">{{ h.path }}</span>
              <span class="text-[10px] text-[var(--color-ink-light)]">行 {{ h.line }} · {{ h.matches }} 处</span>
            </div>
            <div class="text-[11px] text-[var(--color-ink-light)] mt-0.5 line-clamp-2">{{ h.snippet }}</div>
          </button>
        </div>
      </aside>

      <main class="module-panel overflow-hidden flex flex-col" style="max-height: 70vh">
        <div class="module-panel-header flex items-center justify-between gap-2">
          <span class="module-panel-title truncate">{{ selectedFile ? selectedFile.path : '请选择文件' }}</span>
          <div v-if="selectedFile" class="flex items-center gap-1 text-xs">
            <span class="text-[var(--color-ink-light)]">{{ formatSize(selectedFile.size) }} · {{ formatTime(selectedFile.mtime) }}</span>
            <button v-if="!editing" @click="startEdit" class="px-2 py-1 rounded-md border text-xs bg-white" type="button">✎ 编辑</button>
            <button v-else @click="saveEdit" :disabled="savingContent" class="px-2 py-1 rounded-md border text-xs bg-white" type="button">
              {{ savingContent ? '保存中…' : '💾 保存' }}
            </button>
            <button v-if="editing" @click="editing = false; draft = fileContent" class="px-2 py-1 rounded-md border text-xs bg-white" type="button">取消</button>
            <button @click="downloadOne(selectedFile.path)" class="px-2 py-1 rounded-md border text-xs bg-white" type="button">⬇</button>
            <button @click="deleteOne(selectedFile.path)" class="px-2 py-1 rounded-md border border-red-300 text-xs bg-red-50 text-red-700" type="button">🗑</button>
          </div>
        </div>
        <div class="flex-1 overflow-y-auto p-3">
          <div v-if="loadingContent" class="text-sm text-[var(--color-ink-light)] italic">加载中…</div>
          <textarea
            v-else-if="editing"
            v-model="draft"
            class="w-full h-full min-h-[60vh] font-mono text-sm border border-[var(--color-parchment-darker)] rounded-md p-3 bg-white"
            spellcheck="false"
          />
          <pre v-else-if="fileContent" class="code-console text-sm font-mono whitespace-pre-wrap leading-relaxed rounded-md p-3">{{ fileContent }}</pre>
          <p v-else class="text-sm text-[var(--color-ink-light)] italic">从左侧选择文件查看或编辑内容</p>
        </div>
      </main>
    </section>
  </div>
</template>

<style scoped>
.fb-tabs { display: flex; gap: 2px; border-bottom: 1px solid var(--color-control-border); padding: 0 4px; }
.fb-tab { padding: 6px 12px; font-size: 12px; color: var(--color-ink-light); background: transparent; border: none; border-bottom: 2px solid transparent; cursor: pointer; }
.fb-tab.active { color: var(--color-ink); border-bottom-color: var(--color-leather); font-weight: 600; }
.fb-tab:hover { color: var(--color-ink); }
</style>
