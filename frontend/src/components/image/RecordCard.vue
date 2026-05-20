<script setup lang="ts">
import { relativeTime, sourceLabel } from '@/composables/useImageFilters'

export interface ImageRecord {
  id: string
  path?: string
  filename?: string
  url: string
  download_url?: string
  prompt?: string
  config_name?: string
  model?: string
  size?: string
  provider?: string
  source_type?: string
  source_id?: string
  created_at?: string
}

const props = defineProps<{
  record: ImageRecord
  selected?: boolean
}>()

const emit = defineEmits<{
  (e: 'select'): void
  (e: 'view'): void
  (e: 'retry'): void
  (e: 'delete'): void
  (e: 'copyPrompt'): void
  (e: 'copyParams'): void
}>()
</script>

<template>
  <div class="rc-root" :class="{ selected }" @click="emit('view')">
    <div class="rc-check" @click.stop>
      <input type="checkbox" :checked="selected" @change="emit('select')" />
    </div>
    <img :src="record.url" :alt="record.filename" class="rc-thumb" loading="lazy" />
    <div class="rc-meta">
      <span class="rc-source">{{ sourceLabel(record) }}</span>
      <span v-if="record.model" class="rc-chip">{{ record.model }}</span>
      <span v-if="record.size" class="rc-chip">{{ record.size }}</span>
    </div>
    <div class="rc-time">{{ relativeTime(record.created_at) }}</div>
    <div class="rc-actions" @click.stop>
      <button type="button" title="复制提示词" @click="emit('copyPrompt')">📋</button>
      <button type="button" title="复制参数" @click="emit('copyParams')">⚙</button>
      <button type="button" title="重试" @click="emit('retry')">🔄</button>
      <a :href="record.download_url || record.url" target="_blank" title="下载">⬇</a>
      <button type="button" title="删除" class="rc-del" @click="emit('delete')">🗑</button>
    </div>
  </div>
</template>

<style scoped>
.rc-root { position: relative; border-radius: 8px; border: 1px solid var(--color-control-border); overflow: hidden; cursor: pointer; transition: box-shadow 0.15s, border-color 0.15s; background: white; }
.rc-root:hover { border-color: var(--color-leather-light); box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.rc-root.selected { border-color: var(--color-gold); box-shadow: 0 0 0 2px rgba(200,160,60,0.2); }
.rc-check { position: absolute; top: 6px; left: 6px; z-index: 2; }
.rc-check input { width: 16px; height: 16px; cursor: pointer; accent-color: var(--color-gold); }
.rc-thumb { width: 100%; aspect-ratio: 2/3; object-fit: cover; background: var(--color-parchment); display: block; }
.rc-meta { display: flex; flex-wrap: wrap; gap: 4px; padding: 6px 8px 2px; }
.rc-source { font-size: 10px; padding: 1px 6px; border-radius: 999px; background: var(--color-surface-muted); color: var(--color-ink-light); }
.rc-chip { font-size: 10px; padding: 1px 6px; border-radius: 999px; background: #dbeafe; color: #1e40af; }
.rc-time { padding: 0 8px 4px; font-size: 10px; color: var(--color-ink-light); }
.rc-actions { display: flex; gap: 2px; padding: 4px 6px 6px; border-top: 1px solid var(--color-control-border); }
.rc-actions button, .rc-actions a { flex: 1; padding: 4px 0; font-size: 12px; text-align: center; border: none; background: transparent; cursor: pointer; border-radius: 4px; text-decoration: none; }
.rc-actions button:hover, .rc-actions a:hover { background: var(--color-surface-muted); }
.rc-del:hover { background: #fef2f2 !important; }
</style>
