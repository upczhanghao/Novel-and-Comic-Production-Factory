<script setup lang="ts">
import { useFeedbackStore } from '@/stores/feedback'

const feedback = useFeedbackStore()

function iconFor(type: string) {
  if (type === 'success') return '✓'
  if (type === 'error') return '✕'
  if (type === 'warning') return '!'
  return 'ℹ'
}
</script>

<template>
  <Teleport to="body">
    <div class="fb-stack">
      <TransitionGroup name="fb">
        <div
          v-for="item in feedback.items"
          :key="item.id"
          class="fb-item"
          :class="`fb-${item.type}`"
        >
          <div class="fb-icon">{{ iconFor(item.type) }}</div>
          <div class="fb-body">
            <div class="fb-msg">{{ item.message }}</div>
            <div v-if="item.detail" class="fb-detail">{{ item.detail }}</div>
          </div>
          <button v-if="item.undoFn" class="fb-undo" @click="feedback.undo(item.id)" type="button">撤销</button>
          <button class="fb-close" @click="feedback.dismiss(item.id)" type="button" aria-label="关闭">×</button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.fb-stack { position: fixed; bottom: 80px; right: 20px; z-index: 60; display: flex; flex-direction: column; gap: 8px; max-width: 380px; pointer-events: none; }
.fb-item { pointer-events: auto; display: flex; align-items: flex-start; gap: 10px; padding: 10px 12px; border-radius: 10px; background: var(--color-surface); border: 1px solid var(--color-control-border); box-shadow: 0 8px 24px rgba(0,0,0,0.12); font-size: 13px; }
.fb-icon { width: 22px; height: 22px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-weight: 700; color: white; flex-shrink: 0; }
.fb-success .fb-icon { background: var(--color-success); }
.fb-error .fb-icon { background: var(--color-error); }
.fb-warning .fb-icon { background: var(--color-warning); }
.fb-info .fb-icon { background: var(--color-leather-light); }
.fb-body { flex: 1; min-width: 0; }
.fb-msg { font-weight: 500; color: var(--color-ink); }
.fb-detail { color: var(--color-ink-light); font-size: 12px; margin-top: 2px; word-break: break-word; }
.fb-undo { background: transparent; border: 1px solid var(--color-control-border); padding: 2px 8px; border-radius: 6px; font-size: 12px; color: var(--color-leather-light); }
.fb-undo:hover { background: var(--color-surface-muted); }
.fb-close { background: transparent; border: 0; color: var(--color-ink-light); font-size: 18px; line-height: 1; padding: 0 4px; }
.fb-error { border-left: 3px solid var(--color-error); }
.fb-success { border-left: 3px solid var(--color-success); }
.fb-warning { border-left: 3px solid var(--color-warning); }
.fb-info { border-left: 3px solid var(--color-leather-light); }
.fb-enter-from { opacity: 0; transform: translateX(20px); }
.fb-leave-to { opacity: 0; transform: translateX(20px); }
.fb-enter-active, .fb-leave-active { transition: all 0.25s ease; }
@media (max-width: 640px) {
  .fb-stack { left: 12px; right: 12px; bottom: 90px; max-width: none; }
}
</style>
