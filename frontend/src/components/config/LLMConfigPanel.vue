<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { configApi, postSSE } from '@/api/client'
import { useConfigStore, LLM_DEFAULT_SLOTS } from '@/stores/config'
import { useFeedbackStore } from '@/stores/feedback'
import { useConfigHealth, relativeTestTime, statusIcon } from '@/composables/useConfigHealth'
import { validateLLM } from '@/composables/useConfigValidation'
import ConfigSectionHeader from './ConfigSectionHeader.vue'

const props = defineProps<{ pendingPreset?: Record<string, unknown> | null }>()
const emit = defineEmits<{ (e: 'consumed'): void }>()

const configStore = useConfigStore()
const feedback = useFeedbackStore()
const health = useConfigHealth('llm')

const interfaceFormats = ['OpenAI', 'MirrorStages', 'DeepSeek', 'Gemini', 'Ollama', 'Azure OpenAI', 'Azure AI', 'ML Studio', '阿里云百炼', '火山引擎', '硅基流动', 'Grok']

const empty = () => ({
  config_name: '', api_key: '', base_url: '', interface_format: 'OpenAI',
  model_name: '', temperature: 0.7, max_tokens: 4096, timeout: 600,
  enable_thinking: false, thinking_budget: 0, enable_streaming: true,
})

const selected = ref('')
const form = ref(empty())
const testing = ref(false)
const testResult = ref('')
const showSlotPicker = ref(false)
const slotPicks = ref<Record<string, boolean>>({})

const isEdit = computed(() => Boolean(selected.value))
const validation = computed(() => validateLLM(form.value as Record<string, unknown>, isEdit.value))
const hasErrors = computed(() => Object.keys(validation.value.errors).length > 0)

const defaults = computed(() =>
  LLM_DEFAULT_SLOTS.map((s) => ({
    label: s.label,
    value: configStore.llmDefaults[s.key] ?? '',
    missing: !configStore.llmDefaults[s.key] || !(configStore.llmDefaults[s.key] in configStore.llmConfigs),
  })),
)

function loadConfig(name: string) {
  if (!name) { form.value = empty(); return }
  const c = configStore.llmConfigs[name]
  if (!c) return
  form.value = {
    config_name: name,
    api_key: (c.api_key as string) === '***' ? '' : ((c.api_key as string) ?? ''),
    base_url: (c.base_url as string) ?? '',
    interface_format: (c.interface_format as string) ?? 'OpenAI',
    model_name: (c.model_name as string) ?? '',
    temperature: (c.temperature as number) ?? 0.7,
    max_tokens: (c.max_tokens as number) ?? 4096,
    timeout: (c.timeout as number) ?? 600,
    enable_thinking: (c.enable_thinking as boolean) ?? false,
    thinking_budget: (c.thinking_budget as number) ?? 0,
    enable_streaming: (c.enable_streaming as boolean) ?? true,
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
    await configApi.saveLLM(form.value as Record<string, unknown>)
    await configStore.loadAll()
    selected.value = form.value.config_name
    feedback.success(`✅ LLM 配置「${form.value.config_name}」已保存`)
  } catch (e) {
    feedback.error('保存失败', (e as Error).message)
  }
}

async function deleteSelected() {
  if (!selected.value) return
  if (!confirm(`确认删除配置「${selected.value}」？`)) return
  try {
    await configApi.deleteLLM(selected.value)
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
    configApi.testLLM(),
    {
      interface_format: form.value.interface_format,
      api_key: form.value.api_key,
      base_url: form.value.base_url,
      model_name: form.value.model_name,
      temperature: form.value.temperature,
      max_tokens: form.value.max_tokens,
      timeout: form.value.timeout,
      enable_thinking: form.value.enable_thinking,
      thinking_budget: form.value.thinking_budget,
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
        feedback.success('LLM 连通性测试通过')
        onSuccess?.()
      } else {
        feedback.error('LLM 测试失败', content)
      }
    },
    (err) => {
      testResult.value = `❌ ${err}`
      const targetName = form.value.config_name || selected.value
      if (targetName) health.markFail(targetName, err)
      feedback.error('LLM 测试出错', err)
      testing.value = false
    },
    () => { testing.value = false },
  )
}

