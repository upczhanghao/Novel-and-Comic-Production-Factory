<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { configApi, postSSE } from '@/api/client'
import { useConfigStore } from '@/stores/config'
import { useFeedbackStore } from '@/stores/feedback'
import { confirmDialog } from '@/stores/confirm'
import { useConfigHealth, relativeTestTime, statusIcon } from '@/composables/useConfigHealth'
import { validateImage, ASPECT_RATIOS, RESOLUTIONS } from '@/composables/useConfigValidation'
import { useAsyncAction } from '@/composables/useAsyncAction'
import { classifyImageError } from '@/composables/useImageError'
import ConfigSectionHeader from './ConfigSectionHeader.vue'

const props = defineProps<{ pendingPreset?: Record<string, unknown> | null }>()
const emit = defineEmits<{ (e: 'consumed'): void }>()

const configStore = useConfigStore()
const feedback = useFeedbackStore()
const health = useConfigHealth('image')

const empty = () => ({
  config_name: '', provider: 'openai', api_key: '',
  base_url: 'https://api.openai.com/v1',
  model: 'gpt-image-1',
  aspect_ratio: '9:16', resolution: '1080p',
  output_format: 'png',
})

const selected = ref('')
const form = ref(empty())
const testing = ref(false)
const testResult = ref('')

const isEdit = computed(() => Boolean(selected.value))
const validation = computed(() => validateImage(form.value as Record<string, unknown>, isEdit.value))
const hasErrors = computed(() => Object.keys(validation.value.errors).length > 0)

const defaults = computed(() => [
  { label: '默认图片配置', value: configStore.imageDefault, missing: !configStore.imageDefault },
])

function loadConfig(name: string) {
  if (!name) { form.value = empty(); return }
  const c = configStore.imageConfigs[name]
  if (!c) return
  form.value = {
    config_name: name,
    provider: (c.provider as string) ?? 'openai',
    api_key: (c.api_key as string) === '***' ? '' : ((c.api_key as string) ?? ''),
    base_url: (c.base_url as string) ?? 'https://api.openai.com/v1',
    model: (c.model as string) ?? 'gpt-image-1',
    aspect_ratio: (c.aspect_ratio as string) || inferAspectFromLegacy(c) || '9:16',
    resolution: (c.resolution as string) || inferResolutionFromLegacy(c) || '1080p',
    output_format: (c.output_format as string) ?? 'png',
  }
  testResult.value = ''
}

function inferAspectFromLegacy(c: Record<string, unknown>): string {
  const size = String(c.size ?? '')
  const m = size.match(/^(\d+)x(\d+)$/i)
  if (!m) return ''
  const w = Number(m[1]); const h = Number(m[2])
  if (!w || !h) return ''
  const r = w / h
  if (Math.abs(r - 1) < 0.05) return '1:1'
  if (Math.abs(r - 16 / 9) < 0.1) return '16:9'
  if (Math.abs(r - 9 / 16) < 0.1) return '9:16'
  if (Math.abs(r - 4 / 3) < 0.1) return '4:3'
  if (Math.abs(r - 3 / 4) < 0.1) return '3:4'
  return r > 1 ? '3:2' : '2:3'
}

function inferResolutionFromLegacy(c: Record<string, unknown>): string {
  const size = String(c.size ?? '')
  const m = size.match(/^(\d+)x(\d+)$/i)
  if (!m) return ''
  const long = Math.max(Number(m[1]), Number(m[2]))
  if (long >= 3000) return '4k'
  if (long >= 1800) return '2k'
  if (long >= 1000) return '1080p'
  if (long >= 700) return '720p'
  return '480p'
}

const derivedSize = computed(() => derivePreviewSize(form.value.aspect_ratio, form.value.resolution, form.value.provider, form.value.model))
const derivedQuality = computed(() => derivePreviewQuality(form.value.resolution, form.value.model))

