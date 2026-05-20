<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed, nextTick } from 'vue'
import { useLocalStorage } from '@vueuse/core'
import { generateApi } from '@/api/client'
import { useProjectStore } from '@/stores/project'
import { useFeedbackStore } from '@/stores/feedback'

interface ChapterInfo {
  num: number
  has_draft: boolean
  has_final: boolean
}

interface TocEntry {
  num: number
  title: string
}

interface SearchHit {
  num: number
  line: number
  preview: string
  pos: number
}

const projectStore = useProjectStore()
const feedback = useFeedbackStore()

const chapters = ref<ChapterInfo[]>([])
const currentChapter = ref<number | null>(null)
const currentContent = ref('')
const allContents = ref<{ num: number; content: string }[]>([])
const mode = ref<'single' | 'all'>('single')
const loading = ref(false)
const loadingList = ref(false)

// Sidebar toggles
type SidePane = 'chapters' | 'toc' | 'search'
const sidePane = ref<SidePane>('chapters')

// Full-text search
const searchQuery = ref('')
const searchHits = ref<SearchHit[]>([])
const searching = ref(false)

const fontSize = useLocalStorage('reader-font-size', 16)

const currentIndex = computed(() =>
  chapters.value.findIndex((c) => c.num === currentChapter.value),
)
const hasPrev = computed(() => currentIndex.value > 0)
const hasNext = computed(() => currentIndex.value < chapters.value.length - 1)

// TOC: parse first line of each chapter as title (heuristic)
const toc = computed<TocEntry[]>(() => {
  const arr: TocEntry[] = []
  if (mode.value === 'single' && currentChapter.value != null && currentContent.value) {
    const firstLine = currentContent.value.split('\n').find((l) => l.trim()) ?? `第 ${currentChapter.value} 章`
    arr.push({ num: currentChapter.value, title: firstLine.trim().slice(0, 40) })
  } else {
    for (const item of allContents.value) {
      const firstLine = item.content.split('\n').find((l) => l.trim()) ?? `第 ${item.num} 章`
      arr.push({ num: item.num, title: firstLine.trim().slice(0, 40) })
    }
  }
  return arr
})

async function loadChapterList() {
  loadingList.value = true
  try {
    const res = await generateApi.chapters(projectStore.filepath)
    chapters.value = res.data.chapters ?? []
  } catch {
    chapters.value = []
  } finally {
    loadingList.value = false
  }
}

async function loadChapter(num: number) {
  currentChapter.value = num
  loading.value = true
  try {
    const res = await generateApi.getChapter(num, projectStore.filepath)
    currentContent.value = res.data.content ?? ''
  } catch (e: unknown) {
    currentContent.value = `加载失败: ${(e as Error).message}`
  } finally {
    loading.value = false
  }
}

async function loadAllChapters() {
  loading.value = true
  allContents.value = []
  try {
    const withContent = chapters.value.filter((c) => c.has_final || c.has_draft)
    const results = await Promise.all(
      withContent.map(async (c) => {
        const res = await generateApi.getChapter(c.num, projectStore.filepath)
        return { num: c.num, content: res.data.content ?? '' }
      }),
    )
    allContents.value = results.sort((a, b) => a.num - b.num)
  } catch {
    /* ignore */
  } finally {
    loading.value = false
  }
}

function prevChapter() {
  if (!hasPrev.value) return
  loadChapter(chapters.value[currentIndex.value - 1].num)
}

function nextChapter() {
  if (!hasNext.value) return
  loadChapter(chapters.value[currentIndex.value + 1].num)
}

function adjustFontSize(delta: number) {
  const next = fontSize.value + delta
  if (next >= 12 && next <= 28) fontSize.value = next
}

function switchMode(m: 'single' | 'all') {
  mode.value = m
  if (m === 'all' && allContents.value.length === 0) loadAllChapters()
}

