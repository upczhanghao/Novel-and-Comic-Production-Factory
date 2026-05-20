<script setup lang="ts">
import { computed, ref } from 'vue'

interface PromptPair {
  id: string
  label: string
  before: string
  after: string
}

const props = defineProps<{ pairs: PromptPair[] }>()
const emit = defineEmits<{
  (e: 'apply', id: string): void
  (e: 'revert', id: string): void
  (e: 'applyAll'): void
  (e: 'revertAll'): void
}>()

const selected = ref<string | null>(null)
const expanded = computed(() => props.pairs.find((p) => p.id === selected.value) ?? props.pairs[0])
const changedCount = computed(() => props.pairs.filter((p) => p.before !== p.after).length)
</script>

<template>
  <div v-if="pairs.length" class="ed-root">
    <div class="ed-header">
      <div>
        <strong>提示词增强结果</strong>
        <span class="ed-count">{{ changedCount }} / {{ pairs.length }} 条有变化</span>
      </div>
      <div class="ed-actions">
        <button class="ed-btn" @click="emit('revertAll')" type="button">全部还原</button>
        <button class="ed-btn primary" @click="emit('applyAll')" type="button">全部应用</button>
      </div>
    </div>
    <div class="ed-body">
      <ul class="ed-list">
        <li
          v-for="p in pairs"
          :key="p.id"
          :class="{ active: expanded?.id === p.id, changed: p.before !== p.after }"
          @click="selected = p.id"
        >
          <span class="ed-dot" />
          <span class="ed-label">{{ p.label }}</span>
        </li>
      </ul>
      <div class="ed-compare" v-if="expanded">
        <div class="ed-col">
          <div class="ed-col-title">原始</div>
          <pre>{{ expanded.before }}</pre>
        </div>
        <div class="ed-col">
          <div class="ed-col-title">增强后</div>
          <pre>{{ expanded.after }}</pre>
        </div>
      </div>
      <div class="ed-single" v-if="expanded">
        <button class="ed-btn small" @click="emit('revert', expanded.id)" type="button">本条还原</button>
        <button class="ed-btn small primary" @click="emit('apply', expanded.id)" type="button">本条应用</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ed-root { margin-top: 10px; padding: 12px; background: var(--color-surface); border: 1px solid var(--color-control-border); border-radius: 10px; }
.ed-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.ed-header strong { font-size: 13px; }
.ed-count { font-size: 11px; color: var(--color-ink-light); margin-left: 8px; }
.ed-actions { display: flex; gap: 6px; }
.ed-btn { padding: 4px 12px; border-radius: 6px; border: 1px solid var(--color-control-border); background: white; font-size: 12px; cursor: pointer; }
.ed-btn.primary { background: var(--color-ink); color: white; border-color: var(--color-ink); }
.ed-btn.small { padding: 3px 10px; font-size: 11px; }
.ed-body { display: grid; grid-template-columns: 180px 1fr; gap: 12px; }
@media (max-width: 700px) { .ed-body { grid-template-columns: 1fr; } }
.ed-list { list-style: none; padding: 0; margin: 0; max-height: 260px; overflow-y: auto; }
.ed-list li { display: flex; align-items: center; gap: 6px; padding: 5px 8px; border-radius: 6px; font-size: 12px; cursor: pointer; }
.ed-list li:hover { background: var(--color-surface-muted); }
.ed-list li.active { background: var(--color-surface-muted); font-weight: 600; }
.ed-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--color-control-border); }
.ed-list li.changed .ed-dot { background: var(--color-gold); }
.ed-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ed-compare { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
@media (max-width: 700px) { .ed-compare { grid-template-columns: 1fr; } }
.ed-col { background: var(--color-surface-muted); border-radius: 6px; padding: 8px; min-height: 200px; max-height: 280px; overflow-y: auto; }
.ed-col-title { font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--color-ink-light); font-weight: 600; margin-bottom: 4px; }
.ed-col pre { font-family: var(--font-mono); font-size: 11px; white-space: pre-wrap; margin: 0; color: var(--color-ink); line-height: 1.5; }
.ed-single { grid-column: 2; display: flex; justify-content: flex-end; gap: 6px; margin-top: 6px; }
@media (max-width: 700px) { .ed-single { grid-column: 1; } }
</style>
