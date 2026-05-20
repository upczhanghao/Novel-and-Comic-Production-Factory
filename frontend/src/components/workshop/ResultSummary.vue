<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  title: string
  content?: string
  llm?: string
  embedding?: string
  styleName?: string
  narrativeStyle?: string
  startedAt?: number | null
  endedAt?: number | null
}

const props = defineProps<Props>()

const wordCount = computed(() => {
  const text = props.content ?? ''
  return text.replace(/\s+/g, '').length
})

const lineCount = computed(() => (props.content ?? '').split('\n').filter((l) => l.trim()).length)

const elapsed = computed(() => {
  if (!props.startedAt || !props.endedAt) return null
  const ms = props.endedAt - props.startedAt
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`
})
</script>

<template>
  <div v-if="props.content" class="rs-card">
    <div class="rs-title">
      <span class="rs-dot" />
      {{ props.title }} · 生成完成
    </div>
    <div class="rs-grid">
      <div class="rs-cell">
        <div class="rs-k">字数</div>
        <div class="rs-v">{{ wordCount.toLocaleString() }}</div>
      </div>
      <div class="rs-cell">
        <div class="rs-k">行数</div>
        <div class="rs-v">{{ lineCount }}</div>
      </div>
      <div v-if="elapsed" class="rs-cell">
        <div class="rs-k">耗时</div>
        <div class="rs-v">{{ elapsed }}</div>
      </div>
      <div v-if="props.llm" class="rs-cell">
        <div class="rs-k">LLM</div>
        <div class="rs-v" :title="props.llm">{{ props.llm }}</div>
      </div>
      <div v-if="props.embedding" class="rs-cell">
        <div class="rs-k">Embedding</div>
        <div class="rs-v">{{ props.embedding }}</div>
      </div>
      <div v-if="props.styleName && props.styleName !== '不使用文风'" class="rs-cell">
        <div class="rs-k">文风</div>
        <div class="rs-v">{{ props.styleName }}</div>
      </div>
      <div v-if="props.narrativeStyle && props.narrativeStyle !== '不使用文风'" class="rs-cell">
        <div class="rs-k">叙事 DNA</div>
        <div class="rs-v">{{ props.narrativeStyle }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.rs-card { margin-top: 12px; padding: 10px 14px; border-radius: 10px; background: linear-gradient(to right, #ecfdf5, #f0fdf4); border: 1px solid #a7f3d0; }
.rs-title { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #065f46; font-weight: 600; margin-bottom: 8px; }
.rs-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--color-success); }
.rs-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 10px; }
.rs-cell { font-size: 12px; }
.rs-k { color: #065f46; opacity: 0.7; font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; }
.rs-v { color: #064e3b; font-weight: 500; margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
