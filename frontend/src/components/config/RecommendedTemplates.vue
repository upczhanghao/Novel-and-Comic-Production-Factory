<script setup lang="ts">
import { TEMPLATES, type RecommendedTemplate, type TemplateKind } from './templates'

const emit = defineEmits<{ (e: 'apply', tpl: RecommendedTemplate): void }>()

function badgeFor(kind: TemplateKind) {
  return kind === 'llm' ? 'LLM' : kind === 'embedding' ? 'Embedding' : 'Image'
}
</script>

<template>
  <div class="rt-root">
    <div class="rt-head">
      <h3 class="rt-title">推荐配置模板</h3>
      <p class="rt-subtitle">点击任意卡片把预设值填入下方表单，再补 API Key 即可保存。</p>
    </div>
    <div class="rt-grid">
      <button
        v-for="t in TEMPLATES"
        :key="t.id"
        type="button"
        class="rt-card"
        :class="`kind-${t.kind}`"
        :aria-label="`应用模板：${t.label}（${badgeFor(t.kind)}）`"
        @click="emit('apply', t)"
      >
        <div class="rt-card-top">
          <span class="rt-icon">{{ t.icon }}</span>
          <span class="rt-badge">{{ badgeFor(t.kind) }}</span>
        </div>
        <div class="rt-card-name">{{ t.label }}</div>
        <div class="rt-card-desc">{{ t.description }}</div>
      </button>
    </div>
  </div>
</template>

<style scoped>
.rt-root { padding: 14px 16px; background: linear-gradient(135deg, var(--color-parchment), var(--color-surface-muted)); border: 1px solid var(--color-control-border); border-radius: 10px; }
.rt-head { margin-bottom: 10px; }
.rt-title { font-size: 14px; font-weight: 700; color: var(--color-ink); margin: 0; }
.rt-subtitle { font-size: 11px; color: var(--color-ink-light); margin: 2px 0 0; }
.rt-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px; }
.rt-card { display: flex; flex-direction: column; gap: 4px; padding: 10px 12px; background: white; border: 1px solid var(--color-control-border); border-radius: 8px; cursor: pointer; text-align: left; transition: all 0.15s; }
.rt-card:hover { border-color: var(--color-leather-light); box-shadow: 0 2px 8px rgba(0,0,0,0.05); transform: translateY(-1px); }
.rt-card-top { display: flex; align-items: center; justify-content: space-between; }
.rt-icon { font-size: 18px; }
.rt-badge { font-size: 9px; padding: 1px 6px; border-radius: 999px; background: var(--color-surface-muted); color: var(--color-ink-light); font-weight: 600; letter-spacing: 0.05em; }
.rt-card.kind-llm .rt-badge { background: #dbeafe; color: #1e40af; }
.rt-card.kind-embedding .rt-badge { background: #d1fae5; color: #065f46; }
.rt-card.kind-image .rt-badge { background: #fce7f3; color: #9d174d; }
.rt-card-name { font-size: 13px; font-weight: 600; color: var(--color-ink); }
.rt-card-desc { font-size: 11px; color: var(--color-ink-light); line-height: 1.4; }
</style>
