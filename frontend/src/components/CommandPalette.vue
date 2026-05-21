<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useUIStore } from '@/stores/ui'
import { useProjectStore } from '@/stores/project'
import { useConfigStore } from '@/stores/config'
import { presetsApi, stylesApi } from '@/api/client'
import { navRoutes, type NavMeta } from '@/router'

interface PaletteItem {
  id: string
  kind: '模块' | '项目' | '提示词方案' | '文风' | 'LLM 配置' | 'Embedding 配置' | '图片配置' | '操作'
  label: string
  hint?: string
  action: () => unknown | Promise<unknown>
}

const ui = useUIStore()
const router = useRouter()
const projectStore = useProjectStore()
const configStore = useConfigStore()

const query = ref('')
const cursor = ref(0)
const inputRef = ref<HTMLInputElement | null>(null)
const presets = ref<string[]>([])
const stylesList = ref<string[]>([])

// A14: 模块列表派生自 router meta
const modules = navRoutes
  .filter((r) => !r.meta?.hidden && (r.meta as NavMeta | undefined)?.title)
  .map((r) => ({ path: r.path, label: (r.meta as NavMeta).title }))

const allItems = computed<PaletteItem[]>(() => {
  const items: PaletteItem[] = []
  for (const m of modules) {
    items.push({ id: `m:${m.path}`, kind: '模块', label: m.label, hint: m.path, action: () => router.push(m.path) })
  }
  for (const p of projectStore.projects) {
    items.push({
      id: `p:${p}`, kind: '项目', label: p,
      hint: p === projectStore.activeProject ? '当前项目' : '点击切换',
      action: () => projectStore.activateProject(p),
    })
  }
  for (const name of presets.value) {
    items.push({
      id: `pr:${name}`, kind: '提示词方案', label: name, hint: '激活',
      action: () => presetsApi.activate(name),
    })
  }
  for (const s of stylesList.value) {
    items.push({ id: `s:${s}`, kind: '文风', label: s, hint: '前往文风与DNA', action: () => router.push('/styles') })
  }
  for (const n of Object.keys(configStore.llmConfigs)) {
    items.push({ id: `llm:${n}`, kind: 'LLM 配置', label: n, hint: '前往模型配置', action: () => router.push('/config') })
  }
  for (const n of Object.keys(configStore.embeddingConfigs)) {
    items.push({ id: `emb:${n}`, kind: 'Embedding 配置', label: n, hint: '前往模型配置', action: () => router.push('/config') })
  }
  for (const n of Object.keys(configStore.imageConfigs)) {
    items.push({ id: `img:${n}`, kind: '图片配置', label: n, hint: '前往模型配置', action: () => router.push('/config') })
  }
  items.push({ id: 'op:onb', kind: '操作', label: '重新打开首次设置向导', action: () => ui.resetOnboarding() })
  items.push({
    id: 'op:mode', kind: '操作',
    label: ui.isBeginner ? '切换到高级模式' : '切换到新手模式',
    action: () => ui.setMode(ui.isBeginner ? 'advanced' : 'beginner'),
  })
  return items
})

const results = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return allItems.value.slice(0, 30)
  return allItems.value.filter((i) =>
    i.label.toLowerCase().includes(q) || i.kind.toLowerCase().includes(q) || (i.hint ?? '').toLowerCase().includes(q),
  ).slice(0, 50)
})

watch(() => results.value, () => { cursor.value = 0 })

async function loadDynamic() {
  try {
    const [p, s] = await Promise.all([presetsApi.list(), stylesApi.list()])
    presets.value = p.data.presets ?? []
    stylesList.value = (s.data.styles ?? s.data ?? []).map((x: { name?: string } | string) => typeof x === 'string' ? x : x.name ?? '')
      .filter((n: string) => Boolean(n))
  } catch { /* ignore */ }
}

function close() { ui.commandPaletteOpen = false; query.value = '' }

async function activate(item: PaletteItem) {
  try { await item.action() } finally { close() }
}

