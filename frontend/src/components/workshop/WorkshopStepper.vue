<script setup lang="ts">
import { computed } from 'vue'
import type { useWorkshopState } from '@/composables/useWorkshopState'

const props = defineProps<{ state: ReturnType<typeof useWorkshopState> }>()
const emit = defineEmits<{ (e: 'goto', step: number): void }>()

const steps = [
  { key: 'arch', label: '架构', short: '1' },
  { key: 'blueprint', label: '目录', short: '2' },
  { key: 'outline', label: '细纲', short: '3' },
  { key: 'chapter', label: '章节', short: '4' },
  { key: 'finalize', label: '定稿', short: '5' },
  { key: 'humanize', label: '去痕', short: '6' },
  { key: 'continue', label: '续写', short: '7' },
]

const currentStep = computed(() => {
  const s = props.state
  if (s.continueArch.value.running || s.continueArch.value.result) return 6
  if (s.humanize.value.running || s.humanize.value.result) return 5
  if (s.expand.value.running || s.expand.value.result || s.finalize.value.running || s.finalize.value.result) return 4
  if (s.chapter.value.running || s.chapter.value.result) return 3
  if (s.detailedOutline.value.running || s.outlineText.value) return 2
  if (s.bp.value.running || s.bp.value.result) return 1
  return 0
})

function stepStatus(idx: number) {
  if (idx < currentStep.value) return 'done'
  if (idx === currentStep.value) return 'active'
  return 'pending'
}
</script>

<template>
  <div class="ws-stepper">
    <button
      v-for="(step, idx) in steps"
      :key="step.key"
      class="ws-step"
      :class="stepStatus(idx)"
      @click="emit('goto', idx)"
      type="button"
      :title="step.label"
    >
      <span class="ws-step-num">{{ step.short }}</span>
      <span class="ws-step-label">{{ step.label }}</span>
    </button>
  </div>
</template>

<style scoped>
.ws-stepper { display: flex; gap: 4px; padding: 8px 0; overflow-x: auto; }
.ws-step { display: flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 999px; border: 1px solid var(--color-control-border); background: var(--color-surface-muted); font-size: 12px; color: var(--color-ink-light); white-space: nowrap; transition: all 0.15s; cursor: pointer; }
.ws-step:hover { border-color: var(--color-leather-light); }
.ws-step-num { width: 20px; height: 20px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-weight: 700; font-size: 11px; background: var(--color-control-border); color: white; }
.ws-step.active { border-color: var(--color-gold); background: var(--color-gold-light); color: var(--color-ink); }
.ws-step.active .ws-step-num { background: var(--color-gold); }
.ws-step.done { border-color: var(--color-success); }
.ws-step.done .ws-step-num { background: var(--color-success); }
.ws-step-label { display: none; }
@media (min-width: 640px) { .ws-step-label { display: inline; } }
</style>
