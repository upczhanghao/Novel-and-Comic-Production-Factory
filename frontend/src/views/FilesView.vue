<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { filesApi } from '@/api/client'
import { useProjectStore } from '@/stores/project'

interface FileEntry {
  path: string
  name: string
  size: number
  directory: string
}

const projectStore = useProjectStore()
const files = ref<FileEntry[]>([])
const selectedFile = ref<FileEntry | null>(null)
const fileContent = ref('')
const loading = ref(false)
const loadingContent = ref(false)

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

async function loadFiles() {
  loading.value = true
  try {
    const res = await filesApi.list(projectStore.filepath)
    files.value = res.data.files
  } catch { /* ignore */ } finally {
    loading.value = false }
}

async function loadContent(f: FileEntry) {
  selectedFile.value = f
  loadingContent.value = true
  try {
    const res = await filesApi.content(projectStore.filepath, f.path)
    fileContent.value = res.data.content
  } catch (e: unknown) {
    fileContent.value = `❌ 读取失败: ${(e as Error).message}`
  } finally {
    loadingContent.value = false
  }
}

// 按目录分组
const grouped = ref<Record<string, FileEntry[]>>({})
watch(files, (flist) => {
  const g: Record<string, FileEntry[]> = {}
  for (const f of flist) {
    const dir = f.directory || '.'
    if (!g[dir]) g[dir] = []
    g[dir].push(f)
  }
  grouped.value = g
})

onMounted(async () => {
  await projectStore.loadActive()
  await loadFiles()
})

watch(() => projectStore.filepath, loadFiles)
</script>

<template>
  <div class="module-page space-y-4">
    <div class="module-toolbar">
      <h2 class="text-2xl font-bold" style="color: var(--color-ink)">📁 文件管理</h2>
      <div>
        <div class="module-kicker">Project Files</div>
        <div class="module-subtitle">浏览当前项目生成的文稿、配置和结构化数据。</div>
      </div>
      <button @click="loadFiles" class="border border-[var(--color-parchment-darker)] rounded-md px-3 py-1.5 text-sm hover:bg-[var(--color-parchment)] transition-colors" type="button">
        🔄 刷新
      </button>
    </div>

    <p class="text-sm text-[var(--color-ink-light)]">路径：<code class="font-mono bg-[var(--color-parchment-dark)] px-1 rounded">{{ projectStore.filepath }}</code></p>

    <div class="module-grid">
      <!-- 文件树 -->
      <div class="module-panel overflow-hidden module-aside-sticky">
        <div class="module-panel-header">
          <span class="module-panel-title">文件列表</span>
        </div>
        <div class="overflow-y-auto" style="max-height: 600px">
          <div v-if="loading" class="p-4 text-sm text-[var(--color-ink-light)] italic">加载中…</div>
          <div v-else-if="files.length === 0" class="p-4 text-sm text-[var(--color-ink-light)] italic">暂无文件</div>
          <div v-else>
            <div v-for="(group, dir) in grouped" :key="dir">
              <div class="px-3 py-1.5 bg-[var(--color-parchment-dark)] text-xs font-medium text-[var(--color-ink-light)] sticky top-0">
                {{ dir }}
              </div>
              <button
                v-for="f in group"
                :key="f.path"
                @click="loadContent(f)"
                class="w-full text-left px-4 py-2 text-sm hover:bg-[var(--color-parchment)] transition-colors flex items-center justify-between gap-2"
                :class="selectedFile?.path === f.path ? 'bg-[var(--color-parchment)] font-medium' : ''"
                type="button"
              >
                <span class="truncate">{{ f.name }}</span>
                <span class="text-xs text-[var(--color-ink-light)] whitespace-nowrap">{{ formatSize(f.size) }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 文件内容 -->
      <div class="module-panel overflow-hidden">
        <div class="module-panel-header">
          <span class="module-panel-title">
            {{ selectedFile ? selectedFile.path : '请选择文件' }}
          </span>
        </div>
        <div class="p-4 overflow-y-auto" style="max-height: 600px">
          <div v-if="loadingContent" class="text-sm text-[var(--color-ink-light)] italic">加载中…</div>
          <pre v-else-if="fileContent" class="code-console text-sm font-mono whitespace-pre-wrap leading-relaxed rounded-md p-4">{{ fileContent }}</pre>
          <p v-else class="text-sm text-[var(--color-ink-light)] italic">点击左侧文件查看内容</p>
        </div>
      </div>
    </div>
  </div>
</template>
