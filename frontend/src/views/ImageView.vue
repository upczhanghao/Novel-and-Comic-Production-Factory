<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { imagesApi } from '@/api/client'
import { useConfigStore } from '@/stores/config'
import { useProjectStore } from '@/stores/project'

type ImageRow = {
  id: string
  path: string
  filename: string
  url: string
  download_url: string
  prompt?: string
  config_name?: string
  created_at?: string
  source_type?: string
  source_id?: string
}

type PromptItem = {
  id: string
  title: string
  prompt: string
  negative_prompt?: string
  source_type?: string
  source_id?: string
}

const configStore = useConfigStore()
const projectStore = useProjectStore()

const selectedConfig = ref('')
const prompt = ref('')
const generating = ref(false)
const message = ref('')
const currentImage = ref<ImageRow | null>(null)
const gallery = ref<ImageRow[]>([])
const promptQueue = ref<PromptItem[]>([])
const selectedPrompt = ref<PromptItem | null>(null)
const saveDir = ref('')

const filepath = computed(() => projectStore.filepath || './output')
const canGenerate = computed(() => Boolean(selectedConfig.value && prompt.value.trim() && !generating.value))

async function loadGallery() {
  const res = await imagesApi.list(filepath.value)
  gallery.value = res.data.images ?? []
  saveDir.value = res.data.save_dir ?? saveDir.value
}

async function loadPrompts() {
  const res = await imagesApi.prompts(filepath.value)
  promptQueue.value = res.data.items ?? []
  saveDir.value = res.data.save_dir ?? saveDir.value
}

function usePrompt(item: PromptItem) {
  selectedPrompt.value = item
  prompt.value = item.negative_prompt
    ? `${item.prompt}\n\n负向提示词：${item.negative_prompt}`
    : item.prompt
}

async function generateImage() {
  if (!canGenerate.value) return
  generating.value = true
  message.value = '正在生成图片...'
  try {
    const res = await imagesApi.generate({
      config_name: selectedConfig.value,
      prompt: prompt.value,
      filepath: filepath.value,
      source_type: selectedPrompt.value?.source_type ?? 'image_module',
      source_id: selectedPrompt.value?.source_id ?? selectedPrompt.value?.id ?? '',
    })
    currentImage.value = {
      id: res.data.id,
      path: res.data.path,
      filename: res.data.filename,
      url: res.data.url,
      download_url: res.data.download_url,
      prompt: res.data.prompt,
      config_name: res.data.config_name,
      source_type: res.data.source_type,
      source_id: res.data.source_id,
    }
    message.value = res.data.message
    await loadGallery()
  } catch (e: unknown) {
    message.value = `❌ ${(e as Error).message}`
  } finally {
    generating.value = false
  }
}

async function deletePromptItem(item: PromptItem) {
  try {
    const res = await imagesApi.deletePrompt(item.id, filepath.value)
    promptQueue.value = res.data.items ?? []
    saveDir.value = res.data.save_dir ?? saveDir.value
    if (selectedPrompt.value?.id === item.id) {
      selectedPrompt.value = null
      prompt.value = ''
    }
    message.value = res.data.message
  } catch (e: unknown) {
    message.value = `❌ ${(e as Error).message}`
  }
}

