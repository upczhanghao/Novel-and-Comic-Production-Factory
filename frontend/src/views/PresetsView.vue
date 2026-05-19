<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { presetsApi } from '@/api/client'

interface PromptData {
  prompts: Record<string, string>
  keys: string[]
  display_names: Record<string, string>
}

const presets = ref<string[]>([])
const activePreset = ref('')
const activeDesc = ref('')
const statusMsg = ref('')

const promptData = ref<PromptData>({ prompts: {}, keys: [], display_names: {} })
const selectedKey = ref('')
const promptContent = ref('')

const newPresetName = ref('')
const newPresetDesc = ref('')

async function loadAll() {
  const res = await presetsApi.list()
  presets.value = res.data.presets
  activePreset.value = res.data.active_preset
  activeDesc.value = res.data.active_description
  const pd = await presetsApi.getPrompts()
  promptData.value = pd.data
}

async function activate(name: string) {
  try {
    const res = await presetsApi.activate(name)
    activePreset.value = res.data.active_preset
    activeDesc.value = res.data.description
    statusMsg.value = res.data.message
    await loadAll()
  } catch (e: unknown) {
    statusMsg.value = `❌ ${(e as Error).message}`
  }
}

function loadPrompt(key: string) {
  promptContent.value = promptData.value.prompts[key] ?? ''
}

watch(selectedKey, loadPrompt)

async function savePrompt() {
  if (!selectedKey.value) return
  try {
    const res = await presetsApi.updatePrompt(selectedKey.value, promptContent.value)
    statusMsg.value = res.data.message
    await loadAll()
    loadPrompt(selectedKey.value)
  } catch (e: unknown) {
    statusMsg.value = `❌ ${(e as Error).message}`
  }
}

async function resetPrompt() {
  if (!selectedKey.value) return
  try {
    const res = await presetsApi.resetPrompt(selectedKey.value)
    promptContent.value = res.data.content
    statusMsg.value = res.data.message
  } catch (e: unknown) {
    statusMsg.value = `❌ ${(e as Error).message}`
  }
}

async function saveAsNew() {
  if (!newPresetName.value.trim()) return
  try {
    const res = await presetsApi.save(newPresetName.value.trim(), newPresetDesc.value)
    statusMsg.value = res.data.message
    newPresetName.value = ''
    newPresetDesc.value = ''
    await loadAll()
  } catch (e: unknown) {
    statusMsg.value = `❌ ${(e as Error).message}`
  }
}

async function deletePreset(name: string) {
  if (!confirm(`确认删除方案「${name}」？`)) return
  try {
    const res = await presetsApi.delete(name)
    statusMsg.value = res.data.message
    await loadAll()
  } catch (e: unknown) {
    statusMsg.value = `❌ ${(e as Error).message}`
  }
}

onMounted(loadAll)
</script>

<template>
  <div class="module-page compact space-y-5">
    <h2 class="text-2xl font-bold" style="color: var(--color-ink)">📋 提示词方案</h2>

    <Transition name="fade">
      <div v-if="statusMsg" class="px-4 py-2 rounded-md text-sm"
        :class="statusMsg.startsWith('✅') ? 'bg-green-50 text-green-800 border border-green-200' : 'bg-red-50 text-red-800 border border-red-200'">
        {{ statusMsg }}
      </div>
    </Transition>

    <div class="module-toolbar">
      <div>
        <div class="module-kicker">Prompt Presets</div>
        <div class="module-subtitle">当前激活：<strong>{{ activePreset }}</strong> — {{ activeDesc }}</div>
      </div>
    </div>

    <div class="module-grid">
      <!-- 方案列表 -->
      <div class="module-panel p-5 space-y-4 module-aside-sticky">
        <div>
          <h3 class="module-panel-title">方案管理</h3>
          <p class="module-panel-caption">切换、复制或删除提示词方案。</p>
        </div>
      <div class="module-list">
        <div v-for="p in presets" :key="p" class="flex items-center gap-1">
          <button
            @click="activate(p)"
            class="module-list-item flex-1 px-3 py-2 text-sm text-left"
            :class="p === activePreset
              ? 'active font-semibold text-[var(--color-leather)]'
              : ''"
            type="button"
          >
            {{ p }}
          </button>
          <button
            v-if="p !== activePreset"
            @click="deletePreset(p)"
            class="px-1.5 py-1 rounded text-xs text-red-500 border border-red-200 hover:bg-red-50 transition-colors"
            type="button"
            title="删除"
          >✕</button>
        </div>
      </div>

      <!-- 另存为 -->
      <div class="grid grid-cols-1 gap-3 border-t border-[var(--color-parchment-darker)] pt-4">
        <div>
          <label class="block text-xs text-[var(--color-ink-light)] mb-1">新方案名称</label>
          <input v-model="newPresetName" class="border border-[var(--color-parchment-darker)] rounded-md px-3 py-1.5 text-sm w-full" />
        </div>
        <div>
          <label class="block text-xs text-[var(--color-ink-light)] mb-1">描述（可选）</label>
          <input v-model="newPresetDesc" class="border border-[var(--color-parchment-darker)] rounded-md px-3 py-1.5 text-sm w-full" />
        </div>
        <button @click="saveAsNew" class="px-4 py-1.5 rounded-md text-sm font-semibold transition-colors" style="background-color: var(--color-leather); color: var(--color-parchment)" type="button">
          另存为新方案
        </button>
      </div>
      </div>

    <!-- 提示词编辑 -->
      <div class="module-panel p-5 space-y-3">
      <h3 class="module-panel-title">提示词编辑</h3>
      <div class="flex gap-2 flex-wrap">
        <select v-model="selectedKey" class="border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm flex-1">
          <option value="">— 选择提示词 —</option>
          <option
            v-for="key in promptData.keys"
            :key="key"
            :value="key"
          >
            {{ promptData.display_names[key] ?? key }} ({{ key }})
          </option>
        </select>
      </div>
      <textarea
        v-model="promptContent"
        rows="16"
        class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm font-mono resize-y"
        placeholder="选择提示词后显示内容…"
      />
      <div class="flex gap-2 justify-end">
        <button @click="resetPrompt" :disabled="!selectedKey" class="px-4 py-2 rounded-md text-sm border border-[var(--color-parchment-darker)] hover:bg-[var(--color-parchment)] disabled:opacity-40 transition-colors" type="button">
          重置为默认
        </button>
        <button @click="savePrompt" :disabled="!selectedKey" class="px-4 py-2 rounded-md text-sm font-semibold disabled:opacity-40 transition-colors" style="background-color: var(--color-leather); color: var(--color-parchment)" type="button">
          保存到当前方案
        </button>
      </div>
      </div>
    </div>
  </div>
</template>
