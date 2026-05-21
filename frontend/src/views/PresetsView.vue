<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { presetsApi } from '@/api/client'
import { useFeedbackStore } from '@/stores/feedback'
import { confirmDialog } from '@/stores/confirm'

interface PromptMeta { category: string; tags: string[]; description: string }
interface CategoryInfo { label: string; description: string; order: number }
interface PromptData {
  prompts: Record<string, string>
  defaults: Record<string, string>
  keys: string[]
  display_names: Record<string, string>
  meta: Record<string, PromptMeta>
  categories: Record<string, CategoryInfo>
}

const feedback = useFeedbackStore()

const presets = ref<string[]>([])
const activePreset = ref('')
const activeDesc = ref('')

const promptData = ref<PromptData>({ prompts: {}, defaults: {}, keys: [], display_names: {}, meta: {}, categories: {} })
const selectedKey = ref('')
const promptContent = ref('')

const newPresetName = ref('')
const newPresetDesc = ref('')

const search = ref('')
const categoryFilter = ref('all')
const tagFilter = ref<string>('')
const showDiff = ref(false)
const showOnlyCustom = ref(false)

async function loadAll() {
  const res = await presetsApi.list()
  presets.value = res.data.presets
  activePreset.value = res.data.active_preset
  activeDesc.value = res.data.active_description
  const pd = await presetsApi.getPrompts()
  promptData.value = pd.data as PromptData
  if (!selectedKey.value && promptData.value.keys.length) {
    selectedKey.value = promptData.value.keys[0]
  }
  loadPrompt(selectedKey.value)
}

async function activate(name: string) {
  try {
    const res = await presetsApi.activate(name)
    activePreset.value = res.data.active_preset
    activeDesc.value = res.data.description
    feedback.success(res.data.message ?? `已激活方案「${name}」`)
    await loadAll()
  } catch (e: unknown) {
    feedback.error('方案切换失败', (e as Error).message)
  }
}

function loadPrompt(key: string) {
  promptContent.value = promptData.value.prompts[key] ?? ''
}

watch(selectedKey, loadPrompt)

const orderedCategories = computed(() => {
  const entries = Object.entries(promptData.value.categories || {})
  entries.sort((a, b) => (a[1].order ?? 99) - (b[1].order ?? 99))
  return entries
})

const allTags = computed(() => {
  const set = new Set<string>()
  Object.values(promptData.value.meta || {}).forEach((m) => (m.tags || []).forEach((t) => set.add(t)))
  return Array.from(set).sort()
})

interface PromptRow {
  key: string
  title: string
  category: string
  categoryLabel: string
  tags: string[]
  description: string
  customized: boolean
}

const allRows = computed<PromptRow[]>(() => {
  const meta = promptData.value.meta || {}
  const cats = promptData.value.categories || {}
  return promptData.value.keys.map((key) => {
    const m = meta[key] || { category: 'misc', tags: [], description: '' }
    const cur = promptData.value.prompts[key] ?? ''
    const def = promptData.value.defaults[key] ?? ''
    return {
      key,
      title: promptData.value.display_names[key] ?? key,
      category: m.category,
      categoryLabel: cats[m.category]?.label ?? '其他',
      tags: m.tags || [],
      description: m.description || '',
      customized: cur !== def && def !== '',
    }
  })
})

const filteredRows = computed(() => {
  const kw = search.value.trim().toLowerCase()
  return allRows.value.filter((r) => {
    if (categoryFilter.value !== 'all' && r.category !== categoryFilter.value) return false
    if (tagFilter.value && !r.tags.includes(tagFilter.value)) return false
    if (showOnlyCustom.value && !r.customized) return false
    if (!kw) return true
    return (
      r.key.toLowerCase().includes(kw) ||
      r.title.toLowerCase().includes(kw) ||
      r.description.toLowerCase().includes(kw) ||
      r.tags.some((t) => t.toLowerCase().includes(kw))
    )
  })
})