function derivePreviewSize(aspect: string, resolution: string, provider: string, model: string): string {
  const aw_ah = aspect.split(':').map(Number)
  if (aw_ah.length !== 2 || !aw_ah[0] || !aw_ah[1]) return '—'
  const target = aw_ah[0] / aw_ah[1]
  const p = (provider || '').toLowerCase()
  const m = (model || '').toLowerCase()
  if (p === 'openai' || p === 'mirrorstages' || m.startsWith('gpt-image') || m.startsWith('dall-e')) {
    const candidates: [number, number][] = [[1024, 1024], [1024, 1536], [1536, 1024]]
    let best = candidates[0]
    let bestDiff = Infinity
    for (const [w, h] of candidates) {
      const d = Math.abs(w / h - target)
      if (d < bestDiff) { best = [w, h]; bestDiff = d }
    }
    return `${best[0]}×${best[1]}`
  }
  const longEdge = ({ '480p': 480, '720p': 720, '1080p': 1080, '2k': 2048, '4k': 4096 } as Record<string, number>)[resolution] ?? 1080
  const round64 = (n: number) => Math.max(64, Math.round(n / 64) * 64)
  if (aw_ah[0] >= aw_ah[1]) {
    return `${longEdge}×${round64(longEdge * aw_ah[1] / aw_ah[0])}`
  }
  return `${round64(longEdge * aw_ah[0] / aw_ah[1])}×${longEdge}`
}

function derivePreviewQuality(resolution: string, model: string): string {
  const m = (model || '').toLowerCase()
  if (m === 'dall-e-3') return ['1080p', '2k', '4k'].includes(resolution) ? 'hd' : 'standard'
  return ({ '480p': 'low', '720p': 'low', '1080p': 'medium', '2k': 'high', '4k': 'high' } as Record<string, string>)[resolution] ?? 'medium'
}

watch(() => props.pendingPreset, (v) => {
  if (!v) return
  selected.value = ''
  form.value = { ...empty(), ...v }
  emit('consumed')
})

const saveAction = useAsyncAction()
const deleteAction = useAsyncAction()

async function save() {
  if (hasErrors.value) {
    feedback.warning('表单存在错误，请先修正')
    return
  }
  try {
    await saveAction.run(async () => {
      await configApi.saveImage(form.value as Record<string, unknown>)
      await configStore.loadAll()
      selected.value = form.value.config_name
      feedback.success(`✅ 图片配置「${form.value.config_name}」已保存`)
    })
  } catch (e) {
    feedback.error('保存失败', (e as Error).message)
  }
}

async function deleteSelected() {
  if (!selected.value) return
  if (!(await confirmDialog(`确认删除配置「${selected.value}」？`))) return
  try {
    await deleteAction.run(async () => {
      await configApi.deleteImage(selected.value)
      feedback.success(`✅ 已删除「${selected.value}」`)
      selected.value = ''
      form.value = empty()
      await configStore.loadAll()
    })
  } catch (e) {
    feedback.error('删除失败', (e as Error).message)
  }
}

function runTest(onSuccess?: () => void) {
  testing.value = true
  testResult.value = '准备测试…'
  postSSE(
    configApi.testImage(),
    {
      provider: form.value.provider,
      api_key: form.value.api_key,
      base_url: form.value.base_url,
      model: form.value.model,
      // M24/F1: 用 aspect_ratio + resolution，后端派生 size + quality
      aspect_ratio: form.value.aspect_ratio,
      resolution: form.value.resolution,
      output_format: form.value.output_format,
    },
    (msg) => { testResult.value = msg },
    (content) => {
      testResult.value = content
      const ok = content.startsWith('✅')
      const targetName = form.value.config_name || selected.value
      if (targetName) {
        if (ok) health.markOk(targetName, content)
        else health.markFail(targetName, content)
      }
      if (ok) {
        feedback.success('图片配置连通性测试通过')
        onSuccess?.()
      } else {
        const cls = classifyImageError(content)
        feedback.error(cls.title, cls.hint)
      }
    },
    (err) => {
      testResult.value = `❌ ${err}`
      const targetName = form.value.config_name || selected.value
      if (targetName) health.markFail(targetName, err)
      const cls = classifyImageError(err)
      feedback.error(cls.title, cls.hint)
      testing.value = false
    },
    () => { testing.value = false },
  )
}

function testOnly() { runTest() }

