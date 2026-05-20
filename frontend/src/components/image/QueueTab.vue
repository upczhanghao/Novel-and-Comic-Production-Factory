<script setup lang="ts">
import { computed, ref } from 'vue'
import { sourceLabel } from '@/composables/useImageFilters'

export interface PromptItem {
  id: string
  title: string
  prompt: string
  negative_prompt?: string
  source_type?: string
  source_id?: string
}

const props = defineProps<{
  items: PromptItem[]
  selected: string[]
  activeId?: string | null
  busy?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:selected', v: string[]): void
  (e: 'use', item: PromptItem): void
  (e: 'copyPrompt', item: PromptItem): void
  (e: 'copyParams', item: PromptItem): void
  (e: 'delete', item: PromptItem): void
  (e: 'batchGenerate', items: PromptItem[]): void
  (e: 'batchDelete', items: PromptItem[]): void
}>()

const search = ref('')

const filtered = computed(() => {
  const kw = search.value.trim().toLowerCase()
  if (!kw) return props.items
  return props.items.filter((i) =>
    `${i.title} ${i.prompt} ${i.source_id ?? ''}`.toLowerCase().includes(kw),
  )
})

const selectedItems = computed(() => props.items.filter((i) => props.selected.includes(i.id)))
const allFilteredSelected = computed(
  () => filtered.value.length > 0 && filtered.value.every((i) => props.selected.includes(i.id)),
)

function toggleOne(id: string) {
  const next = props.selected.includes(id)
    ? props.selected.filter((x) => x !== id)
    : [...props.selected, id]
  emit('update:selected', next)
}

function toggleAll() {
  if (allFilteredSelected.value) {
    const ids = new Set(filtered.value.map((i) => i.id))
    emit('update:selected', props.selected.filter((x) => !ids.has(x)))
  } else {
    const set = new Set(props.selected)
    filtered.value.forEach((i) => set.add(i.id))
    emit('update:selected', Array.from(set))
  }
}

function clearSel() { emit('update:selected', []) }
</script>

<template>
  <div class="qt-root">
    <div class="qt-toolbar">
      <input v-model="search" placeholder="搜索标题 / 来源 / 提示词…" class="qt-search" />
      <div class="qt-bar">
        <span class="qt-count">{{ selected.length }} / {{ items.length }} 已选</span>
        <button class="qt-btn" type="button" @click="toggleAll">
          {{ allFilteredSelected ? '取消全选' : '全选' }}
        </button>
        <button class="qt-btn" type="button" :disabled="!selected.length" @click="clearSel">清空</button>
        <button
          class="qt-btn primary"
          type="button"
          :disabled="!selected.length || busy"
          @click="emit('batchGenerate', selectedItems)"
        >批量生成</button>
        <button
          class="qt-btn danger"
          type="button"
          :disabled="!selected.length"
          @click="emit('batchDelete', selectedItems)"
        >批量删除</button>
      </div>
    </div>

    <div class="qt-list">
      <div v-if="!filtered.length" class="qt-empty">
        {{ items.length ? '没有匹配的提示词' : '暂无导入提示词。前往「漫剧制作」批量导入分镜/角色提示词。' }}
      </div>
      <div
        v-for="item in filtered"
        :key="item.id"
        class="qt-item"
        :class="{ active: activeId === item.id, selected: selected.includes(item.id) }"
      >
        <input
          type="checkbox"
          :checked="selected.includes(item.id)"
          @change="toggleOne(item.id)"
          class="qt-check"
        />
        <div class="qt-body" @click="emit('use', item)">
          <div class="qt-title-row">
            <div class="qt-title">{{ item.title || item.id }}</div>
            <span class="qt-source">{{ sourceLabel(item) }}</span>
          </div>
          <div class="qt-prompt">{{ item.prompt }}</div>
          <div v-if="item.negative_prompt" class="qt-neg">负向：{{ item.negative_prompt }}</div>
        </div>
        <div class="qt-ops">
          <button type="button" @click="emit('use', item)" title="使用">使用</button>
          <button type="button" @click="emit('copyPrompt', item)" title="复制提示词">📋</button>
          <button type="button" @click="emit('copyParams', item)" title="复制参数">⚙</button>
          <button type="button" class="qt-del" @click="emit('delete', item)" title="删除">🗑</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.qt-root { display: flex; flex-direction: column; gap: 10px; }
.qt-toolbar { display: flex; flex-direction: column; gap: 6px; }
.qt-search { padding: 6px 10px; font-size: 12px; border-radius: 6px; border: 1px solid var(--color-control-border); background: white; }
.qt-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; padding: 8px 10px; background: var(--color-surface-muted); border: 1px solid var(--color-control-border); border-radius: 8px; }
.qt-count { font-size: 12px; color: var(--color-ink-light); margin-right: auto; }
.qt-btn { padding: 4px 10px; font-size: 12px; border-radius: 6px; border: 1px solid var(--color-control-border); background: white; cursor: pointer; }
.qt-btn:hover:not(:disabled) { border-color: var(--color-leather-light); }
.qt-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.qt-btn.primary { background: var(--color-ink); color: white; border-color: var(--color-ink); }
.qt-btn.danger { color: var(--color-error); border-color: #fecaca; }
.qt-btn.danger:hover:not(:disabled) { background: var(--color-error); color: white; }
.qt-list { display: flex; flex-direction: column; gap: 6px; max-height: calc(100vh - 380px); min-height: 240px; overflow: auto; padding-right: 2px; }
.qt-empty { font-size: 13px; color: var(--color-ink-light); text-align: center; padding: 24px; border: 1px dashed var(--color-control-border); border-radius: 8px; }
.qt-item { display: flex; align-items: flex-start; gap: 8px; padding: 8px 10px; background: white; border: 1px solid var(--color-control-border); border-radius: 8px; transition: border-color 0.15s; }
.qt-item:hover { border-color: var(--color-leather-light); }
.qt-item.active { border-color: var(--color-gold); box-shadow: 0 0 0 2px rgba(200,160,60,0.15); }
.qt-item.selected { background: #fef9e7; }
.qt-check { width: 16px; height: 16px; margin-top: 2px; accent-color: var(--color-gold); cursor: pointer; }
.qt-body { flex: 1; min-width: 0; cursor: pointer; }
.qt-title-row { display: flex; align-items: center; gap: 6px; }
.qt-title { font-size: 13px; font-weight: 600; color: var(--color-ink); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.qt-source { font-size: 10px; padding: 1px 6px; border-radius: 999px; background: var(--color-surface-muted); color: var(--color-ink-light); white-space: nowrap; }
.qt-prompt { font-size: 11px; color: var(--color-ink-light); margin-top: 2px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.qt-neg { font-size: 10px; color: #b91c1c; margin-top: 2px; opacity: 0.8; display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical; overflow: hidden; }
.qt-ops { display: flex; flex-direction: column; gap: 2px; }
.qt-ops button { padding: 2px 6px; font-size: 11px; border-radius: 4px; border: 1px solid transparent; background: transparent; cursor: pointer; }
.qt-ops button:hover { background: var(--color-surface-muted); }
.qt-ops .qt-del:hover { background: #fef2f2; color: var(--color-error); }
</style>