async function runFullSearch() {
  const q = searchQuery.value.trim()
  if (!q) {
    searchHits.value = []
    return
  }
  searching.value = true
  searchHits.value = []
  try {
    const withContent = chapters.value.filter((c) => c.has_final || c.has_draft)
    const needle = q.toLowerCase()
    const hits: SearchHit[] = []

    const fetchChapter = async (num: number): Promise<string> => {
      const existing = allContents.value.find((a) => a.num === num)
      if (existing) return existing.content
      try {
        const res = await generateApi.getChapter(num, projectStore.filepath)
        return res.data.content ?? ''
      } catch {
        return ''
      }
    }

    // Concurrent batching: 6 chapters at a time
    const CONCURRENCY = 6
    let idx = 0
    while (idx < withContent.length) {
      const batch = withContent.slice(idx, idx + CONCURRENCY)
      const texts = await Promise.all(batch.map((c) => fetchChapter(c.num)))
      batch.forEach((c, i) => {
        const text = texts[i]
        if (!text) return
        const lower = text.toLowerCase()
        let from = 0
        let count = 0
        while (from < text.length && count < 5) {
          const found = lower.indexOf(needle, from)
          if (found < 0) break
          const lineNo = text.slice(0, found).split('\n').length
          const start = Math.max(0, found - 30)
          const end = Math.min(text.length, found + q.length + 60)
          hits.push({
            num: c.num,
            line: lineNo,
            preview: text.slice(start, end).replace(/\s+/g, ' ').trim(),
            pos: found,
          })
          from = found + needle.length
          count++
        }
      })
      idx += CONCURRENCY
    }

    searchHits.value = hits
    if (!hits.length) feedback.info('未找到匹配项')
  } finally {
    searching.value = false
  }
}

async function jumpToHit(hit: SearchHit) {
  if (mode.value === 'all') {
    // Already loaded, scroll to chapter section
    await nextTick()
    const el = document.getElementById(`reader-chapter-${hit.num}`)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  } else {
    await loadChapter(hit.num)
  }
}

function copyChapter() {
  if (!currentContent.value) return
  navigator.clipboard.writeText(currentContent.value).then(
    () => feedback.success('✅ 已复制当前章节'),
    () => feedback.warning('剪贴板不可用'),
  )
}

function onKey(e: KeyboardEvent) {
  // Ignore when typing in inputs
  const t = e.target as HTMLElement | null
  if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return
  if (e.key === 'ArrowLeft' || e.key.toLowerCase() === 'k') {
    if (mode.value === 'single') { prevChapter(); e.preventDefault() }
  } else if (e.key === 'ArrowRight' || e.key.toLowerCase() === 'j') {
    if (mode.value === 'single') { nextChapter(); e.preventDefault() }
  } else if (e.key === '+' || e.key === '=') {
    adjustFontSize(1); e.preventDefault()
  } else if (e.key === '-' || e.key === '_') {
    adjustFontSize(-1); e.preventDefault()
  } else if (e.key === '/' && !e.ctrlKey && !e.metaKey) {
    sidePane.value = 'search'
    e.preventDefault()
    nextTick(() => {
      const input = document.getElementById('reader-search-input') as HTMLInputElement | null
      input?.focus()
    })
  }
}

onMounted(async () => {
  await projectStore.loadActive()
  await loadChapterList()
  window.addEventListener('keydown', onKey)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKey)
})

watch(() => projectStore.filepath, loadChapterList)
</script>

