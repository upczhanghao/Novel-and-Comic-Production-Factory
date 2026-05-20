<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { imagesApi } from '@/api/client'
import { useConfigStore } from '@/stores/config'
import { useProjectStore } from '@/stores/project'
import { useFeedbackStore } from '@/stores/feedback'
import { useTasksStore } from '@/stores/tasks'
import PromptEditor from '@/components/image/PromptEditor.vue'
import ImageErrorBanner from '@/components/image/ImageErrorBanner.vue'
import QueueTab, { type PromptItem } from '@/components/image/QueueTab.vue'
import RecordsTab from '@/components/image/RecordsTab.vue'
import type { ImageRecord } from '@/components/image/RecordCard.vue'

const configStore = useConfigStore()
const projectStore = useProjectStore()
const feedback = useFeedbackStore()
const tasks = useTasksStore()

type Tab = 'queue' | 'records'
const TAB_KEY = 'nw.imageView.tab'
const initialTab = (localStorage.getItem(TAB_KEY) as Tab) || 'queue'
const tab = ref<Tab>(initialTab === 'records' ? 'records' : 'queue')
watch(tab, (v) => localStorage.setItem(TAB_KEY, v))

const selectedConfig = ref('')
const positivePrompt = ref('')
const negativePrompt = ref('')
const generating = ref(false)
const lastError = ref('')
const currentImage = ref<ImageRecord | null>(null)
const gallery = ref<ImageRecord[]>([])
const promptQueue = ref<PromptItem[]>([])
const selectedPrompt = ref<PromptItem | null>(null)
const saveDir = ref('')

const queueSelected = ref<string[]>([])
const recordsSelected = ref<string[]>([])
const cancelBatch = ref(false)
const concurrency = ref(3)

const filepath = computed(() => projectStore.filepath || './output')
const canGenerate = computed(
  () => Boolean(selectedConfig.value && positivePrompt.value.trim() && !generating.value),
)
const noConfig = computed(() => !configStore.imageChoices.length)
const configHint = computed(() => {
  if (noConfig.value) return '尚未配置图片模型，前往「模型配置」添加 OpenAI / MirrorStages 凭据'
  if (!selectedConfig.value) return '请选择一个图片配置；首个可用配置已为你预选'
  return ''
})

function buildBody(prompt: string, opts?: { sourceType?: string; sourceId?: string }) {
  return {
    config_name: selectedConfig.value,
    prompt,
    filepath: filepath.value,
    source_type: opts?.sourceType ?? 'image_module',
    source_id: opts?.sourceId ?? '',
  }
}

function combinedPrompt(p: string, n?: string) {
  return n?.trim() ? `${p}\n\n负向提示词：${n}` : p
}

async function loadGallery() {
  try {
    const res = await imagesApi.list(filepath.value)
    gallery.value = res.data.images ?? []
    saveDir.value = res.data.save_dir ?? saveDir.value
  } catch (e) {
    feedback.error('加载生成记录失败', (e as Error).message)
  }
}

async function loadPrompts() {
  try {
    const res = await imagesApi.prompts(filepath.value)
    promptQueue.value = res.data.items ?? []
    saveDir.value = res.data.save_dir ?? saveDir.value
  } catch (e) {
    feedback.error('加载待生成队列失败', (e as Error).message)
  }
}

function usePrompt(item: PromptItem) {
  selectedPrompt.value = item
  positivePrompt.value = item.prompt
  negativePrompt.value = item.negative_prompt ?? ''
  lastError.value = ''
}

async function copyText(text: string, label = '已复制') {
  try {
    await navigator.clipboard.writeText(text)
    feedback.info(label)
  } catch {
    feedback.warning('无法访问剪贴板')
  }
}

