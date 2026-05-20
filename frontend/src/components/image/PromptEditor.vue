<script setup lang="ts">
import { computed } from 'vue'
import PromptBreakdown from './PromptBreakdown.vue'

const props = defineProps<{
  modelValue: string
  negative?: string
  rows?: number
  disabled?: boolean
  placeholder?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: string): void
  (e: 'update:negative', v: string): void
}>()

const text = computed({
  get: () => props.modelValue ?? '',
  set: (v: string) => emit('update:modelValue', v),
})
const negText = computed({
  get: () => props.negative ?? '',
  set: (v: string) => emit('update:negative', v),
})

function copyAll() {
  const full = negText.value ? `${text.value}\n\n负向提示词：${negText.value}` : text.value
  navigator.clipboard?.writeText(full).catch(() => {})
}
</script>

<template>
  <div class="pe-root">
    <div class="pe-section">
      <div class="pe-label-row">
        <label class="pe-label">正向提示词</label>
        <button class="pe-mini" type="button" @click="copyAll" :disabled="!text">复制全部</button>
      </div>
      <textarea
        v-model="text"
        :rows="rows ?? 8"
        :disabled="disabled"
        :placeholder="placeholder ?? '描述主体、风格、构图、光影、质量关键词等…'"
        class="pe-textarea"
      />
    </div>
    <div class="pe-section">
      <label class="pe-label">负向提示词（可选）</label>
      <textarea
        v-model="negText"
        rows="3"
        :disabled="disabled"
        placeholder="想避免出现的元素，例如 blurry, low quality, extra fingers…"
        class="pe-textarea pe-neg"
      />
    </div>
    <PromptBreakdown :prompt="text" :negative="negText" />
  </div>
</template>

<style scoped>
.pe-root { display: flex; flex-direction: column; gap: 10px; }
.pe-section { display: flex; flex-direction: column; gap: 4px; }
.pe-label-row { display: flex; align-items: center; justify-content: space-between; }
.pe-label { font-size: 11px; color: var(--color-ink-light); }
.pe-mini { padding: 2px 8px; font-size: 11px; border-radius: 4px; border: 1px solid var(--color-control-border); background: white; cursor: pointer; }
.pe-mini:disabled { opacity: 0.4; cursor: not-allowed; }
.pe-textarea { width: 100%; padding: 8px 10px; font-size: 13px; line-height: 1.55; border: 1px solid var(--color-parchment-darker); border-radius: 8px; resize: vertical; background: white; }
.pe-textarea:focus { outline: none; border-color: var(--color-leather-light); box-shadow: 0 0 0 2px rgba(150,110,80,0.12); }
.pe-textarea.pe-neg { background: var(--color-surface-muted); }
</style>