function onKeydown(e: KeyboardEvent) {
  if (!ui.commandPaletteOpen) {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault()
      ui.commandPaletteOpen = true
      nextTick(() => inputRef.value?.focus())
    }
    return
  }
  if (e.key === 'Escape') { close(); return }
  if (e.key === 'ArrowDown') { e.preventDefault(); cursor.value = Math.min(results.value.length - 1, cursor.value + 1); return }
  if (e.key === 'ArrowUp') { e.preventDefault(); cursor.value = Math.max(0, cursor.value - 1); return }
  if (e.key === 'Enter') { e.preventDefault(); const it = results.value[cursor.value]; if (it) activate(it); return }
}

watch(() => ui.commandPaletteOpen, (open) => {
  if (open) { loadDynamic(); nextTick(() => inputRef.value?.focus()) }
})

onMounted(() => { window.addEventListener('keydown', onKeydown) })
onUnmounted(() => { window.removeEventListener('keydown', onKeydown) })
</script>

<template>
  <Teleport to="body">
    <div v-if="ui.commandPaletteOpen" class="cp-mask" @click.self="close">
      <div class="cp-modal">
        <div class="cp-input-row">
          <span class="cp-icon">⌘K</span>
          <input
            ref="inputRef"
            v-model="query"
            placeholder="搜索模块 / 项目 / 提示词 / 文风…"
            class="cp-input"
          />
          <kbd>Esc</kbd>
        </div>
        <div class="cp-list">
          <div v-if="!results.length" class="cp-empty">未找到结果</div>
          <button
            v-for="(item, idx) in results"
            :key="item.id"
            class="cp-item"
            :class="{ active: idx === cursor }"
            @mouseenter="cursor = idx"
            @click="activate(item)"
            type="button"
          >
            <span class="cp-kind">{{ item.kind }}</span>
            <span class="cp-label">{{ item.label }}</span>
            <span class="cp-hint">{{ item.hint }}</span>
          </button>
        </div>
        <div class="cp-footer">
          <span><kbd>↑↓</kbd> 选择</span>
          <span><kbd>Enter</kbd> 打开</span>
          <span><kbd>Esc</kbd> 关闭</span>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.cp-mask { position: fixed; inset: 0; background: rgba(0,0,0,0.45); backdrop-filter: blur(6px); z-index: 80; display: flex; align-items: flex-start; justify-content: center; padding-top: 12vh; }
.cp-modal { width: min(560px, 92vw); background: var(--color-surface); border-radius: 12px; box-shadow: 0 24px 48px rgba(0,0,0,0.32); display: flex; flex-direction: column; max-height: 70vh; overflow: hidden; }
.cp-input-row { display: flex; align-items: center; gap: 10px; padding: 14px 16px; border-bottom: 1px solid var(--color-control-border); }
.cp-icon { font-size: 11px; font-family: var(--font-mono); color: var(--color-ink-light); background: var(--color-surface-muted); padding: 2px 6px; border-radius: 4px; }
.cp-input { flex: 1; border: 0; outline: 0; background: transparent; font-size: 15px; box-shadow: none !important; }
.cp-input:focus { box-shadow: none !important; }
.cp-list { flex: 1; overflow-y: auto; padding: 6px; }
.cp-empty { padding: 24px; text-align: center; color: var(--color-ink-light); font-size: 13px; }
.cp-item { display: grid; grid-template-columns: 80px 1fr auto; align-items: center; gap: 10px; width: 100%; padding: 8px 12px; border: 0; background: transparent; text-align: left; border-radius: 6px; font-size: 13px; cursor: pointer; }
.cp-item.active { background: var(--color-surface-muted); }
.cp-kind { font-size: 10px; font-weight: 600; letter-spacing: 0.06em; color: var(--color-ink-light); text-transform: uppercase; }
.cp-label { color: var(--color-ink); font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cp-hint { color: var(--color-ink-light); font-size: 11px; }
.cp-footer { padding: 8px 14px; border-top: 1px solid var(--color-control-border); display: flex; gap: 14px; font-size: 11px; color: var(--color-ink-light); }
kbd { font-family: var(--font-mono); font-size: 10px; padding: 1px 5px; border: 1px solid var(--color-control-border); border-radius: 4px; background: var(--color-surface-muted); }
</style>