async function testAndSetDefault() {
  if (!form.value.config_name) {
    feedback.warning('请先填写配置名称')
    return
  }
  if (!(form.value.config_name in configStore.imageConfigs)) {
    feedback.info('未保存的配置不能直接设为默认，请先保存')
    return
  }
  runTest(async () => {
    try {
      await configApi.setImageDefault(form.value.config_name)
      await configStore.loadAll()
      feedback.success(`✅ 已将「${form.value.config_name}」设为默认图片配置`)
    } catch (e) {
      feedback.error('设为默认失败', (e as Error).message)
    }
  })
}

function statusFor(name: string) {
  return health.get(name)
}
</script>

<template>
  <div class="config-section">
    <ConfigSectionHeader
      title="图片生成配置"
      subtitle="用于图片生成模块和漫剧分镜单图生成"
      icon="🎨"
      :defaults="defaults"
      accent="#ec4899"
    />
    <div class="config-body">
      <div class="cf-row">
        <select v-model="selected" @change="loadConfig(selected)" class="cf-input flex-1">
          <option value="">— 选择已有配置 —</option>
          <option v-for="c in configStore.imageChoices" :key="c" :value="c">
            {{ statusIcon(statusFor(c).status) }} {{ c }}{{ configStore.isSkeleton('image', c) ? ' ⚠ 未配置' : '' }}
          </option>
        </select>
        <button class="cf-btn" type="button" @click="selected = ''; form = empty()">+ 新建</button>
        <button
          class="cf-btn danger" type="button"
          :disabled="!selected"
          :data-busy="deleteAction.busy.value ? 'true' : undefined"
          :data-flash="deleteAction.flash.value || undefined"
          @click="deleteSelected"
        >删除</button>
      </div>

      <div v-if="selected" class="cf-health" title="健康状态仅保存在当前浏览器，更换设备需重新测试">
        <span>{{ statusIcon(statusFor(selected).status) }}</span>
        <span class="cf-health-label">{{
          statusFor(selected).status === 'ok' ? '健康' :
          statusFor(selected).status === 'fail' ? '上次测试失败' : '未测试'
        }}</span>
        <span class="cf-health-time">{{ relativeTestTime(statusFor(selected).lastTestedAt) }}</span>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
        <div>
          <label class="cf-label">配置名称 *</label>
          <input v-model="form.config_name" class="cf-input" />
          <div v-if="validation.errors.config_name" class="cf-err">{{ validation.errors.config_name }}</div>
        </div>
        <div>
          <label class="cf-label">接口类型</label>
          <select v-model="form.provider" class="cf-input">
            <option value="openai">OpenAI Images</option>
            <option value="mirrorstages">MirrorStages Images</option>
          </select>
        </div>
        <div>
          <label class="cf-label">API Key</label>
          <input v-model="form.api_key" type="password" :placeholder="isEdit ? '已有 Key 留空不修改' : '必填'" class="cf-input" />
          <div v-if="validation.errors.api_key" class="cf-err">{{ validation.errors.api_key }}</div>
        </div>
        <div>
          <label class="cf-label">Base URL</label>
          <input v-model="form.base_url" class="cf-input" />
          <div v-if="validation.errors.base_url" class="cf-err">{{ validation.errors.base_url }}</div>
          <div v-else-if="validation.warnings.base_url" class="cf-warn">{{ validation.warnings.base_url }}</div>
        </div>
        <div>
          <label class="cf-label">模型</label>
          <input v-model="form.model" class="cf-input" placeholder="gpt-image-1" />
        </div>
        <div>
          <label class="cf-label">图片比例</label>
          <select v-model="form.aspect_ratio" class="cf-input">
            <option v-for="r in ASPECT_RATIOS" :key="r" :value="r">{{ r }}</option>
          </select>
          <div v-if="validation.errors.aspect_ratio" class="cf-err">{{ validation.errors.aspect_ratio }}</div>
        </div>
        <div>
          <label class="cf-label">分辨率档位</label>
          <select v-model="form.resolution" class="cf-input">
            <option v-for="r in RESOLUTIONS" :key="r" :value="r">{{ r }}</option>
          </select>
          <div v-if="validation.errors.resolution" class="cf-err">{{ validation.errors.resolution }}</div>
        </div>
        <div class="sm:col-span-2">
          <div class="cf-derived" :title="`provider=${form.provider}, model=${form.model}`">
            <span class="cf-derived-label">实际请求参数</span>
            <span class="cf-derived-pill">size: {{ derivedSize }}</span>
            <span class="cf-derived-pill">quality: {{ derivedQuality }}</span>
            <span class="cf-derived-hint">— 由比例 + 档位 + 模型自动派生，不需要手填</span>
          </div>
        </div>
        <div>
          <label class="cf-label">输出格式</label>
          <select v-model="form.output_format" class="cf-input">
            <option value="png">png</option>
            <option value="jpeg">jpeg</option>
            <option value="webp">webp</option>
          </select>
        </div>
      </div>

      <div v-if="testResult" class="mt-3 px-3 py-2 rounded-md text-xs"
        :class="testResult.startsWith('✅') ? 'bg-green-50 text-green-800 border border-green-200' : 'bg-red-50 text-red-800 border border-red-200'">
        {{ testResult }}
      </div>

      <div class="cf-row mt-3 justify-end">
        <button
          class="cf-btn ghost" type="button"
          :disabled="testing || !form.model"
          :data-busy="testing ? 'true' : undefined"
          @click="testOnly"
        >
          {{ testing ? '测试中…' : '测试连接' }}
        </button>
        <button
          class="cf-btn ghost" type="button"
          :disabled="testing || !isEdit"
          :data-busy="testing ? 'true' : undefined"
          @click="testAndSetDefault"
        >
          测试并设为默认
        </button>
        <button
          class="cf-btn primary" type="button"
          :disabled="hasErrors"
          :data-busy="saveAction.busy.value ? 'true' : undefined"
          :data-flash="saveAction.flash.value || undefined"
          @click="save"
        >保存图片配置</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.config-section { display: flex; flex-direction: column; }
