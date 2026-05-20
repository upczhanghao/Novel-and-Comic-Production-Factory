<script setup lang="ts">
import { ref, computed } from 'vue'
import type { HistoryKind, HistorySnapshot } from '@/composables/useManjuHistory'

const props = defineProps<{
  kind: HistoryKind
  label: string
  list: HistorySnapshot[]
}>()

const emit = defineEmits<{
  (e: 'restore', snap: HistorySnapshot): void
  (e: 'remove', ts: number): void
}>()

const open = ref(false)
const previewing = ref<HistorySnapshot | null>(null)

function fmt(ts: number) {
  const d = new Date(ts)
  return d.toLocaleString()
}

function previewText(snap: HistorySnapshot) {
  const p = snap.payload
  if (typeof p === 'string') return p.slice(0, 800)
  try { return JSON.stringify(p, null, 2).slice(0, 800) } catch { return '' }
}

const count = computed(() => props.list.length)
</script>

<template>
  <div class="vh-root">
    <button class="vh-toggle" @click="open = !open" type="button">
      <span>{{ props.label }}版本历史</span>
      <span class="vh-count">{{ count }}</span>
      <span class="vh-arrow">{{ open ? '▾' : '▸' }}</span>
    </button>
    <div v-if="open" class="vh-body">
      <div v-if="!count" class="vh-empty">还没有历史快照。每次保存或自动同步时会自动入栈。</div>
      <ul v-else class="vh-list">
        <li v-for="snap in props.list" :key="snap.ts" :class="{ active: previewing?.ts === snap.ts }">
          <div class="vh-line" @click="previewing = previewing?.ts === snap.ts ? null : snap">
            <span class="vh-time">{{ fmt(snap.ts) }}</span>
            <div class="vh-acts">
              <button @click.stop="emit('restore', snap)" class="vh-btn" type="button">回滚</button>
              <button @click.stop="emit('remove', snap.ts)" class="vh-btn danger" type="button">删除</button>
            </div>
          </div>
          <pre v-if="previewing?.ts === snap.ts" class="vh-preview">{{ previewText(snap) }}</pre>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.vh-root { border: 1px solid var(--color-control-border); border-radius: 8px; background: var(--color-surface); margin-top: 8px; }
.vh-toggle { display: flex; align-items: center; gap: 8px; width: 100%; padding: 8px 12px; background: transparent; border: 0; cursor: pointer; font-size: 12px; color: var(--color-ink); }
.vh-count { background: var(--color-control-border); color: var(--color-ink-light); padding: 1px 8px; border-radius: 999px; font-size: 11px; }
.vh-arrow { margin-left: auto; opacity: 0.5; }
.vh-body { padding: 0 12px 12px; border-top: 1px dashed var(--color-control-border); }
.vh-empty { padding: 12px 0; font-size: 11px; color: var(--color-ink-light); }
.vh-list { list-style: none; padding: 0; margin: 0; max-height: 320px; overflow-y: auto; }
.vh-list li { border-bottom: 1px solid var(--color-control-border); }
.vh-list li.active { background: var(--color-surface-muted); }
.vh-line { display: flex; align-items: center; justify-content: space-between; padding: 6px 8px; cursor: pointer; }
.vh-time { font-size: 12px; color: var(--color-ink); font-family: var(--font-mono); }
.vh-acts { display: flex; gap: 4px; }
.vh-btn { padding: 2px 8px; font-size: 11px; border-radius: 4px; border: 1px solid var(--color-control-border); background: white; cursor: pointer; }
.vh-btn.danger { color: var(--color-error); border-color: #fecaca; }
.vh-preview { margin: 6px 0; padding: 8px; background: white; border: 1px solid var(--color-control-border); border-radius: 4px; font-family: var(--font-mono); font-size: 10px; max-height: 200px; overflow: auto; white-space: pre-wrap; }
</style>
