import { ref, computed, type Ref } from 'vue'
import { useFeedbackStore } from '@/stores/feedback'
import { confirmDialog } from '@/stores/confirm'

// A7: 知识库 / 作者参考库共用的库管理逻辑。两者 API 形状相同，仅 scope 不同：
// - Knowledge: 全局，按 filepath 寻址
// - AuthorRef: 按 styleName 寻址，绑定到具体文风
// 通过 adapter 注入具体 API 调用；UI（按钮/表头）保持各自 view 控制。

export interface LibraryFileRecord {
  file_id: string
  filename: string
  tags: string[]
  author?: string
  size_bytes: number
  chunks: number
  imported_at: string
  status: 'ok' | 'indexing' | 'error'
  error?: string
}

export interface LibraryStats {
  exists?: boolean
  file_count: number
  manifest_chunks: number
  vector_count: number | null
  error_count: number
  indexing_count: number
  orphan_warning: string
}

export interface LibraryAdapter {
  files: () => Promise<{ files: LibraryFileRecord[] }>
  stats: (embConfig: string) => Promise<LibraryStats>
  import: (fd: FormData) => Promise<{ message?: string }>
  deleteFile: (fileId: string, embConfig: string) => Promise<unknown>
  search: (query: string, embConfig: string, k: number, fileId?: string) => Promise<{ hits: LibrarySearchHit[] }>
  source: (fileId: string) => Promise<{ text: string }>
  rebuild: (embConfig: string) => Promise<{ message?: string }>
  clear?: () => Promise<unknown>
  // optional — knowledge has updateFile(meta) and replaceFile(file); authorRef has only rename via updateFile
  updateFile?: (fileId: string, data: { filename?: string; tags?: string[]; author?: string }) => Promise<unknown>
  replaceFile?: (fileId: string, fd: FormData) => Promise<{ message?: string }>
}

export interface LibrarySearchHit {
  file_id: string
  filename: string
  chunk_idx: number
  score: number
  snippet: string
}

export function useLibrary(adapter: Ref<LibraryAdapter | null>) {
  const feedback = useFeedbackStore()

  const files = ref<LibraryFileRecord[]>([])
  const stats = ref<LibraryStats | null>(null)
  const loading = ref(false)
  const importing = ref(false)
  const rebuilding = ref(false)
  const searching = ref(false)
  const hits = ref<LibrarySearchHit[]>([])
  const sourcePreview = ref<{ filename: string; text: string } | null>(null)

  const totalFiles = computed(() => stats.value?.file_count ?? files.value.length)

  async function load(embConfig: string, opts: { silent?: boolean } = {}) {
    if (!adapter.value) return
    loading.value = true
    try {
      const [fRes, sRes] = await Promise.all([adapter.value.files(), adapter.value.stats(embConfig)])
      files.value = fRes.files || []
      stats.value = sRes
    } catch (e: unknown) {
      files.value = []
      stats.value = null
      if (!opts.silent) feedback.error('加载失败', (e as Error).message)
    } finally {
      loading.value = false
    }
  }

  async function importFiles(toImport: File[], embConfig: string, tags: string, extraFormFields: (fd: FormData) => void) {
    if (!adapter.value || !toImport.length || !embConfig) return { success: 0, failed: 0 }
    importing.value = true
    let success = 0, failed = 0
    for (const file of toImport) {
      try {
        const fd = new FormData()
        fd.append('emb_config_name', embConfig)
        fd.append('file', file)
        if (tags.trim()) fd.append('tags', tags.trim())
        extraFormFields(fd)
        await adapter.value.import(fd)
        success++
      } catch { failed++ }
    }
    importing.value = false
    return { success, failed }
  }

  async function deleteFile(rec: LibraryFileRecord, embConfig: string, confirmText?: string) {
    if (!adapter.value) return false
    const ok = await confirmDialog(confirmText ?? `确认删除「${rec.filename}」？`)
    if (!ok) return false
    try {
      await adapter.value.deleteFile(rec.file_id, embConfig)
      feedback.success(`已删除「${rec.filename}」`)
      return true
    } catch (e: unknown) { feedback.error('删除失败', (e as Error).message); return false }
  }

  async function search(query: string, embConfig: string, k = 6, fileId?: string) {
    if (!adapter.value || !query.trim()) return
    if (!embConfig) { feedback.warning('请先选择 Embedding'); return }
    searching.value = true
    hits.value = []
    try {
      const res = await adapter.value.search(query.trim(), embConfig, k, fileId)
      hits.value = res.hits || []
      if (!hits.value.length) feedback.info('没有命中任何片段')
    } catch (e: unknown) { feedback.error('检索失败', (e as Error).message) }
    finally { searching.value = false }
  }

  async function viewSource(rec: LibraryFileRecord) {
    if (!adapter.value) return
    try {
      const res = await adapter.value.source(rec.file_id)
      sourcePreview.value = { filename: rec.filename, text: res.text }
    } catch (e: unknown) { feedback.error('读取原文失败', (e as Error).message) }
  }

  async function rebuild(embConfig: string, confirmText?: string) {
    if (!adapter.value) return false
    if (!embConfig) { feedback.warning('请先选择 Embedding'); return false }
    const ok = await confirmDialog(confirmText ?? '确认重建索引？将删除向量库后基于已保存源文件重新嵌入。')
    if (!ok) return false
    rebuilding.value = true
    try {
      const res = await adapter.value.rebuild(embConfig)
      if (res.message) feedback.success(res.message)
      return true
    } catch (e: unknown) { feedback.error('重建失败', (e as Error).message); return false }
    finally { rebuilding.value = false }
  }

  async function clearAll(confirmText: string) {
    if (!adapter.value?.clear) return false
    if (!(await confirmDialog(confirmText))) return false
    try {
      await adapter.value.clear()
      feedback.success('已清空')
      return true
    } catch (e: unknown) { feedback.error('清空失败', (e as Error).message); return false }
  }

  return {
    files, stats, loading, importing, rebuilding, searching, hits, sourcePreview, totalFiles,
    load, importFiles, deleteFile, search, viewSource, rebuild, clearAll,
  }
}

export function fmtBytes(n: number): string {
  if (!n) return '0 B'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(2)} MB`
}
