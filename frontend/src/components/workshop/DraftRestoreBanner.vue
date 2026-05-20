<script setup lang="ts">
import type { Ref } from 'vue'

interface DraftSnapshot { ts: number; fields: Record<string, unknown> }

defineProps<{ snapshot: DraftSnapshot | null | { ts: number } }>()
const emit = defineEmits<{ (e: 'restore'): void; (e: 'discard'): void }>()

function fmt(ts: number) {
  const diff = (Date.now() - ts) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  return `${Math.floor(diff / 3600)} 小时前`
}
</script>

<template>
  <div v-if="snapshot" class="dr-banner">
    <span class="dr-icon">💾</span>
    <div class="dr-text">
      <strong>检测到 {{ fmt((snapshot as DraftSnapshot).ts) }}的草稿</strong>
      <p>包含未保存到项目文件的字段（架构步骤、章节字段等）。</p>
    </div>
    <div class="dr-actions">
      <button class="dr-btn primary" @click="emit('restore')" type="button">恢复</button>
      <button class="dr-btn" @click="emit('discard')" type="button">忽略</button>
    </div>
  </div>
</template>

<style scoped>
.dr-banner { display: flex; align-items: flex-start; gap: 12px; padding: 12px 16px; border-radius: 10px; background: linear-gradient(to right, #fef3c7, #fef9c3); border: 1px solid #fde68a; }
.dr-icon { font-size: 20px; flex-shrink: 0; }
.dr-text { flex: 1; min-width: 0; }
.dr-text strong { display: block; font-size: 13px; color: #78350f; }
.dr-text p { margin: 2px 0 0; font-size: 12px; color: #92400e; }
.dr-actions { display: flex; gap: 6px; flex-shrink: 0; }
.dr-btn { padding: 4px 12px; border-radius: 6px; border: 1px solid #fde68a; background: white; color: #78350f; font-size: 12px; cursor: pointer; }
.dr-btn.primary { background: var(--color-ink); color: white; border-color: var(--color-ink); }
</style>