function testOnly() { runTest() }

function testAndSetDefault() {
  if (!form.value.config_name) {
    feedback.warning('请先填写配置名称')
    return
  }
  if (!(form.value.config_name in configStore.llmConfigs)) {
    feedback.info('未保存的配置不能直接设为默认，请先保存')
    return
  }
  runTest(() => {
    slotPicks.value = Object.fromEntries(LLM_DEFAULT_SLOTS.map((s) => [s.key, s.key === 'prompt_draft_llm']))
    showSlotPicker.value = true
  })
}

async function applySlots() {
  const slots = Object.entries(slotPicks.value).filter(([, v]) => v).map(([k]) => k)
  if (!slots.length) { showSlotPicker.value = false; return }
  let ok = 0
  for (const slot of slots) {
    try {
      await configApi.setLLMDefault(slot, form.value.config_name)
      ok++
    } catch (e) {
      feedback.error(`${slot} 写入失败`, (e as Error).message)
    }
  }
  await configStore.loadAll()
  showSlotPicker.value = false
  feedback.success(`✅ 已将「${form.value.config_name}」设为 ${ok} 个默认槽位`)
}

function selectAllSlots() {
  for (const s of LLM_DEFAULT_SLOTS) slotPicks.value[s.key] = true
}

function statusFor(name: string) {
  return health.get(name)
}
</script>