const groupedRows = computed(() => {
  const groups: Record<string, PromptRow[]> = {}
  for (const r of filteredRows.value) {
    if (!groups[r.category]) groups[r.category] = []
    groups[r.category].push(r)
  }
  return orderedCategories.value
    .filter(([cat]) => groups[cat]?.length)
    .map(([cat, info]) => ({ cat, info, items: groups[cat] }))
})

const selectedRow = computed(() => allRows.value.find((r) => r.key === selectedKey.value) ?? null)
const selectedDefault = computed(() => promptData.value.defaults[selectedKey.value] ?? '')
const hasChanges = computed(() => promptContent.value !== (promptData.value.prompts[selectedKey.value] ?? ''))
const isCustomized = computed(() => selectedRow.value?.customized ?? false)

const VARIABLE_RE = /\{([a-zA-Z_][\w]*)\}/g
function extractVariables(text: string): string[] {
  const set = new Set<string>()
  let m: RegExpExecArray | null
  while ((m = VARIABLE_RE.exec(text)) !== null) set.add(m[1])
  return Array.from(set).sort()
}
const editorVariables = computed(() => extractVariables(promptContent.value))
const defaultVariables = computed(() => extractVariables(selectedDefault.value))
const missingVariables = computed(() => defaultVariables.value.filter((v) => !editorVariables.value.includes(v)))
const extraVariables = computed(() => editorVariables.value.filter((v) => !defaultVariables.value.includes(v)))

function highlightedHtml(text: string): string {
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  return escaped.replace(/\{([a-zA-Z_][\w]*)\}/g, '<span class="pv-var">{$1}</span>')
}
const previewHtml = computed(() => highlightedHtml(promptContent.value))
const defaultHtml = computed(() => highlightedHtml(selectedDefault.value))

async function savePrompt() {
  if (!selectedKey.value) return
  try {
    const res = await presetsApi.updatePrompt(selectedKey.value, promptContent.value)
    feedback.success(res.data.message ?? '已保存')
    await loadAll()
  } catch (e: unknown) {
    feedback.error('保存失败', (e as Error).message)
  }
}

async function resetPrompt() {
  if (!selectedKey.value) return
  if (!(await confirmDialog(`确认重置「${selectedRow.value?.title || selectedKey.value}」为默认内容？此操作不可撤销。`))) return
  try {
    const res = await presetsApi.resetPrompt(selectedKey.value)
    promptContent.value = res.data.content
    feedback.success(res.data.message ?? '已恢复默认')
    await loadAll()
  } catch (e: unknown) {
    feedback.error('重置失败', (e as Error).message)
  }
}

async function copyPrompt() {
  try {
    await navigator.clipboard.writeText(promptContent.value)
    feedback.info('已复制提示词到剪贴板')
  } catch {
    feedback.warning('无法访问剪贴板')
  }
}

function applyDefaultToEditor() {
  promptContent.value = selectedDefault.value
  feedback.info('已加载默认内容到编辑器，需点击「保存到当前方案」才会生效')
}

async function saveAsNew() {
  if (!newPresetName.value.trim()) return
  try {
    const res = await presetsApi.save(newPresetName.value.trim(), newPresetDesc.value)
    feedback.success(res.data.message ?? `已另存为「${newPresetName.value.trim()}」`)
    newPresetName.value = ''
    newPresetDesc.value = ''
    await loadAll()
  } catch (e: unknown) {
    feedback.error('另存失败', (e as Error).message)
  }
}

async function deletePreset(name: string) {
  if (!(await confirmDialog(`确认删除方案「${name}」？此操作不可撤销。`))) return
  try {
    const res = await presetsApi.delete(name)
    feedback.success(res.data.message ?? '已删除')
    await loadAll()
  } catch (e: unknown) {
    feedback.error('删除失败', (e as Error).message)
  }
}

onMounted(loadAll)
</script>

