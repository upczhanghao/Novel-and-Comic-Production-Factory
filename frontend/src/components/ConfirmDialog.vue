<script setup lang="ts">
import { computed } from 'vue'
import { useConfirmStore } from '@/stores/confirm'

const store = useConfirmStore()
const open = computed(() => !!store.current)

function ok() { store.decide(true) }
function cancel() { store.decide(false) }

function onKey(e: KeyboardEvent) {
  if (!open.value) return
  if (e.key === 'Escape') cancel()
  if (e.key === 'Enter') ok()
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="cd-mask" @click.self="cancel" @keydown="onKey" tabindex="0">
      <div class="cd-modal" role="dialog" aria-modal="true">
        <div class="cd-title">{{ store.current?.title || '确认操作' }}</div>
        <div class="cd-msg">{{ store.current?.message }}</div>
        <div class="cd-actions">
          <button class="cd-btn" type="button" @click="cancel">{{ store.current?.cancelText || '取消' }}</button>
          <button
            class="cd-btn"
            :class="store.current?.danger ? 'cd-danger' : 'cd-primary'"
            type="button"
            @click="ok"
          >{{ store.current?.okText || '确认' }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.cd-mask { position: fixed; inset: 0; background: rgba(9,9,11,0.5); backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center; z-index: 100; padding: 1rem; }
.cd-modal { width: min(420px, 100%); background: white; border-radius: 12px; padding: 20px; box-shadow: 0 20px 40px rgba(0,0,0,0.25); }
.cd-title { font-size: 0.95rem; font-weight: 700; color: var(--color-ink); margin-bottom: 8px; }
.cd-msg { font-size: 0.875rem; color: var(--color-ink-light); white-space: pre-wrap; line-height: 1.5; margin-bottom: 16px; }
.cd-actions { display: flex; justify-content: flex-end; gap: 8px; }
.cd-btn { padding: 6px 14px; font-size: 13px; border-radius: 6px; border: 1px solid var(--color-control-border); background: white; cursor: pointer; }
.cd-btn:hover { background: var(--color-surface-muted); }
.cd-primary { background: var(--color-leather); color: var(--color-parchment); border-color: var(--color-leather); font-weight: 600; }
.cd-primary:hover { background: var(--color-leather-light); }
.cd-danger { background: #dc2626; color: white; border-color: #dc2626; font-weight: 600; }
.cd-danger:hover { background: #b91c1c; }
</style>
