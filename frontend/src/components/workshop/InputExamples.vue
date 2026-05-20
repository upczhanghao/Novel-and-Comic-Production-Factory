<script setup lang="ts">
interface Example {
  label: string
  value: string
  description?: string
}

const props = defineProps<{
  field: string
  examples: Example[]
  modelValue: string | number
  minHint?: string
}>()

const emit = defineEmits<{ (e: 'update:modelValue', v: string | number): void }>()

function pick(ex: Example) {
  emit('update:modelValue', ex.value)
}
</script>

<template>
  <div class="ie-root">
    <div class="ie-header">
      <span class="ie-tag">建议</span>
      <span v-if="props.minHint" class="ie-min">最小可用：{{ props.minHint }}</span>
    </div>
    <div class="ie-chips">
      <button
        v-for="ex in props.examples"
        :key="ex.label"
        @click="pick(ex)"
        class="ie-chip"
        :class="{ active: String(props.modelValue) === ex.value }"
        :title="ex.description"
        type="button"
      >{{ ex.label }}</button>
    </div>
  </div>
</template>

<style scoped>
.ie-root { margin-top: 6px; }
.ie-header { display: flex; align-items: center; gap: 8px; font-size: 11px; color: var(--color-ink-light); margin-bottom: 4px; }
.ie-tag { background: var(--color-gold-light); color: var(--color-gold-dark); padding: 1px 6px; border-radius: 4px; font-weight: 600; }
.ie-min { font-style: italic; }
.ie-chips { display: flex; flex-wrap: wrap; gap: 4px; }
.ie-chip { padding: 3px 10px; font-size: 11px; border-radius: 999px; border: 1px solid var(--color-control-border); background: white; color: var(--color-ink-light); cursor: pointer; transition: all 0.15s; }
.ie-chip:hover { border-color: var(--color-leather-light); color: var(--color-ink); }
.ie-chip.active { background: var(--color-leather); color: white; border-color: var(--color-leather); }
</style>