function copyPromptItem(item: PromptItem) {
  copyText(combinedPrompt(item.prompt, item.negative_prompt), '已复制提示词')
}
function copyPromptParams(item: PromptItem) {
  const obj = { id: item.id, source_type: item.source_type, source_id: item.source_id, config_name: selectedConfig.value }
  copyText(JSON.stringify(obj, null, 2), '已复制参数')
}
function copyRecordPrompt(r: ImageRecord) {
  copyText(r.prompt ?? '', '已复制提示词')
}
function copyRecordParams(r: ImageRecord) {
  const obj = { id: r.id, model: r.model, size: r.size, provider: r.provider, config_name: r.config_name, source_type: r.source_type, source_id: r.source_id }
  copyText(JSON.stringify(obj, null, 2), '已复制参数')
}

async function generateImage() {
  if (!canGenerate.value) return
  generating.value = true
  lastError.value = ''
  try {
    const res = await imagesApi.generate(
      buildBody(combinedPrompt(positivePrompt.value, negativePrompt.value), {
        sourceType: selectedPrompt.value?.source_type ?? 'image_module',
        sourceId: selectedPrompt.value?.source_id ?? selectedPrompt.value?.id ?? '',
      }),
    )
    currentImage.value = res.data as ImageRecord
    feedback.success(res.data.message ?? '✅ 图片已生成')
    await loadGallery()
  } catch (e) {
    const msg = (e as Error).message
    lastError.value = msg
    feedback.error('图片生成失败', msg)
  } finally {
    generating.value = false
  }
}

async function batchGenerate(items: PromptItem[]) {
  if (!items.length) return
  if (!selectedConfig.value) {
    feedback.warning('请先选择图片配置')
    return
  }
  if (!confirm(`将使用配置「${selectedConfig.value}」生成 ${items.length} 张图片（并发 ${concurrency.value}）？`)) return

  cancelBatch.value = false
  generating.value = true
  let ok = 0
  let fail = 0
  const total = items.length
  let nextIdx = 0
  let completed = 0

  async function worker() {
    while (!cancelBatch.value && nextIdx < total) {
      const i = nextIdx++
      const item = items[i]
      const taskId = `image-batch-${Date.now()}-${item.id}`
      tasks.register(taskId, `生成 ${item.title || item.id}`, () => {
        cancelBatch.value = true
      })
      try {
        tasks.update(taskId, `${i + 1}/${total} 生成中…`, Math.round(((i + 0.5) / total) * 100))
        const res = await imagesApi.generate(
          buildBody(combinedPrompt(item.prompt, item.negative_prompt), {
            sourceType: item.source_type ?? 'custom',
            sourceId: item.source_id ?? item.id,
          }),
        )
        tasks.update(taskId, '完成', 100)
        tasks.finish(taskId, 'done')
        ok++
        // 实时插入到 gallery 顶部，不必等所有任务完成
        const rec = res.data as ImageRecord
        if (rec && rec.url) {
          const existing = gallery.value.findIndex((g) => g.id === rec.id)
          if (existing >= 0) gallery.value.splice(existing, 1)
          gallery.value = [rec, ...gallery.value]
        }
      } catch (e) {
        tasks.finish(taskId, 'error')
        fail++
        feedback.error(`「${item.title || item.id}」生成失败`, (e as Error).message)
      } finally {
        completed++
      }
    }
  }

  const workers = Array.from({ length: Math.min(concurrency.value, total) }, () => worker())
  await Promise.all(workers)

  generating.value = false
  cancelBatch.value = false
  feedback.success(`批量生成完成：成功 ${ok}，失败 ${fail}`)
  // 最终再做一次完整刷新以补齐元数据
  await loadGallery()
}

async function batchDeletePromptItems(items: PromptItem[]) {
  if (!items.length) return
  if (!confirm(`删除 ${items.length} 条提示词？`)) return
  const backup = [...items]
  try {
    const res = await imagesApi.batchDeletePrompts(items.map((i) => i.id), filepath.value)
    promptQueue.value = res.data.items ?? []
    queueSelected.value = []
    feedback.success(res.data.message ?? '✅ 已删除', {
      undoFn: async () => {
        await imagesApi.importPrompts({
          filepath: filepath.value,
          items: backup.map((i) => ({
            id: i.id, title: i.title, prompt: i.prompt,
            negative_prompt: i.negative_prompt ?? '',
            source_type: i.source_type ?? 'custom',
            source_id: i.source_id ?? i.id,
          })),
          replace: false,
        })
        await loadPrompts()
      },
    })
  } catch (e) {
    feedback.error('批量删除失败', (e as Error).message)
  }
}

