<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { configApi } from '@/api/client'

type Status = 'ok' | 'warning' | 'error' | 'missing' | 'unknown'

interface HealthGroup { status: Status; count: number; default?: string; missing_slots?: string[] }
interface HealthPayload {
  overall: Status
  llm: HealthGroup
  embedding: HealthGroup
  image: HealthGroup
}

const data = ref<HealthPayload | null>(null)
const open = ref(false)
let timer: number | null = null

async function poll() {
  try {
    const res = await configApi.health()
    data.value = res.data as HealthPayload
  } catch {
    data.value = null
  }
}

onMounted(() => {
  poll()
  timer = window.setInterval(poll, 60_000)
})
onUnmounted(() => { if (timer) clearInterval(timer) })

const dotClass = computed(() => {
  const s = data.value?.overall ?? 'unknown'
  return `dot-${s}`
})

const tip = computed(() => {
  if (!data.value) return '加载中…'
  const map: Record<Status, string> = { ok: '配置正常', warning: '部分配置缺失', error: '关键配置缺失', missing: '未配置', unknown: '未知' }
  return map[data.value.overall]
})

function labelFor(s: Status) {
  return { ok: '✓', warning: '!', error: '✕', missing: '–', unknown: '?' }[s]
}
</script>

<template>
  <div class="ch-wrap">
    <button class="ch-btn" @click="open = !open" type="button" :title="tip">
      <span class="ch-dot" :class="dotClass" />
      <span class="ch-text">配置 {{ labelFor(data?.overall ?? 'unknown') }}</span>
    </button>
    <div v-if="open && data" class="ch-pop">
      <div class="ch-row">
        <span class="ch-dot" :class="`dot-${data.llm.status}`" />
        <span>LLM</span><strong>{{ data.llm.count }} 个</strong>
        <router-link v-if="data.llm.status !== 'ok'" to="/config" class="ch-link" @click="open = false">前往</router-link>
      </div>
      <div class="ch-row">
        <span class="ch-dot" :class="`dot-${data.embedding.status}`" />
        <span>Embedding</span><strong>{{ data.embedding.count }} 个</strong>
        <router-link v-if="data.embedding.status !== 'ok'" to="/config" class="ch-link" @click="open = false">前往</router-link>
      </div>
      <div class="ch-row">
        <span class="ch-dot" :class="`dot-${data.image.status}`" />
        <span>图片</span><strong>{{ data.image.count }} 个</strong>
        <router-link v-if="data.image.status !== 'ok'" to="/config" class="ch-link" @click="open = false">前往</router-link>
      </div>
      <div v-if="data.llm.missing_slots?.length" class="ch-warn">
        未指派槽位：{{ data.llm.missing_slots.join('、') }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.ch-wrap { position: relative; }
.ch-btn { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; font-size: 11px; background: #fff; border: 1px solid #d4d4d8; border-radius: 6px; color: var(--color-ink); cursor: pointer; transition: border-color 0.15s, box-shadow 0.15s; }
.ch-btn:hover { border-color: var(--color-leather-light); box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12); }
.ch-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.ch-text { font-family: var(--font-mono); }
.dot-ok { background: #10b981; box-shadow: 0 0 0 2px rgba(16,185,129,0.25); }
.dot-warning { background: #f59e0b; box-shadow: 0 0 0 2px rgba(245,158,11,0.25); }
.dot-error { background: #ef4444; box-shadow: 0 0 0 2px rgba(239,68,68,0.25); }
.dot-missing { background: #6b7280; }
.dot-unknown { background: #6b7280; opacity: 0.5; }
.ch-pop { position: absolute; bottom: calc(100% + 6px); left: 0; min-width: 240px; background: white; color: var(--color-ink); border-radius: 8px; padding: 8px; box-shadow: 0 8px 24px rgba(0,0,0,0.18); z-index: 40; }
.ch-row { display: flex; align-items: center; gap: 8px; padding: 4px 6px; font-size: 12px; }
.ch-row strong { margin-left: auto; color: var(--color-ink-light); font-weight: 500; font-size: 11px; }
.ch-link { color: var(--color-leather-light); font-size: 11px; padding-left: 6px; }
.ch-warn { padding: 4px 6px; margin-top: 4px; font-size: 10px; color: #b45309; background: #fef3c7; border-radius: 4px; }
</style>
