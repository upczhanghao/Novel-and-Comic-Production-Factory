<script setup lang="ts">
import { computed } from 'vue'
import { classifyImageError } from '@/composables/useImageError'

const props = defineProps<{ message: string }>()
const emit = defineEmits<{ (e: 'dismiss'): void }>()

const classified = computed(() => classifyImageError(props.message))
</script>

<template>
  <div v-if="message" class="err-root" :class="`err-${classified.category}`">
    <div class="err-icon">⚠</div>
    <div class="err-body">
      <div class="err-title">{{ classified.title }}</div>
      <div class="err-hint">{{ classified.hint }}</div>
      <details class="err-detail">
        <summary>查看原始错误</summary>
        <pre>{{ classified.detail }}</pre>
      </details>
    </div>
    <div class="err-actions">
      <router-link
        v-if="classified.category === 'auth' || classified.category === 'model' || classified.category === 'config'"
        to="/config"
        class="err-btn"
      >前往配置</router-link>
      <button class="err-btn ghost" type="button" @click="emit('dismiss')">关闭</button>
    </div>
  </div>
</template>

<style scoped>
.err-root { display: flex; gap: 10px; padding: 10px 12px; border-radius: 8px; border: 1px solid #fecaca; background: #fef2f2; }
.err-root.err-quota { background: #fffbeb; border-color: #fde68a; }
.err-root.err-network { background: #eff6ff; border-color: #bfdbfe; }
.err-root.err-size, .err-root.err-config { background: #f5f3ff; border-color: #ddd6fe; }
.err-icon { font-size: 16px; line-height: 1; color: var(--color-error); flex-shrink: 0; padding-top: 2px; }
.err-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.err-title { font-size: 13px; font-weight: 600; color: var(--color-ink); }
.err-hint { font-size: 12px; color: var(--color-ink-light); line-height: 1.5; }
.err-detail { font-size: 11px; color: var(--color-ink-light); }
.err-detail summary { cursor: pointer; user-select: none; padding: 2px 0; }
.err-detail pre { margin: 4px 0 0; padding: 6px 8px; background: rgba(0,0,0,0.04); border-radius: 4px; white-space: pre-wrap; word-break: break-all; font-size: 10px; max-height: 120px; overflow: auto; }
.err-actions { display: flex; flex-direction: column; gap: 4px; flex-shrink: 0; }
.err-btn { padding: 4px 10px; font-size: 11px; border-radius: 6px; border: 1px solid var(--color-ink); background: var(--color-ink); color: white; text-decoration: none; text-align: center; cursor: pointer; }
.err-btn.ghost { background: transparent; color: var(--color-ink); }
.err-btn:hover { opacity: 0.85; }
</style>