async function deleteOnePrompt(item: PromptItem) {
  await batchDeletePromptItems([item])
}

async function batchDeleteRecords(records: ImageRecord[]) {
  if (!records.length) return
  if (!confirm(`删除 ${records.length} 张图片记录及文件？`)) return
  try {
    await imagesApi.batchDeleteRecords(records.map((r) => r.id), filepath.value, true)
    recordsSelected.value = []
    if (currentImage.value && records.some((r) => r.id === currentImage.value!.id)) {
      currentImage.value = null
    }
    feedback.success(`✅ 已删除 ${records.length} 张图片`)
    await loadGallery()
  } catch (e) {
    feedback.error('批量删除失败', (e as Error).message)
  }
}

async function deleteOneRecord(record: ImageRecord) {
  if (!confirm(`删除「${record.filename || record.id}」及文件？`)) return
  try {
    await imagesApi.deleteRecord(record.id, filepath.value, true)
    if (currentImage.value?.id === record.id) currentImage.value = null
    feedback.success('✅ 已删除')
    await loadGallery()
  } catch (e) {
    feedback.error('删除失败', (e as Error).message)
  }
}

async function retryRecord(record: ImageRecord) {
  if (!record.prompt) {
    feedback.warning('该记录没有保存原始提示词，无法重试')
    return
  }
  const cfg = record.config_name && configStore.imageChoices.includes(record.config_name)
    ? record.config_name
    : selectedConfig.value
  if (!cfg) {
    feedback.warning('未找到可用配置，请先在右侧选择')
    return
  }
  const taskId = `image-retry-${record.id}-${Date.now()}`
  tasks.register(taskId, `重试 ${record.filename || record.id}`)
  try {
    await imagesApi.generate({
      config_name: cfg,
      prompt: record.prompt,
      filepath: filepath.value,
      source_type: record.source_type ?? 'image_module',
      source_id: record.source_id ?? '',
    })
    tasks.finish(taskId, 'done')
    feedback.success('✅ 重试完成')
    await loadGallery()
  } catch (e) {
    tasks.finish(taskId, 'error')
    feedback.error('重试失败', (e as Error).message)
  }
}

async function batchRetryRecords(records: ImageRecord[]) {
  const usable = records.filter((r) => r.prompt)
  if (!usable.length) {
    feedback.warning('所选记录均无原始提示词')
    return
  }
  if (usable.length < records.length) {
    feedback.info(`${records.length - usable.length} 条无提示词将跳过`)
  }
  cancelBatch.value = false
  generating.value = true
  let ok = 0; let fail = 0
  let nextIdx = 0
  const total = usable.length

  async function worker() {
    while (!cancelBatch.value && nextIdx < total) {
      const i = nextIdx++
      const r = usable[i]
      const taskId = `image-retry-batch-${Date.now()}-${r.id}`
      tasks.register(taskId, `重试 ${r.filename || r.id}`, () => { cancelBatch.value = true })
      try {
        tasks.update(taskId, `${i + 1}/${total}`, Math.round(((i + 0.5) / total) * 100))
        const res = await imagesApi.generate({
          config_name: r.config_name && configStore.imageChoices.includes(r.config_name) ? r.config_name : selectedConfig.value,
          prompt: r.prompt!,
          filepath: filepath.value,
          source_type: r.source_type ?? 'image_module',
          source_id: r.source_id ?? '',
        })
        tasks.finish(taskId, 'done')
        ok++
        const rec = res.data as ImageRecord
        if (rec && rec.url) {
          const existing = gallery.value.findIndex((g) => g.id === rec.id)
          if (existing >= 0) gallery.value.splice(existing, 1)
          gallery.value = [rec, ...gallery.value]
        }
      } catch (e) {
        tasks.finish(taskId, 'error')
        fail++
        feedback.error(`「${r.filename || r.id}」重试失败`, (e as Error).message)
      }
    }
  }

  const workers = Array.from({ length: Math.min(concurrency.value, total) }, () => worker())
  await Promise.all(workers)

  generating.value = false
  feedback.success(`批量重试完成：成功 ${ok}，失败 ${fail}`)
  recordsSelected.value = []
  await loadGallery()
}