async function deleteImageRecord(img: ImageRow) {
  try {
    const res = await imagesApi.deleteRecord(img.id, filepath.value, true)
    message.value = res.data.message
    if (currentImage.value?.id === img.id || currentImage.value?.path === img.path) currentImage.value = null
    await loadGallery()
  } catch (e: unknown) {
    message.value = `❌ ${(e as Error).message}`
  }
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
        <div class="module-subtitle">集中处理待生成提示词、参数编辑、图片预览与生成记录。</div>
      </div>
      <div class="module-action-row">
        <button @click="loadPrompts" class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm bg-white" type="button">刷新提示词</button>
        <button @click="loadGallery" class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm bg-white" type="button">刷新记录</button>
        <router-link to="/config" class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm bg-white hover:bg-[var(--color-surface-muted)] transition-colors">
          管理图片配置
        </router-link>
      </div>
    </div>

    <section class="module-grid three">
      <aside class="module-panel p-4 space-y-3 module-aside-sticky">
        <div class="flex items-center justify-between">
          <div>
            <h3 class="font-semibold text-[var(--color-ink)]">待生成提示词</h3>
            <p class="text-xs text-[var(--color-ink-light)] mt-1">{{ promptQueue.length }} 个任务</p>
          </div>
        </div>
        <div class="space-y-2 max-h-[calc(100vh-220px)] overflow-auto pr-1">
          <div
            v-for="item in promptQueue"
            :key="item.id"
            @click="usePrompt(item)"
            class="w-full module-list-item px-3 py-2.5 cursor-pointer"
            :class="selectedPrompt?.id === item.id ? 'active' : ''"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0 text-left">
                <div class="text-sm font-semibold text-[var(--color-ink)] truncate">{{ item.title }}</div>
                <div class="text-xs text-[var(--color-ink-light)] line-clamp-2 mt-1">{{ item.prompt }}</div>
              </div>
              <button
                @click.stop="deletePromptItem(item)"
                class="shrink-0 px-2 py-1 rounded border border-red-200 text-[10px] text-red-600 hover:bg-red-50"
                type="button"
              >
                删除
              </button>
            </div>
          </div>
          <div v-if="!promptQueue.length" class="text-sm text-[var(--color-ink-light)] rounded-md border border-dashed border-[var(--color-parchment-darker)] p-4 text-center">暂无导入提示词。</div>
        </div>
      </aside>

      <main class="module-panel p-4 min-h-[620px] flex flex-col">
        <div v-if="currentImage" class="space-y-3">
          <img :src="currentImage.url" :alt="currentImage.filename" class="max-h-[760px] w-full object-contain rounded-md border border-[var(--color-parchment-darker)] bg-[var(--color-surface-muted)]" />
          <div class="flex items-center justify-between gap-3 flex-wrap">
            <div class="text-sm text-[var(--color-ink-light)] break-all">{{ currentImage.filename }}</div>
            <a :href="currentImage.download_url" class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm bg-white" target="_blank">下载图片</a>
          </div>
        </div>
        <div v-else class="flex-1 min-h-[520px] grid place-items-center text-center text-sm text-[var(--color-ink-light)] rounded-md border border-dashed border-[var(--color-parchment-darker)] bg-[var(--color-surface-muted)]">
          <div>
            <div class="text-4xl mb-3">✦</div>
            <div class="font-semibold text-[var(--color-ink)]">选择提示词并生成图片</div>
            <div class="mt-1">生成结果会在这里预览。</div>
          </div>
        </div>
      </main>

      <aside class="space-y-4 module-aside-sticky">
        <div class="module-panel p-4 space-y-4">
          <div>
            <h3 class="font-semibold text-[var(--color-ink)]">生成参数</h3>
            <p class="text-xs text-[var(--color-ink-light)] mt-1">编辑提示词并提交到图片模型。</p>
          </div>
          <div>
            <label class="block text-xs text-[var(--color-ink-light)] mb-1">图片生成配置</label>
            <select v-model="selectedConfig" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm">
              <option value="">请选择配置</option>
              <option v-for="c in configStore.imageChoices" :key="c" :value="c">{{ c }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs text-[var(--color-ink-light)] mb-1">图片提示词</label>
            <textarea v-model="prompt" rows="9" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm resize-y" />
          </div>
          <div class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-xs text-[var(--color-ink-light)] break-all bg-[var(--color-surface-muted)]">
            {{ saveDir || `${filepath}/images` }}
          </div>
          <div v-if="message" class="text-sm" :class="message.startsWith('✅') ? 'text-green-700' : message.startsWith('❌') ? 'text-red-600' : 'text-[var(--color-ink-light)]'">
            {{ message }}
          </div>
          <button
            @click="generateImage"
            :disabled="!canGenerate"
            class="w-full px-5 py-2 rounded-md text-sm font-semibold disabled:opacity-50"
            style="background-color: var(--color-leather); color: var(--color-parchment)"
            type="button"
          >
            {{ generating ? '生成中...' : '生成图片' }}
          </button>
        </div>

        <div class="module-panel p-4">
          <div class="flex items-center justify-between mb-3">
            <div>
              <h3 class="font-semibold text-[var(--color-ink)]">生成记录</h3>
              <p class="text-xs text-[var(--color-ink-light)] mt-1">{{ gallery.length }} 张图片</p>
            </div>
          </div>
          <div class="grid grid-cols-2 gap-2 max-h-[440px] overflow-auto">
            <div
              v-for="img in gallery"
              :key="img.id || img.path"
              @click="currentImage = img"
              class="text-left module-list-item overflow-hidden cursor-pointer"
            >
              <img :src="img.url" :alt="img.filename" class="w-full aspect-[2/3] object-cover bg-[var(--color-parchment)]" />
              <div class="p-1.5 space-y-1">
                <div class="text-[10px] text-[var(--color-ink-light)] truncate">{{ img.filename }}</div>
                <button
                  @click.stop="deleteImageRecord(img)"
                  class="w-full px-2 py-1 rounded border border-red-200 text-[10px] text-red-600 hover:bg-red-50"
                  type="button"
                >
                  删除
                </button>
              </div>
            </div>
            <div v-if="!gallery.length" class="col-span-2 text-sm text-[var(--color-ink-light)]">暂无图片</div>
          </div>
        </div>
      </aside>
    </section>
  </div>
</template>
