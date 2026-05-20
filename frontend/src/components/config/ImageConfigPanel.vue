<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { configApi, postSSE } from '@/api/client'
import { useConfigStore } from '@/stores/config'
import { useFeedbackStore } from '@/stores/feedback'
import { useConfigHealth, relativeTestTime, statusIcon } from '@/composables/useConfigHealth'
import { validateImage } from '@/composables/useConfigValidation'
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
  model: 'gpt-image-1', size: '1024x1536', quality: 'medium', output_format: 'png',
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
    size: (c.size as string) ?? '1024x1536',
    quality: (c.quality as string) ?? 'medium',
    output_format: (c.output_format as string) ?? 'png',
  }
  testResult.value = ''
}

watch(() => props.pendingPreset, (v) => {
  if (!v) return
  selected.value = ''
  form.value = { ...empty(), ...form.value, ...v }
  emit('consumed')
})

async function save() {
  if (hasErrors.value) {
    feedback.warning('表单存在错误，请先修正')
    return
  }
  try {
    await configApi.saveImage(form.value as Record<string, unknown>)
    await configStore.loadAll()
    selected.value = form.value.config_name
    feedback.success(`✅ 图片配置「${form.value.config_name}」已保存`)
  } catch (e) {
    feedback.error('保存失败', (e as Error).message)
  }
}

async function deleteSelected() {
  if (!selected.value) return
  if (!confirm(`确认删除配置「${selected.value}」？`)) return
  try {
    await configApi.deleteImage(selected.value)
    feedback.success(`✅ 已删除「${selected.value}」`)
    selected.value = ''
    form.value = empty()
    await configStore.loadAll()
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
      size: '1024x1024',
      quality: 'low',
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
        <button class="cf-btn danger" type="button" :disabled="!selected" @click="deleteSelected">删除</button>
      </div>

      <div v-if="selected" class="cf-health">
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
          <label class="cf-label">尺寸</label>
          <input v-model="form.size" class="cf-input" placeholder="1024x1536" />
          <div v-if="validation.errors.size" class="cf-err">{{ validation.errors.size }}</div>
          <div v-else-if="validation.warnings.size" class="cf-warn">{{ validation.warnings.size }}</div>
        </div>
        <div>
          <label class="cf-label">质量</label>
          <select v-model="form.quality" class="cf-input">
            <option value="low">low</option>
            <option value="medium">medium</option>
            <option value="high">high</option>
          </select>
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
        <button class="cf-btn ghost" type="button" :disabled="testing || !form.model" @click="testOnly">
          {{ testing ? '测试中…' : '测试连接' }}
        </button>
        <button class="cf-btn ghost" type="button" :disabled="testing || !isEdit" @click="testAndSetDefault">
          测试并设为默认
        </button>
        <button class="cf-btn primary" type="button" :disabled="hasErrors" @click="save">保存图片配置</button>
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
</style>