function viewRecord(r: ImageRecord) {
  currentImage.value = r
}

onMounted(async () => {
  await Promise.all([configStore.loadAll(), projectStore.loadActive()])
  if (configStore.imageChoices.length) selectedConfig.value = configStore.imageChoices[0]
  await Promise.all([loadGallery(), loadPrompts()])
})
</script>

<template>
  <div class="module-page space-y-4">
    <div class="module-toolbar">
      <h2 class="text-2xl font-bold" style="color: var(--color-ink)">图片生成</h2>
      <div>
        <div class="module-kicker">Image Lab</div>
        <div class="module-subtitle">待生成队列与生成记录分两个标签页管理；支持批量生成、重试、过滤与撤销。</div>
      </div>
      <div class="module-action-row">
        <button @click="loadPrompts" class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm bg-white" type="button">刷新队列</button>
        <button @click="loadGallery" class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm bg-white" type="button">刷新记录</button>
        <router-link to="/config" class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm bg-white hover:bg-[var(--color-surface-muted)] transition-colors">
          管理图片配置
        </router-link>
      </div>
    </div>

    <section class="module-grid two">
      <main class="module-panel p-4 min-h-[480px] flex flex-col gap-3">
        <div class="iv-tabs">
          <button
            class="iv-tab"
            :class="{ active: tab === 'queue' }"
            type="button"
            @click="tab = 'queue'"
          >
            待生成队列
            <span class="iv-badge">{{ promptQueue.length }}</span>
          </button>
          <button
            class="iv-tab"
            :class="{ active: tab === 'records' }"
            type="button"
            @click="tab = 'records'"
          >
            生成记录
            <span class="iv-badge">{{ gallery.length }}</span>
          </button>
        </div>

        <QueueTab
          v-if="tab === 'queue'"
          :items="promptQueue"
          v-model:selected="queueSelected"
          :active-id="selectedPrompt?.id ?? null"
          :busy="generating"
          @use="usePrompt"
          @copyPrompt="copyPromptItem"
          @copyParams="copyPromptParams"
          @delete="deleteOnePrompt"
          @batchGenerate="batchGenerate"
          @batchDelete="batchDeletePromptItems"
        />

        <RecordsTab
          v-else
          :records="gallery"
          v-model:selected="recordsSelected"
          :busy="generating"
          @view="viewRecord"
          @retry="retryRecord"
          @delete="deleteOneRecord"
          @copyPrompt="copyRecordPrompt"
          @copyParams="copyRecordParams"
          @batchRetry="batchRetryRecords"
          @batchDelete="batchDeleteRecords"
        />
      </main>

      <aside class="space-y-4 module-aside-sticky">
        <div class="module-panel p-4 space-y-3">
          <div>
            <h3 class="font-semibold text-[var(--color-ink)]">生成参数</h3>
            <p class="text-xs text-[var(--color-ink-light)] mt-1">编辑提示词后点击生成；选中队列项可自动回填。</p>
          </div>

          <div v-if="configHint" class="iv-config-hint" :class="{ warn: noConfig }">
            <div class="flex-1">{{ configHint }}</div>
            <router-link v-if="noConfig" to="/config" class="iv-hint-link">前往配置</router-link>
          </div>

          <div>
            <label class="block text-xs text-[var(--color-ink-light)] mb-1">图片生成配置</label>
            <select v-model="selectedConfig" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm">
              <option value="">请选择配置</option>
              <option v-for="c in configStore.imageChoices" :key="c" :value="c">{{ c }}</option>
            </select>
          </div>

          <div>
            <label class="block text-xs text-[var(--color-ink-light)] mb-1">批量并发数</label>
            <select v-model.number="concurrency" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm">
              <option :value="1">1（顺序执行）</option>
              <option :value="2">2</option>
              <option :value="3">3（推荐）</option>
              <option :value="5">5</option>
              <option :value="8">8</option>
              <option :value="10">10</option>
            </select>
          </div>

          <PromptEditor
            v-model="positivePrompt"
            v-model:negative="negativePrompt"
            :disabled="generating"
          />

          <div v-if="selectedPrompt" class="text-[11px] text-[var(--color-ink-light)] truncate">
            源自队列项：{{ selectedPrompt.title || selectedPrompt.id }}
          </div>

          <div class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-xs text-[var(--color-ink-light)] break-all bg-[var(--color-surface-muted)]">
            {{ saveDir || `${filepath}/images` }}
          </div>

          <ImageErrorBanner v-if="lastError" :message="lastError" @dismiss="lastError = ''" />

          <button
            @click="generateImage"
            :disabled="!canGenerate"
            class="w-full px-5 py-2 rounded-md text-sm font-semibold disabled:opacity-50"
            style="background-color: var(--color-leather); color: var(--color-parchment)"
            type="button"
          >
            {{ generating ? '生成中…' : '生成图片' }}
          </button>
        </div>

        <div v-if="currentImage" class="module-panel p-3 space-y-2">
          <img :src="currentImage.url" :alt="currentImage.filename" class="w-full max-h-[420px] object-contain rounded-md border border-[var(--color-parchment-darker)] bg-[var(--color-surface-muted)]" />
          <div class="text-[11px] text-[var(--color-ink-light)] break-all">{{ currentImage.filename }}</div>
          <div class="flex gap-2">
            <a :href="currentImage.download_url || currentImage.url" target="_blank" class="flex-1 text-center px-3 py-1.5 rounded-md border border-[var(--color-parchment-darker)] text-xs bg-white">下载</a>
            <button type="button" class="flex-1 px-3 py-1.5 rounded-md border border-[var(--color-parchment-darker)] text-xs bg-white" @click="retryRecord(currentImage)">重试</button>
          </div>
        </div>
      </aside>
    </section>
  </div>
