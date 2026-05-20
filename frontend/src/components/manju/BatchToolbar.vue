<script setup lang="ts">
import { computed } from 'vue'

interface Selectable { id: string; locked?: boolean; [k: string]: unknown }

const props = defineProps<{
  total: number
  selected: string[]
  showRegenerate?: boolean
  showQueueImport?: boolean
}>()

const emit = defineEmits<{
  (e: 'selectAll'): void
  (e: 'clear'): void
  (e: 'lock'): void
  (e: 'unlock'): void
  (e: 'delete'): void
  (e: 'regenerate'): void
  (e: 'queueImport'): void
}>()

const hasSelection = computed(() => props.selected.length > 0)
</script>

<template>
  <div class="bt-root">
    <div class="bt-left">
      <span class="bt-count">{{ selected.length }} / {{ total }} 已选</span>
      <button class="bt-btn" @click="emit('selectAll')" type="button">全选</button>
      <button class="bt-btn" @click="emit('clear')" :disabled="!hasSelection" type="button">清空</button>
    </div>
    <div class="bt-right">
      <button class="bt-btn" @click="emit('lock')" :disabled="!hasSelection" type="button">批量锁定</button>
      <button class="bt-btn" @click="emit('unlock')" :disabled="!hasSelection" type="button">批量解锁</button>
      <button v-if="showRegenerate" class="bt-btn" @click="emit('regenerate')" :disabled="!hasSelection" type="button">批量重生成</button>
      <button v-if="showQueueImport" class="bt-btn primary" @click="emit('queueImport')" :disabled="!hasSelection" type="button">导入图片队列</button>
      <button class="bt-btn danger" @click="emit('delete')" :disabled="!hasSelection" type="button">批量删除</button>
    </div>
  </div>
</template>

<style scoped>
.bt-root { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 6px; padding: 8px 10px; background: var(--color-surface-muted); border: 1px solid var(--color-control-border); border-radius: 8px; }
.bt-left, .bt-right { display: flex; gap: 4px; flex-wrap: wrap; align-items: center; }
.bt-count { font-size: 12px; color: var(--color-ink-light); margin-right: 6px; }
.bt-btn { padding: 4px 10px; font-size: 12px; border-radius: 6px; border: 1px solid var(--color-control-border); background: white; cursor: pointer; }
.bt-btn:hover:not(:disabled) { border-color: var(--color-leather-light); }
.bt-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.bt-btn.primary { background: var(--color-ink); color: white; border-color: var(--color-ink); }
.bt-btn.danger { color: var(--color-error); border-color: #fecaca; }
.bt-btn.danger:hover:not(:disabled) { background: var(--color-error); color: white; border-color: var(--color-error); }
</style>
