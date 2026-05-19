<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { imagesApi } from '@/api/client'
import { useConfigStore } from '@/stores/config'
import { useProjectStore } from '@/stores/project'

type ImageRow = {
  path: string
  filename: string
  url: string
  download_url: string
  prompt?: string
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
      path: res.data.path,
      filename: res.data.filename,
      url: res.data.url,
      download_url: res.data.download_url,
      prompt: res.data.prompt,
    }
    message.value = res.data.message
    await loadGallery()
  } catch (e: unknown) {
    message.value = `❌ ${(e as Error).message}`
  } finally {
    generating.value = false
  }
}

onMounted(async () => {
  await Promise.all([configStore.loadAll(), projectStore.loadActive()])
  if (configStore.imageChoices.length) selectedConfig.value = configStore.imageChoices[0]
  await Promise.all([loadGallery(), loadPrompts()])
})
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 py-6 space-y-6">
    <div class="flex items-center justify-between gap-3 flex-wrap">
      <h2 class="text-2xl font-bold" style="color: var(--color-ink)">图片生成</h2>
      <router-link to="/config" class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm hover:bg-white transition-colors">
        管理图片配置
      </router-link>
    </div>

    <section class="rounded-xl border border-[var(--color-parchment-darker)] bg-white p-4 space-y-4">
      <div class="grid grid-cols-1 md:grid-cols-[240px_1fr] gap-3">
        <div>
          <label class="block text-xs text-[var(--color-ink-light)] mb-1">图片生成配置</label>
          <select v-model="selectedConfig" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm">
            <option value="">请选择配置</option>
            <option v-for="c in configStore.imageChoices" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-[var(--color-ink-light)] mb-1">图片保存目录</label>
          <div class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm text-[var(--color-ink-light)]">
            {{ saveDir || `${filepath}/images` }}
          </div>
        </div>
      </div>

      <div>
        <label class="block text-xs text-[var(--color-ink-light)] mb-1">图片提示词</label>
        <textarea v-model="prompt" rows="7" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm resize-y" />
      </div>

      <div class="flex items-center justify-between gap-3 flex-wrap">
        <div v-if="message" class="text-sm" :class="message.startsWith('✅') ? 'text-green-700' : message.startsWith('❌') ? 'text-red-600' : 'text-[var(--color-ink-light)]'">
          {{ message }}
        </div>
        <div v-else class="text-sm text-[var(--color-ink-light)]">生成后的图片会保存在项目文件夹内的 images/项目名称 目录。</div>
        <button
          @click="generateImage"
          :disabled="!canGenerate"
          class="px-5 py-2 rounded-md text-sm font-semibold disabled:opacity-50"
          style="background-color: var(--color-leather); color: var(--color-parchment)"
          type="button"
        >
          {{ generating ? '生成中...' : '生成图片' }}
        </button>
      </div>
    </section>

    <section class="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px] gap-5">
      <div class="rounded-xl border border-[var(--color-parchment-darker)] bg-white p-4 min-h-[420px]">
        <div v-if="currentImage" class="space-y-3">
          <img :src="currentImage.url" :alt="currentImage.filename" class="max-h-[720px] w-full object-contain rounded-md border border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]" />
          <div class="flex items-center justify-between gap-3 flex-wrap">
            <div class="text-sm text-[var(--color-ink-light)] break-all">{{ currentImage.filename }}</div>
            <a :href="currentImage.download_url" class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm" target="_blank">下载图片</a>
          </div>
        </div>
        <div v-else class="h-full min-h-[360px] flex items-center justify-center text-sm text-[var(--color-ink-light)]">
          暂无预览
        </div>
      </div>

      <aside class="space-y-4">
        <div class="rounded-xl border border-[var(--color-parchment-darker)] bg-white p-4">
          <div class="flex items-center justify-between mb-3">
            <h3 class="font-semibold text-[var(--color-leather)]">待生成提示词</h3>
            <button @click="loadPrompts" class="px-2 py-1 rounded border border-[var(--color-parchment-darker)] text-xs" type="button">刷新</button>
          </div>
          <div class="space-y-2 max-h-72 overflow-auto">
            <button
              v-for="item in promptQueue"
              :key="item.id"
              @click="usePrompt(item)"
              class="w-full text-left rounded-md border border-[var(--color-parchment-darker)] px-2 py-2 hover:border-[var(--color-leather)] transition-colors"
              type="button"
            >
              <div class="text-xs font-semibold text-[var(--color-ink)] truncate">{{ item.title }}</div>
              <div class="text-[10px] text-[var(--color-ink-light)] truncate">{{ item.prompt }}</div>
            </button>
            <div v-if="!promptQueue.length" class="text-sm text-[var(--color-ink-light)]">暂无导入提示词。</div>
          </div>
        </div>

        <div class="rounded-xl border border-[var(--color-parchment-darker)] bg-white p-4">
          <div class="flex items-center justify-between mb-3">
            <h3 class="font-semibold text-[var(--color-leather)]">生成记录</h3>
            <button @click="loadGallery" class="px-2 py-1 rounded border border-[var(--color-parchment-darker)] text-xs" type="button">刷新</button>
          </div>
          <div class="grid grid-cols-2 gap-2 max-h-[420px] overflow-auto">
            <button
              v-for="img in gallery"
              :key="img.path"
              @click="currentImage = img"
              class="text-left border border-[var(--color-parchment-darker)] rounded-md overflow-hidden hover:border-[var(--color-leather)] transition-colors"
              type="button"
            >
              <img :src="img.url" :alt="img.filename" class="w-full aspect-[2/3] object-cover bg-[var(--color-parchment)]" />
              <div class="p-1 text-[10px] text-[var(--color-ink-light)] truncate">{{ img.filename }}</div>
            </button>
            <div v-if="!gallery.length" class="col-span-2 text-sm text-[var(--color-ink-light)]">暂无图片</div>
          </div>
        </div>
      </aside>
    </section>
  </div>
</template>