<template>
  <div class="module-page space-y-4">
    <div class="module-toolbar">
      <div>
        <h2 class="text-2xl font-bold" style="color: var(--color-ink)">提示词方案</h2>
        <div class="module-kicker">Prompt Library</div>
        <div class="module-subtitle">
          当前方案：<strong>{{ activePreset || '—' }}</strong>
          <span v-if="activeDesc"> · {{ activeDesc }}</span>
        </div>
      </div>
    </div>

    <!-- 方案切换条 -->
    <section class="module-panel p-3">
      <div class="pv-presets">
        <div class="pv-presets-label">方案库</div>
        <div class="pv-preset-chips">
          <div v-for="p in presets" :key="p" class="pv-preset-chip" :class="{ active: p === activePreset }">
            <button @click="activate(p)" type="button" class="pv-preset-name">{{ p }}</button>
            <button
              v-if="p !== activePreset"
              @click="deletePreset(p)"
              type="button"
              class="pv-preset-x"
              title="删除方案"
            >✕</button>
            <span v-else class="pv-preset-active-dot" title="当前激活">●</span>
          </div>
        </div>
        <div class="pv-presets-form">
          <input v-model="newPresetName" placeholder="新方案名称" class="pv-input" />
          <input v-model="newPresetDesc" placeholder="描述（可选）" class="pv-input" />
          <button @click="saveAsNew" :disabled="!newPresetName.trim()" type="button" class="pv-btn-primary">
            基于当前另存为
          </button>
        </div>
      </div>
    </section>

    <!-- 库 + 预览 + 应用 三段式 -->
    <section class="pv-grid">
      <!-- 左：库（搜索 + 分类） -->
      <aside class="module-panel pv-library">
        <div class="pv-lib-head">
          <input v-model="search" placeholder="搜索 prompt 名称、key、标签…" class="pv-input pv-search" />
          <div class="pv-lib-filters">
            <select v-model="categoryFilter" class="pv-input">
              <option value="all">全部分类</option>
              <option v-for="[cat, info] in orderedCategories" :key="cat" :value="cat">
                {{ info.label }}
              </option>
            </select>
            <select v-model="tagFilter" class="pv-input">
              <option value="">全部标签</option>
              <option v-for="t in allTags" :key="t" :value="t">{{ t }}</option>
            </select>
          </div>
          <label class="pv-lib-toggle">
            <input type="checkbox" v-model="showOnlyCustom" />
            仅显示已自定义
          </label>
          <div class="pv-lib-count">共 {{ filteredRows.length }} / {{ allRows.length }} 条</div>
        </div>

        <div class="pv-lib-list">
          <div v-for="group in groupedRows" :key="group.cat" class="pv-group">
            <div class="pv-group-head">
              <span class="pv-group-label">{{ group.info.label }}</span>
              <span class="pv-group-count">{{ group.items.length }}</span>
            </div>
            <div class="pv-group-desc">{{ group.info.description }}</div>
            <button
              v-for="r in group.items"
              :key="r.key"
              type="button"
              class="pv-item"
              :class="{ active: r.key === selectedKey }"
              @click="selectedKey = r.key"
            >
              <div class="pv-item-top">
                <span class="pv-item-title">{{ r.title }}</span>
                <span v-if="r.customized" class="pv-item-badge custom">已自定义</span>
              </div>
              <div class="pv-item-desc">{{ r.description || r.key }}</div>
              <div class="pv-item-tags">
                <span v-for="t in r.tags" :key="t" class="pv-tag">{{ t }}</span>
              </div>
            </button>
          </div>
          <div v-if="!filteredRows.length" class="pv-empty">没有符合条件的提示词</div>
        </div>
      </aside>

      <!-- 中：预览（含变量高亮、与默认对比） -->
      <main class="module-panel pv-preview">
        <div class="pv-preview-head">
          <div>
            <h3 class="module-panel-title">
              {{ selectedRow?.title || '请选择提示词' }}
              <span v-if="isCustomized" class="pv-item-badge custom inline-flex">已自定义</span>
            </h3>
            <p v-if="selectedRow" class="pv-preview-meta">
              <code class="pv-key">{{ selectedRow.key }}</code>
              · {{ selectedRow.categoryLabel }}
              <span v-if="selectedRow.tags.length"> · </span>
              <span v-for="t in selectedRow.tags" :key="t" class="pv-tag-mini">{{ t }}</span>
            </p>
            <p v-if="selectedRow?.description" class="pv-preview-desc">{{ selectedRow.description }}</p>
          </div>
          <label class="pv-toggle">
            <input type="checkbox" v-model="showDiff" />
            对比默认
          </label>
        </div>

        <div v-if="selectedRow" class="pv-editor-wrap">
          <div v-if="!showDiff">
            <textarea
              v-model="promptContent"
              rows="20"
              class="pv-editor"
              placeholder="编辑提示词…"
              spellcheck="false"
            />
            <details class="pv-preview-details">
              <summary>预览（变量高亮）</summary>
              <pre class="pv-preview-box" v-html="previewHtml" />
            </details>
          </div>
          <div v-else class="pv-diff">
            <div class="pv-diff-col">
              <div class="pv-diff-label">默认内容</div>
              <pre class="pv-preview-box" v-html="defaultHtml" />
            </div>
            <div class="pv-diff-col">
              <div class="pv-diff-label">当前内容（{{ activePreset }}）</div>
              <pre class="pv-preview-box" v-html="previewHtml" />
            </div>
          </div>

          <div v-if="missingVariables.length || extraVariables.length" class="pv-warn">
            <div v-if="missingVariables.length">
              ⚠ 默认含有但当前缺失的变量：
              <code v-for="v in missingVariables" :key="`m-${v}`" class="pv-var-inline missing">{{ '{' + v + '}' }}</code>
            </div>
            <div v-if="extraVariables.length">
              ⚐ 当前新增的变量（运行时若未提供值会保留原样）：
              <code v-for="v in extraVariables" :key="`e-${v}`" class="pv-var-inline extra">{{ '{' + v + '}' }}</code>
            </div>
          </div>
        </div>
        <div v-else class="pv-empty pv-empty-large">
          在左侧库中选择一个提示词
        </div>
      </main>

      <!-- 右：应用面板 -->
      <aside class="module-panel pv-apply">
        <h3 class="module-panel-title">应用</h3>
        <p class="module-panel-caption">编辑会保存到当前方案「{{ activePreset || '—' }}」。可另存为新方案保留原版。</p>

        <div class="pv-apply-actions" v-if="selectedRow">
          <button @click="savePrompt" :disabled="!hasChanges" type="button" class="pv-btn-primary">
            {{ hasChanges ? '保存到当前方案' : '无修改' }}
          </button>
          <button @click="applyDefaultToEditor" type="button" class="pv-btn">载入默认内容</button>
          <button @click="copyPrompt" type="button" class="pv-btn">复制提示词</button>
          <button @click="resetPrompt" :disabled="!isCustomized" type="button" class="pv-btn-danger">
            重置为默认
          </button>
        </div>

        <div v-if="selectedRow" class="pv-vars-summary">
          <div class="pv-vars-title">变量统计</div>
          <div class="pv-vars-stat">
            <span>当前</span>
            <strong>{{ editorVariables.length }}</strong>
          </div>
          <div class="pv-vars-stat">
            <span>默认</span>
            <strong>{{ defaultVariables.length }}</strong>
          </div>
          <div class="pv-vars-list">
            <code v-for="v in editorVariables" :key="`u-${v}`" class="pv-var-inline">{{ '{' + v + '}' }}</code>
            <span v-if="!editorVariables.length" class="text-[11px] text-[var(--color-ink-light)]">（暂无变量）</span>
          </div>
        </div>
      </aside>
    </section>
  </div>