<template>
  <div class="module-page space-y-4">
    <h2 class="text-2xl font-bold" style="color: var(--color-ink)">📖 小说阅读</h2>

    <div class="module-toolbar">
      <div>
        <div class="module-kicker">Reader</div>
        <div class="module-subtitle">章节列表 / 标题目录 / 全文搜索；← / → 切换章节，/ 搜索，+ / − 字号。</div>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-[300px_minmax(0,1fr)] gap-4">
      <!-- 左侧：章节列表 / 目录 / 搜索 -->
      <div class="module-panel overflow-hidden module-aside-sticky flex flex-col" style="max-height: 75vh">
        <div class="rv-tabs">
          <button class="rv-tab" :class="{ active: sidePane === 'chapters' }" type="button" @click="sidePane = 'chapters'">章节</button>
          <button class="rv-tab" :class="{ active: sidePane === 'toc' }" type="button" @click="sidePane = 'toc'">目录</button>
          <button class="rv-tab" :class="{ active: sidePane === 'search' }" type="button" @click="sidePane = 'search'">搜索</button>
          <button @click="loadChapterList" class="ml-auto text-xs text-[var(--color-ink-light)] hover:text-[var(--color-leather)] px-2" type="button">🔄</button>
        </div>

        <!-- 章节列表 -->
        <div v-if="sidePane === 'chapters'" class="overflow-y-auto flex-1">
          <div v-if="loadingList" class="p-4 text-sm text-[var(--color-ink-light)] italic">加载中…</div>
          <div v-else-if="chapters.length === 0" class="p-4 text-sm text-[var(--color-ink-light)] italic">
            暂无章节，请先在创作工坊中生成章节。
          </div>
          <div v-else>
            <button
              v-for="ch in chapters"
              :key="ch.num"
              @click="loadChapter(ch.num)"
              class="w-full text-left px-4 py-2.5 text-sm transition-colors flex items-center justify-between gap-2 border-b border-[var(--color-parchment-dark)]"
              :class="currentChapter === ch.num ? 'bg-[var(--color-parchment)] font-medium text-[var(--color-leather)]' : 'text-[var(--color-ink)]'"
              type="button"
            >
              <span>第 {{ ch.num }} 章</span>
              <span class="text-xs px-1.5 py-0.5 rounded"
                :class="ch.has_final ? 'bg-[var(--color-success)] text-white' : ch.has_draft ? 'bg-[var(--color-warning)] text-white' : 'bg-[var(--color-parchment-dark)] text-[var(--color-ink-light)]'">
                {{ ch.has_final ? '定稿' : ch.has_draft ? '草稿' : '空' }}
              </span>
            </button>
          </div>
        </div>

        <!-- 标题目录 -->
        <div v-else-if="sidePane === 'toc'" class="overflow-y-auto flex-1 p-2">
          <div v-if="mode === 'single' && toc.length === 0" class="text-xs text-[var(--color-ink-light)] italic p-2">
            请先选择章节查看目录
          </div>
          <div v-else-if="mode === 'all' && toc.length === 0" class="text-xs text-[var(--color-ink-light)] italic p-2">
            正在加载全书内容…
          </div>
          <button
            v-for="entry in toc"
            :key="entry.num"
            @click="mode === 'all' ? jumpToHit({ num: entry.num, line: 1, preview: '', pos: 0 }) : loadChapter(entry.num)"
            class="w-full text-left px-2 py-1.5 hover:bg-[var(--color-parchment)] rounded-md flex items-baseline gap-2"
            type="button"
          >
            <span class="text-[10px] text-[var(--color-ink-light)] w-8 flex-shrink-0">{{ entry.num }}</span>
            <span class="text-sm truncate">{{ entry.title }}</span>
          </button>
        </div>

        <!-- 全文搜索 -->
        <div v-else class="overflow-y-auto flex-1 p-2 space-y-2">
          <div class="flex items-center gap-1">
            <input
              id="reader-search-input"
              v-model="searchQuery"
              @keyup.enter="runFullSearch"
              placeholder="搜索全书…（/ 聚焦）"
              class="flex-1 border border-[var(--color-parchment-darker)] rounded-md px-2 py-1.5 text-sm"
            />
            <button @click="runFullSearch" :disabled="searching" class="px-2 py-1.5 rounded-md border text-sm bg-white" type="button">
              {{ searching ? '…' : '搜' }}
            </button>
          </div>
          <div v-if="!searchHits.length && searchQuery && !searching" class="text-xs text-[var(--color-ink-light)] italic p-2">
            无结果
          </div>
          <button
            v-for="(h, i) in searchHits"
            :key="`${h.num}-${i}`"
            @click="jumpToHit(h)"
            class="w-full text-left px-2 py-2 rounded-md hover:bg-[var(--color-parchment)] border border-transparent"
            type="button"
          >
            <div class="flex items-center justify-between gap-2">
              <span class="text-sm font-medium">第 {{ h.num }} 章</span>
              <span class="text-[10px] text-[var(--color-ink-light)]">行 {{ h.line }}</span>
            </div>
            <div class="text-[11px] text-[var(--color-ink-light)] mt-0.5 line-clamp-2">{{ h.preview }}</div>
          </button>
        </div>
      </div>

      <!-- 右侧：阅读区 -->
      <div class="module-panel reader-canvas overflow-hidden flex flex-col">
        <!-- 工具栏 -->
        <div class="module-panel-header">
          <span class="font-medium text-sm text-[var(--color-leather)]">
            {{ mode === 'single' && currentChapter ? `第 ${currentChapter} 章` : mode === 'all' ? '全部章节' : '请选择章节' }}
          </span>
          <div class="flex items-center gap-3">
            <button v-if="mode === 'single' && currentChapter" @click="copyChapter" class="border border-[var(--color-parchment-darker)] rounded px-2 py-0.5 text-xs hover:bg-white" type="button" title="复制章节">
              📋
            </button>
            <div class="flex items-center gap-1">
              <button @click="adjustFontSize(-1)" class="border border-[var(--color-parchment-darker)] rounded px-2 py-0.5 text-xs hover:bg-white" type="button" title="缩小字号 (-)">A-</button>
              <span class="text-xs text-[var(--color-ink-light)] w-8 text-center">{{ fontSize }}</span>
              <button @click="adjustFontSize(1)" class="border border-[var(--color-parchment-darker)] rounded px-2 py-0.5 text-xs hover:bg-white" type="button" title="放大字号 (+)">A+</button>
            </div>
            <div class="flex rounded-md border border-[var(--color-parchment-darker)] overflow-hidden">
              <button @click="switchMode('single')" class="px-3 py-1 text-xs" :class="mode === 'single' ? 'bg-[var(--color-leather)] text-white' : 'hover:bg-[var(--color-parchment-dark)]'" type="button">单章</button>
              <button @click="switchMode('all')" class="px-3 py-1 text-xs" :class="mode === 'all' ? 'bg-[var(--color-leather)] text-white' : 'hover:bg-[var(--color-parchment-dark)]'" type="button">全部</button>
            </div>
          </div>
        </div>

        <!-- 内容区 -->
        <div class="flex-1 overflow-y-auto p-6" style="max-height: 75vh">
          <div v-if="loading" class="text-sm text-[var(--color-ink-light)] italic text-center py-8">加载中…</div>

          <template v-else-if="mode === 'single'">
            <div v-if="!currentChapter" class="text-sm text-[var(--color-ink-light)] italic text-center py-8">
              点击左侧章节开始阅读，按 ← / → 切换上下章
            </div>
            <div v-else
              class="mx-auto leading-relaxed whitespace-pre-wrap"
              :style="{ fontSize: fontSize + 'px', color: 'var(--color-ink)', maxWidth: '680px', fontFamily: 'var(--font-serif)', lineHeight: '1.8' }">
              {{ currentContent }}
            </div>
          </template>

          <template v-else>
            <div v-if="allContents.length === 0 && !loading" class="text-sm text-[var(--color-ink-light)] italic text-center py-8">
              暂无已有内容的章节
            </div>
            <div v-else class="mx-auto space-y-8" style="max-width: 680px">
              <div v-for="item in allContents" :key="item.num" :id="`reader-chapter-${item.num}`">
                <h3 class="text-lg font-bold mb-4 pb-2 border-b border-[var(--color-parchment-darker)]" style="color: var(--color-leather)">
                  第 {{ item.num }} 章
                </h3>
                <div class="leading-relaxed whitespace-pre-wrap" :style="{ fontSize: fontSize + 'px', color: 'var(--color-ink)', fontFamily: 'var(--font-serif)', lineHeight: '1.8' }">
                  {{ item.content }}
                </div>
              </div>
            </div>
          </template>
        </div>

        <!-- 底部导航 -->
        <div v-if="mode === 'single' && currentChapter"
          class="px-4 py-3 bg-[var(--color-parchment)] border-t border-[var(--color-parchment-darker)] flex items-center justify-between">
          <button @click="prevChapter" :disabled="!hasPrev" class="border border-[var(--color-parchment-darker)] rounded-md px-4 py-1.5 text-sm"
            :class="hasPrev ? 'hover:bg-white text-[var(--color-ink)]' : 'opacity-40 cursor-not-allowed text-[var(--color-ink-light)]'" type="button">← 上一章 (←/K)</button>
          <span class="text-xs text-[var(--color-ink-light)]">{{ currentIndex + 1 }} / {{ chapters.length }}</span>
          <button @click="nextChapter" :disabled="!hasNext" class="border border-[var(--color-parchment-darker)] rounded-md px-4 py-1.5 text-sm"
            :class="hasNext ? 'hover:bg-white text-[var(--color-ink)]' : 'opacity-40 cursor-not-allowed text-[var(--color-ink-light)]'" type="button">下一章 (→/J) →</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.rv-tabs { display: flex; gap: 2px; border-bottom: 1px solid var(--color-control-border); padding: 0 4px; }
.rv-tab { padding: 6px 10px; font-size: 12px; color: var(--color-ink-light); background: transparent; border: none; border-bottom: 2px solid transparent; cursor: pointer; }
.rv-tab.active { color: var(--color-ink); border-bottom-color: var(--color-leather); font-weight: 600; }
.rv-tab:hover { color: var(--color-ink); }
</style>
