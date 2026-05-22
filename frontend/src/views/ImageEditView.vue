<script setup lang="ts">
import { computed, ref } from 'vue'
import { imagesApi } from '@/api/client'
import { useConfigStore } from '@/stores/config'
import { useProjectStore } from '@/stores/project'
import { useFeedbackStore } from '@/stores/feedback'
import { useTasksStore } from '@/stores/tasks'

const configStore = useConfigStore()
const projectStore = useProjectStore()
const feedback = useFeedbackStore()
const tasks = useTasksStore()

const filepath = computed(() => projectStore.filepath || './output')

const selectedConfig = ref('')
const prompt = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const sourceFile = ref<File | null>(null)
const sourcePreview = ref<string>('')
const sourceB64 = ref<string>('')

const running = ref(false)
const resultUrl = ref('')
const resultFilename = ref('')
const lastError = ref('')

const noConfig = computed(() => !configStore.imageChoices.length)
const canSubmit = computed(
  () => Boolean(selectedConfig.value && prompt.value.trim() && sourceB64.value && !running.value),
)

if (!selectedConfig.value && configStore.imageChoices.length) {
  selectedConfig.value = configStore.imageChoices[0]
}

function readFileAsBase64(file: File): Promise<{ b64: string; dataUrl: string }> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const dataUrl = String(reader.result || '')
      const comma = dataUrl.indexOf(',')
      resolve({ b64: comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl, dataUrl })
    }
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

async function onFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  const f = target.files?.[0]
  if (!f) return
  if (!/^image\/(png|jpe?g|webp)$/i.test(f.type)) {
    feedback.warning('仅支持 PNG / JPEG / WebP 图片')
    target.value = ''
    return
  }
  sourceFile.value = f
  const { b64, dataUrl } = await readFileAsBase64(f)
  sourceB64.value = b64
  sourcePreview.value = dataUrl
}

async function submit() {
  if (!canSubmit.value) return
  running.value = true
  lastError.value = ''
  resultUrl.value = ''
  const taskId = `image-edit-local-${Date.now()}`
  tasks.register(taskId, `编辑 ${sourceFile.value?.name || '本地图片'}`)
  try {
    const res = await imagesApi.edit({
      config_name: selectedConfig.value,
      prompt: prompt.value.trim(),
      filepath: filepath.value,
      source_image_b64: sourceB64.value,
      source_filename: sourceFile.value?.name || 'upload.png',
      source_id: '',
    })
    const data = res.data || {}
    resultUrl.value = data.url || ''
    resultFilename.value = data.filename || ''
    tasks.finish(taskId, 'done')
    feedback.success('✅ 图片已编辑')
  } catch (e) {
    lastError.value = (e as Error).message
    tasks.finish(taskId, 'error')
    feedback.error('编辑失败', lastError.value)
  } finally {
    running.value = false
  }
}
</script>

<template>
  <div class="space-y-4">
    <header class="flex items-center justify-between flex-wrap gap-2">
      <h2 class="text-2xl font-bold" style="color: var(--color-ink)">🎨 图片编辑</h2>
      <div class="text-xs text-[var(--color-ink-light)]">基于 OpenAI / MirrorStages 的 /images/edits 接口，上传一张图片 + 文本提示词重写整图</div>
    </header>

    <div v-if="noConfig" class="iv-config-hint warn">
      尚未配置图片模型，前往「模型配置」添加 OpenAI / MirrorStages 凭据
      <router-link to="/config" class="iv-hint-link">去配置</router-link>
    </div>

    <div class="module-grid wide-aside">
      <aside class="space-y-4">
        <section class="module-panel p-4 space-y-3">
          <div class="module-panel-title">输入</div>
          <div>
            <label class="block text-xs text-[var(--color-ink-light)] mb-1">编辑用配置</label>
            <select v-model="selectedConfig" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm">
              <option v-for="c in configStore.imageChoices" :key="c" :value="c">{{ c }}</option>
            </select>
          </div>

          <div>
            <label class="block text-xs text-[var(--color-ink-light)] mb-1">原图（PNG / JPEG / WebP）</label>
            <input ref="fileInput" type="file" accept="image/png,image/jpeg,image/webp" @change="onFileChange" class="text-sm text-[var(--color-ink)] file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:font-medium file:cursor-pointer" />
            <div v-if="sourceFile" class="mt-1 text-[11px] text-[var(--color-ink-light)] break-all">{{ sourceFile.name }} · {{ (sourceFile.size / 1024).toFixed(1) }} KB</div>
          </div>

          <div>
            <label class="block text-xs text-[var(--color-ink-light)] mb-1">编辑提示词</label>
            <textarea v-model="prompt" rows="5" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm resize-y" placeholder="例如：把猫加上一顶红色礼帽，保持背景与画风不变" />
          </div>

          <button
            type="button"
            class="w-full px-4 py-2 rounded-md text-sm font-semibold disabled:opacity-50"
            style="background-color: var(--color-leather); color: var(--color-parchment)"
            :disabled="!canSubmit"
            @click="submit"
          >
            {{ running ? '编辑中...' : '提交编辑' }}
          </button>

          <div v-if="lastError" class="text-xs text-red-700 whitespace-pre-wrap">{{ lastError }}</div>
        </section>
      </aside>

      <main class="space-y-4">
        <section class="module-panel p-4 space-y-3">
          <div class="module-panel-title">原图预览</div>
          <div v-if="sourcePreview" class="bg-[var(--color-parchment-dark)] rounded-md border border-[var(--color-parchment-darker)] p-2">
            <img :src="sourcePreview" class="max-w-full max-h-[420px] object-contain mx-auto" />
          </div>
          <div v-else class="text-sm text-[var(--color-ink-light)] italic">尚未上传原图</div>
        </section>

        <section class="module-panel p-4 space-y-3">
          <div class="module-panel-title">编辑结果</div>
          <div v-if="resultUrl" class="bg-[var(--color-parchment-dark)] rounded-md border border-[var(--color-parchment-darker)] p-2 space-y-2">
            <img :src="resultUrl" class="max-w-full max-h-[520px] object-contain mx-auto" />
            <div class="text-[11px] text-[var(--color-ink-light)] break-all">{{ resultFilename }}</div>
            <div class="flex gap-2">
              <a :href="resultUrl" target="_blank" class="flex-1 text-center px-3 py-1.5 rounded-md border border-[var(--color-parchment-darker)] text-xs bg-white">下载/查看</a>
              <router-link to="/images" class="flex-1 text-center px-3 py-1.5 rounded-md border border-[var(--color-parchment-darker)] text-xs bg-white">去图片库</router-link>
            </div>
          </div>
          <div v-else class="text-sm text-[var(--color-ink-light)] italic">尚无编辑结果。编辑成功后图片也会出现在「图片生成 → 已生成」列表中。</div>
        </section>
      </main>
    </div>
  </div>
</template>

<style scoped>
.iv-config-hint { display: flex; align-items: center; gap: 8px; padding: 6px 10px; font-size: 11px; color: var(--color-ink-light); background: var(--color-surface-muted); border-radius: 6px; border: 1px solid var(--color-control-border); }
.iv-config-hint.warn { background: #fffbeb; border-color: #fde68a; color: #78350f; }
.iv-hint-link { padding: 2px 8px; font-size: 11px; border-radius: 4px; background: var(--color-ink); color: white; text-decoration: none; flex-shrink: 0; }
</style>