</template>

<style scoped>
.pv-presets { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.pv-presets-label { font-size: 12px; font-weight: 600; color: var(--color-ink-light); }
.pv-preset-chips { display: flex; flex-wrap: wrap; gap: 6px; flex: 1; }
.pv-preset-chip { display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px; border-radius: 999px;
  background: white; border: 1px solid var(--color-parchment-darker); font-size: 12px; }
.pv-preset-chip.active { background: var(--color-leather); color: var(--color-parchment); border-color: var(--color-leather); }
.pv-preset-name { background: none; border: none; padding: 0; cursor: pointer; color: inherit; font-size: inherit; }
.pv-preset-x { background: none; border: none; padding: 0 0 0 4px; cursor: pointer; color: #b91c1c; font-size: 11px; }
.pv-preset-active-dot { color: var(--color-parchment); font-size: 9px; padding-left: 2px; }
.pv-presets-form { display: flex; gap: 6px; align-items: center; }

.pv-input { padding: 5px 10px; font-size: 12px; border: 1px solid var(--color-parchment-darker); border-radius: 6px; background: white; }
.pv-search { flex: 1; min-width: 0; }

.pv-btn-primary { padding: 5px 12px; font-size: 12px; font-weight: 600; border-radius: 6px;
  background: var(--color-leather); color: var(--color-parchment); border: none; cursor: pointer; }
.pv-btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.pv-btn { padding: 5px 12px; font-size: 12px; border-radius: 6px;
  background: white; color: var(--color-ink); border: 1px solid var(--color-parchment-darker); cursor: pointer; }
.pv-btn-danger { padding: 5px 12px; font-size: 12px; border-radius: 6px;
  background: white; color: #b91c1c; border: 1px solid #fecaca; cursor: pointer; }
.pv-btn-danger:disabled { opacity: 0.4; cursor: not-allowed; }

.pv-grid { display: grid; grid-template-columns: 320px 1fr 280px; gap: 12px; align-items: stretch; }
@media (max-width: 1280px) { .pv-grid { grid-template-columns: 280px 1fr; } .pv-apply { grid-column: 1 / -1; } }
@media (max-width: 800px) { .pv-grid { grid-template-columns: 1fr; } }

/* 左侧库 */
.pv-library { display: flex; flex-direction: column; padding: 0; max-height: 720px; }
.pv-lib-head { padding: 10px; display: flex; flex-direction: column; gap: 6px; border-bottom: 1px solid var(--color-parchment-darker); }
.pv-lib-filters { display: flex; gap: 6px; }
.pv-lib-filters .pv-input { flex: 1; min-width: 0; }
.pv-lib-toggle { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: var(--color-ink-light); cursor: pointer; }
.pv-lib-count { font-size: 11px; color: var(--color-ink-light); }
.pv-lib-list { overflow-y: auto; flex: 1; padding: 6px; }

.pv-group { margin-bottom: 8px; }
.pv-group-head { display: flex; align-items: baseline; gap: 6px; padding: 6px 8px 2px; }
.pv-group-label { font-size: 11px; font-weight: 700; color: var(--color-leather); text-transform: uppercase; letter-spacing: 0.05em; }
.pv-group-count { font-size: 10px; padding: 0 5px; border-radius: 999px; background: var(--color-surface-muted); color: var(--color-ink-light); }
.pv-group-desc { font-size: 10px; color: var(--color-ink-light); padding: 0 8px 4px; }

.pv-item { display: block; width: 100%; text-align: left; padding: 8px 10px; margin-bottom: 4px;
  background: white; border: 1px solid var(--color-parchment-darker); border-radius: 6px; cursor: pointer;
  transition: border-color 0.1s, background 0.1s; }
.pv-item:hover { background: var(--color-surface-muted); }
.pv-item.active { border-color: var(--color-leather); background: #fffaf2; }
.pv-item-top { display: flex; align-items: center; justify-content: space-between; gap: 6px; }
.pv-item-title { font-size: 12px; font-weight: 600; color: var(--color-ink); }
.pv-item-badge { font-size: 9px; padding: 1px 6px; border-radius: 999px; line-height: 1.3; }
.pv-item-badge.custom { background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; }
.pv-item-desc { font-size: 10px; color: var(--color-ink-light); margin-top: 2px; line-height: 1.4; }
.pv-item-tags { display: flex; flex-wrap: wrap; gap: 3px; margin-top: 4px; }
.pv-tag { font-size: 9px; padding: 1px 6px; border-radius: 999px; background: var(--color-surface-muted); color: var(--color-ink-light); }

.pv-empty { padding: 18px; text-align: center; font-size: 12px; color: var(--color-ink-light); }
.pv-empty-large { padding: 60px 20px; }

/* 中间预览 */
.pv-preview { display: flex; flex-direction: column; padding: 14px; gap: 8px; }
.pv-preview-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
.pv-preview-meta { font-size: 11px; color: var(--color-ink-light); display: flex; align-items: center; flex-wrap: wrap; gap: 4px; margin-top: 2px; }
.pv-key { padding: 1px 6px; background: var(--color-surface-muted); border-radius: 4px; font-size: 10px; }
.pv-tag-mini { font-size: 10px; padding: 0 5px; background: var(--color-surface-muted); border-radius: 999px; color: var(--color-ink-light); }
.pv-preview-desc { font-size: 11px; color: var(--color-ink-light); margin-top: 4px; }
.pv-toggle { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: var(--color-ink-light); cursor: pointer; white-space: nowrap; }

.pv-editor-wrap { flex: 1; display: flex; flex-direction: column; gap: 8px; min-height: 0; }
.pv-editor { width: 100%; min-height: 360px; padding: 10px 12px; font-size: 12px;
  border: 1px solid var(--color-parchment-darker); border-radius: 6px; font-family: ui-monospace, monospace;
  line-height: 1.55; resize: vertical; background: #fffefb; }
.pv-preview-details summary { font-size: 11px; color: var(--color-ink-light); cursor: pointer; padding: 4px 0; }
.pv-preview-box { padding: 10px; background: var(--color-surface-muted); border-radius: 6px;
  font-family: ui-monospace, monospace; font-size: 11px; line-height: 1.55; white-space: pre-wrap;
  max-height: 360px; overflow-y: auto; word-break: break-word; }
:deep(.pv-var) { background: #fde68a; color: #78350f; padding: 0 3px; border-radius: 3px; font-weight: 600; }

.pv-diff { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.pv-diff-col { display: flex; flex-direction: column; gap: 4px; }
.pv-diff-label { font-size: 11px; font-weight: 600; color: var(--color-ink-light); }

.pv-warn { padding: 8px 10px; background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px;
  font-size: 11px; color: #78350f; display: flex; flex-direction: column; gap: 4px; }
.pv-var-inline { padding: 1px 5px; border-radius: 3px; font-family: ui-monospace, monospace; font-size: 10px;
  background: var(--color-surface-muted); color: var(--color-ink); margin: 0 2px; display: inline-block; }
.pv-var-inline.missing { background: #fee2e2; color: #991b1b; }
.pv-var-inline.extra { background: #dbeafe; color: #1e40af; }

/* 右侧应用 */
.pv-apply { display: flex; flex-direction: column; padding: 14px; gap: 10px; }
.pv-apply-actions { display: flex; flex-direction: column; gap: 6px; }
.pv-apply-actions button { width: 100%; padding: 7px 12px; font-size: 12px; }

.pv-vars-summary { padding: 8px 10px; background: var(--color-surface-muted); border-radius: 6px; }
.pv-vars-title { font-size: 11px; font-weight: 600; color: var(--color-ink-light); margin-bottom: 4px; }
.pv-vars-stat { display: flex; justify-content: space-between; font-size: 11px; padding: 2px 0; }
.pv-vars-stat strong { color: var(--color-ink); }
.pv-vars-list { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 3px; }
</style>