.config-body { padding: 14px 16px; background: white; border: 1px solid var(--color-control-border); border-top: none; border-radius: 0 0 10px 10px; }
.cf-row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.cf-row.justify-end { justify-content: flex-end; }
.cf-input { padding: 8px 10px; font-size: 13px; border: 1px solid var(--color-parchment-darker); border-radius: 6px; background: white; width: 100%; }
.cf-input:focus { outline: none; border-color: var(--color-leather-light); box-shadow: 0 0 0 2px rgba(150,110,80,0.12); }
.cf-label { display: block; font-size: 11px; color: var(--color-ink-light); margin-bottom: 4px; }
.cf-btn { padding: 7px 14px; font-size: 13px; border-radius: 6px; border: 1px solid var(--color-control-border); background: white; cursor: pointer; }
.cf-btn:hover:not(:disabled) { border-color: var(--color-leather-light); }
.cf-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.cf-btn.primary { background: var(--color-leather); color: var(--color-parchment); border-color: var(--color-leather); font-weight: 600; }
.cf-btn.ghost { background: transparent; }
.cf-btn.danger { color: var(--color-error); border-color: #fecaca; }
.cf-btn.danger:hover:not(:disabled) { background: var(--color-error); color: white; }
.cf-err { font-size: 11px; color: var(--color-error); margin-top: 2px; }
.cf-warn { font-size: 11px; color: #92400e; margin-top: 2px; }
.cf-health { display: flex; align-items: center; gap: 8px; padding: 6px 10px; margin-top: 8px; background: var(--color-surface-muted); border: 1px solid var(--color-control-border); border-radius: 6px; font-size: 12px; }
.cf-health-label { font-weight: 600; color: var(--color-ink); }
.cf-health-time { color: var(--color-ink-light); }
.cf-derived { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; padding: 6px 10px; background: #fff7ed; border: 1px solid #fed7aa; border-radius: 6px; font-size: 11px; }
.cf-derived-label { font-weight: 600; color: #9a3412; }
.cf-derived-pill { padding: 2px 8px; background: white; border: 1px solid #fdba74; border-radius: 999px; font-family: ui-monospace, monospace; color: #7c2d12; }
.cf-derived-hint { color: var(--color-ink-light); font-size: 10px; }
</style>