</template>

<style scoped>
.iv-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--color-control-border); padding-bottom: 0; }
.iv-tab { display: inline-flex; align-items: center; gap: 6px; padding: 8px 14px; font-size: 13px; font-weight: 500; color: var(--color-ink-light); background: transparent; border: none; border-bottom: 2px solid transparent; margin-bottom: -1px; cursor: pointer; transition: color 0.15s, border-color 0.15s; }
.iv-tab:hover { color: var(--color-ink); }
.iv-tab.active { color: var(--color-ink); border-bottom-color: var(--color-leather); font-weight: 600; }
.iv-badge { padding: 0 6px; min-width: 18px; height: 16px; line-height: 16px; text-align: center; font-size: 10px; border-radius: 999px; background: var(--color-surface-muted); color: var(--color-ink-light); }
.iv-tab.active .iv-badge { background: var(--color-leather); color: var(--color-parchment); }
.iv-config-hint { display: flex; align-items: center; gap: 8px; padding: 6px 10px; font-size: 11px; color: var(--color-ink-light); background: var(--color-surface-muted); border-radius: 6px; border: 1px solid var(--color-control-border); }
.iv-config-hint.warn { background: #fffbeb; border-color: #fde68a; color: #78350f; }
.iv-hint-link { padding: 2px 8px; font-size: 11px; border-radius: 4px; background: var(--color-ink); color: white; text-decoration: none; flex-shrink: 0; }
</style>