<template>
  <div class="config-section">
    <ConfigSectionHeader
      title="LLM 配置"
      subtitle="用于创作、改写、提示词草稿、一致性审查等文本任务"
      icon="🧠"
      :defaults="defaults"
      accent="#3b82f6"
    />
    <div class="config-body">
      <div class="cf-row">
        <select v-model="selected" @change="loadConfig(selected)" class="cf-input flex-1">
          <option value="">— 选择已有配置 —</option>
          <option v-for="c in configStore.llmChoices" :key="c" :value="c">
            {{ statusIcon(statusFor(c).status) }} {{ c }}{{ configStore.isSkeleton('llm', c) ? ' ⚠ 未配置' : '' }}
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
        <span v-if="statusFor(selected).lastMessage" class="cf-health-msg" :title="statusFor(selected).lastMessage">
          {{ statusFor(selected).lastMessage.slice(0, 60) }}
        </span>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
        <div>
          <label class="cf-label">配置名称 *</label>
          <input v-model="form.config_name" class="cf-input" />
          <div v-if="validation.errors.config_name" class="cf-err">{{ validation.errors.config_name }}</div>
        </div>
        <div>
          <label class="cf-label">接口格式</label>
          <select v-model="form.interface_format" class="cf-input">
            <option v-for="f in interfaceFormats" :key="f" :value="f">{{ f }}</option>
          </select>
        </div>
        <div>
          <label class="cf-label">API Key</label>
          <input v-model="form.api_key" type="password" :placeholder="isEdit ? '已有 Key 留空不修改' : '必填'" class="cf-input" />
          <div v-if="validation.errors.api_key" class="cf-err">{{ validation.errors.api_key }}</div>
          <div v-else-if="validation.warnings.api_key" class="cf-warn">{{ validation.warnings.api_key }}</div>
        </div>
        <div>
          <label class="cf-label">Base URL</label>
          <input v-model="form.base_url" class="cf-input" placeholder="https://api.example.com/v1" />
          <div v-if="validation.errors.base_url" class="cf-err">{{ validation.errors.base_url }}</div>
          <div v-else-if="validation.warnings.base_url" class="cf-warn">{{ validation.warnings.base_url }}</div>
        </div>
        <div>
          <label class="cf-label">模型名称 *</label>
          <input v-model="form.model_name" class="cf-input" />
          <div v-if="validation.errors.model_name" class="cf-err">{{ validation.errors.model_name }}</div>
        </div>
        <div>
          <label class="cf-label">Temperature ({{ form.temperature }})</label>
          <input v-model.number="form.temperature" type="range" min="0" max="2" step="0.05" class="w-full accent-[var(--color-leather)]" />
        </div>
        <div>
          <label class="cf-label">Max Tokens</label>
          <input v-model.number="form.max_tokens" type="number" min="256" class="cf-input" />
        </div>
        <div>
          <label class="cf-label">超时（秒）</label>
          <input v-model.number="form.timeout" type="number" min="10" class="cf-input" />
        </div>
        <label class="cf-checkbox">
          <input type="checkbox" v-model="form.enable_thinking" />
          启用 Thinking 模式
        </label>
        <label class="cf-checkbox">
          <input type="checkbox" v-model="form.enable_streaming" />
          流式输出
        </label>
        <div v-if="form.enable_thinking">
          <label class="cf-label">Thinking Budget</label>
          <input v-model.number="form.thinking_budget" type="number" min="0" class="cf-input" />
        </div>
      </div>

      <div v-if="testResult" class="mt-3 px-3 py-2 rounded-md text-xs"
        :class="testResult.startsWith('✅') ? 'bg-green-50 text-green-800 border border-green-200' : 'bg-red-50 text-red-800 border border-red-200'">
        {{ testResult }}
      </div>

      <div class="cf-row mt-3 justify-end">
        <button class="cf-btn ghost" type="button" :disabled="testing || !form.model_name" @click="testOnly">
          {{ testing ? '测试中…' : '测试连接' }}
        </button>
        <button class="cf-btn ghost" type="button" :disabled="testing || !isEdit" @click="testAndSetDefault" title="先保存再测，通过后设为默认">
          测试并设为默认
        </button>
        <button class="cf-btn primary" type="button" :disabled="hasErrors" @click="save">保存 LLM 配置</button>
      </div>
    </div>

    <Teleport to="body">
      <div v-if="showSlotPicker" class="slot-modal-mask" @click.self="showSlotPicker = false">
        <div class="slot-modal">
          <div class="slot-head">
            <div>
              <div class="slot-title">设为哪些默认槽位？</div>
              <div class="slot-sub">将「{{ form.config_name }}」应用到选中的任务上。</div>
            </div>
            <button class="cf-btn ghost" type="button" @click="selectAllSlots">全选</button>
          </div>
          <div class="slot-list">
            <label v-for="s in LLM_DEFAULT_SLOTS" :key="s.key" class="slot-item">
              <input type="checkbox" v-model="slotPicks[s.key]" />
              <div class="flex-1">
                <div class="slot-item-label">{{ s.label }}</div>
                <div class="slot-item-current">当前：{{ configStore.llmDefaults[s.key] || '未设置' }}</div>
              </div>
            </label>
          </div>
          <div class="slot-actions">
            <button class="cf-btn" type="button" @click="showSlotPicker = false">取消</button>
            <button class="cf-btn primary" type="button" @click="applySlots">应用</button>
          </div>
        </div>
      </div>
    </Teleport>
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
.cf-checkbox { display: flex; align-items: center; gap: 8px; font-size: 13px; cursor: pointer; user-select: none; }
.cf-checkbox input { accent-color: var(--color-leather); }
.cf-health { display: flex; align-items: center; gap: 8px; padding: 6px 10px; margin-top: 8px; background: var(--color-surface-muted); border: 1px solid var(--color-control-border); border-radius: 6px; font-size: 12px; }
.cf-health-label { font-weight: 600; color: var(--color-ink); }
.cf-health-time { color: var(--color-ink-light); }
.cf-health-msg { color: var(--color-ink-light); margin-left: auto; max-width: 50%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 11px; }

.slot-modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: grid; place-items: center; z-index: 100; }
.slot-modal { width: min(480px, 92vw); background: white; border-radius: 10px; padding: 16px; box-shadow: 0 10px 40px rgba(0,0,0,0.2); }
.slot-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; }
.slot-title { font-size: 14px; font-weight: 700; color: var(--color-ink); }
.slot-sub { font-size: 12px; color: var(--color-ink-light); margin-top: 2px; }
.slot-list { display: flex; flex-direction: column; gap: 4px; max-height: 320px; overflow: auto; }
.slot-item { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border: 1px solid var(--color-control-border); border-radius: 6px; cursor: pointer; }
.slot-item:hover { background: var(--color-surface-muted); }
.slot-item input { accent-color: var(--color-leather); }
.slot-item-label { font-size: 13px; font-weight: 600; color: var(--color-ink); }
.slot-item-current { font-size: 11px; color: var(--color-ink-light); }
.slot-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px; }
</style>
