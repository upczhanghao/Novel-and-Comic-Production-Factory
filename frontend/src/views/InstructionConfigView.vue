<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { configApi } from '@/api/client'
import { useFeedbackStore } from '@/stores/feedback'
import { confirmDialog } from '@/stores/confirm'

// M23: 只有从 /manju 跳转过来时才显示返回按钮
const cameFromManju = ref(false)

type InstructionTemplate = {
  key: string
  title: string
  description: string
  content: string
  variables: string[]
  customized: boolean
  default_content?: string
}

const feedback = useFeedbackStore()

const templates = ref<Record<string, InstructionTemplate>>({})
const defaults = ref<Record<string, string>>({})
const selectedKey = ref('')
const editorContent = ref('')
const loading = ref(false)
const saving = ref(false)

const search = ref('')
const showOnlyCustom = ref(false)
const showDiff = ref(false)

const orderedTemplates = computed(() => Object.values(templates.value))
const selectedTemplate = computed(() => templates.value[selectedKey.value])
const hasChanges = computed(() => Boolean(selectedTemplate.value && editorContent.value !== selectedTemplate.value.content))

const filtered = computed(() => {
  const kw = search.value.trim().toLowerCase()
  return orderedTemplates.value.filter((t) => {
    if (showOnlyCustom.value && !t.customized) return false
    if (!kw) return true
    return (
      t.key.toLowerCase().includes(kw) ||
      t.title.toLowerCase().includes(kw) ||
      t.description.toLowerCase().includes(kw)
    )
  })
})

async function loadTemplates() {
  loading.value = true
  try {
    const res = await configApi.listManjuInstructions()
    const data = res.data.templates ?? {}
    templates.value = data
    const defs: Record<string, string> = {}
    Object.entries(data).forEach(([k, v]) => {
      const tpl = v as InstructionTemplate
      if (tpl.default_content) defs[k] = tpl.default_content
    })
    defaults.value = defs
    if (!selectedKey.value || !templates.value[selectedKey.value]) {
      selectedKey.value = orderedTemplates.value[0]?.key ?? ''
    }
    editorContent.value = selectedTemplate.value?.content ?? ''
  } catch (e: unknown) {
    feedback.error('加载指令模板失败', (e as Error).message)
  } finally {
    loading.value = false
  }
}

function selectTemplate(key: string) {
  selectedKey.value = key
  editorContent.value = templates.value[key]?.content ?? ''
}

async function saveTemplate() {
  if (!selectedTemplate.value) return
  saving.value = true
  try {
    const res = await configApi.saveManjuInstruction(selectedKey.value, editorContent.value)
    templates.value = res.data.templates ?? templates.value
    editorContent.value = templates.value[selectedKey.value]?.content ?? editorContent.value
    feedback.success(res.data.message ?? '已保存')
  } catch (e: unknown) {
    feedback.error('保存失败', (e as Error).message)
  } finally {
    saving.value = false
  }
}

async function resetTemplate() {
  if (!selectedTemplate.value) return
  if (!(await confirmDialog(`确认将「${selectedTemplate.value.title}」恢复为默认？`))) return
  saving.value = true
  try {
    const res = await configApi.resetManjuInstruction(selectedKey.value)
    templates.value = res.data.templates ?? templates.value
    editorContent.value = res.data.content ?? templates.value[selectedKey.value]?.content ?? ''
    feedback.success(res.data.message ?? '已恢复默认')
  } catch (e: unknown) {
    feedback.error('重置失败', (e as Error).message)
  } finally {
    saving.value = false
  }
}

async function copyContent() {
  try {
    await navigator.clipboard.writeText(editorContent.value)
    feedback.info('已复制指令到剪贴板')
  } catch {
    feedback.warning('无法访问剪贴板')
  }
}

function applyDefaultToEditor() {
  if (!selectedTemplate.value) return
  const def = defaults.value[selectedKey.value]
  if (def != null) {
    editorContent.value = def
    feedback.info('已加载默认内容，需点击「保存模板」才会生效')
  }
}

// 变量分析
const VARIABLE_RE = /\{([a-zA-Z_][\w]*)\}/g
function extractVariables(text: string): string[] {
  const set = new Set<string>()
  let m: RegExpExecArray | null
  while ((m = VARIABLE_RE.exec(text)) !== null) set.add(m[1])
  return Array.from(set).sort()
}

const expectedVariables = computed(() => selectedTemplate.value?.variables ?? [])
const usedVariables = computed(() => extractVariables(editorContent.value))
const missingVariables = computed(() => expectedVariables.value.filter((v) => !usedVariables.value.includes(v)))
const unknownVariables = computed(() => usedVariables.value.filter((v) => !expectedVariables.value.includes(v)))

function highlightedHtml(text: string, expected: string[]): string {
  const ok = new Set(expected)
  const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  return escaped.replace(/\{([a-zA-Z_][\w]*)\}/g, (_, name) => {
    const cls = ok.has(name) ? 'ic-var ok' : 'ic-var unknown'
    return `<span class="${cls}">{${name}}</span>`
  })
}
const previewHtml = computed(() => highlightedHtml(editorContent.value, expectedVariables.value))
const defaultPreviewHtml = computed(() =>
  highlightedHtml(defaults.value[selectedKey.value] ?? '', expectedVariables.value)
)

function insertVariable(name: string) {
  editorContent.value = (editorContent.value || '') + `{${name}}`
}

onMounted(() => {
  // 通过 referrer 简单判断来源；不能保证 100%，仅用于决定是否显示返回按钮
  cameFromManju.value = typeof document !== 'undefined' && /\/manju(\b|$)/.test(document.referrer || '')
  loadTemplates()
})
</script>

<template>
  <div class="module-page space-y-4">
    <div class="module-toolbar">
      <div>
        <h2 class="text-2xl font-bold" style="color: var(--color-ink)">指令配置</h2>
        <div class="module-kicker">Instruction Lab</div>
        <p class="module-subtitle">
          漫剧制作模块发送给 AI 的核心指令模板。支持变量高亮、缺失检查与一键恢复默认。
        </p>
      </div>
      <router-link v-if="cameFromManju" to="/manju" class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm hover:bg-white transition-colors">
        返回漫剧制作
      </router-link>
    </div>

    <section class="ic-grid">
      <!-- 左：库 -->
      <aside class="module-panel ic-library">
        <div class="ic-lib-head">
          <input v-model="search" placeholder="搜索模板…" class="ic-input" />
          <label class="ic-toggle">
            <input type="checkbox" v-model="showOnlyCustom" />
            仅自定义
          </label>
          <button @click="loadTemplates" :disabled="loading" type="button" class="ic-btn-mini">
            {{ loading ? '加载中' : '刷新' }}
          </button>
        </div>
        <div class="ic-lib-list">
          <button
            v-for="item in filtered"
            :key="item.key"
            @click="selectTemplate(item.key)"
            class="ic-item"
            :class="{ active: selectedKey === item.key }"
            type="button"
          >
            <div class="ic-item-top">
              <span class="ic-item-title">{{ item.title }}</span>
              <span v-if="item.customized" class="ic-badge custom">已自定义</span>
            </div>
            <div class="ic-item-desc">{{ item.description }}</div>
            <div class="ic-item-vars">
              <code v-for="v in item.variables" :key="v" class="ic-var-mini">{{ '{' + v + '}' }}</code>
            </div>
          </button>
          <div v-if="!filtered.length" class="ic-empty">没有匹配的模板</div>
        </div>
      </aside>

      <!-- 中：预览 / 编辑 -->
      <main class="module-panel ic-editor-pane">
        <div class="ic-editor-head" v-if="selectedTemplate">
          <div class="flex-1 min-w-0">
            <h3 class="module-panel-title">
              {{ selectedTemplate.title }}
              <span v-if="selectedTemplate.customized" class="ic-badge custom inline-flex">已自定义</span>
            </h3>
            <p class="ic-meta">
              <code class="ic-key">{{ selectedTemplate.key }}</code>
              · {{ selectedTemplate.description }}
            </p>
          </div>
          <label class="ic-toggle">
            <input type="checkbox" v-model="showDiff" :disabled="!defaults[selectedKey]" />
            对比默认
          </label>
        </div>

        <div v-if="selectedTemplate" class="ic-editor-body">
          <div v-if="!showDiff">
            <textarea
              v-model="editorContent"
              spellcheck="false"
              class="ic-editor"
            />
            <details class="ic-preview-details">
              <summary>预览（变量高亮）</summary>
              <pre class="ic-preview-box" v-html="previewHtml" />
            </details>
          </div>
          <div v-else class="ic-diff">
            <div class="ic-diff-col">
              <div class="ic-diff-label">默认</div>
              <pre class="ic-preview-box" v-html="defaultPreviewHtml" />
            </div>
            <div class="ic-diff-col">
              <div class="ic-diff-label">当前编辑中</div>
              <pre class="ic-preview-box" v-html="previewHtml" />
            </div>
          </div>

          <div v-if="missingVariables.length || unknownVariables.length" class="ic-warn">
            <div v-if="missingVariables.length">
              ⚠ 缺失变量（模板预期但当前未使用）：
              <code v-for="v in missingVariables" :key="`m-${v}`" class="ic-var-inline missing" @click="insertVariable(v)" title="点击插入到末尾">
                {{ '{' + v + '}' }}
              </code>
            </div>
            <div v-if="unknownVariables.length">
              ⚐ 未识别的变量（运行时不会被替换）：
              <code v-for="v in unknownVariables" :key="`u-${v}`" class="ic-var-inline unknown">{{ '{' + v + '}' }}</code>
            </div>
          </div>
        </div>

        <div v-else class="ic-empty ic-empty-large">在左侧选择一个模板</div>
      </main>

      <!-- 右：应用 -->
      <aside class="module-panel ic-apply" v-if="selectedTemplate">
        <h3 class="module-panel-title">应用</h3>
        <p class="module-panel-caption">所有修改保存后立即对漫剧流水线生效。</p>

        <div class="ic-apply-actions">
          <button @click="saveTemplate" :disabled="saving || !hasChanges" type="button" class="ic-btn-primary">
            {{ saving ? '保存中…' : (hasChanges ? '保存模板' : '无修改') }}
          </button>
          <button @click="applyDefaultToEditor" :disabled="!defaults[selectedKey]" type="button" class="ic-btn">载入默认</button>
          <button @click="copyContent" type="button" class="ic-btn">复制指令</button>
          <button @click="resetTemplate" :disabled="saving || !selectedTemplate.customized" type="button" class="ic-btn-danger">
            恢复默认
          </button>
        </div>

        <div class="ic-vars-section">
          <div class="ic-vars-title">预期变量</div>
          <div class="ic-vars-list">
            <code
              v-for="v in expectedVariables"
              :key="v"
              class="ic-var-inline"
              :class="{ missing: missingVariables.includes(v) }"
              @click="insertVariable(v)"
              :title="missingVariables.includes(v) ? '缺失 - 点击插入' : '已使用 - 点击追加'"
            >
              {{ '{' + v + '}' }}
            </code>
            <span v-if="!expectedVariables.length" class="text-[11px] text-[var(--color-ink-light)]">此模板无预期变量</span>
          </div>
        </div>

        <div class="ic-vars-section">
          <div class="ic-vars-title">变量统计</div>
          <div class="ic-vars-stat">
            <span>已使用</span>
            <strong>{{ usedVariables.length }}</strong>
          </div>
          <div class="ic-vars-stat" :class="{ warn: missingVariables.length }">
            <span>缺失</span>
            <strong>{{ missingVariables.length }}</strong>
          </div>
          <div class="ic-vars-stat" :class="{ warn: unknownVariables.length }">
            <span>未识别</span>
            <strong>{{ unknownVariables.length }}</strong>
          </div>
        </div>
      </aside>
    </section>
  </div>
</template>

<style scoped>
.ic-grid { display: grid; grid-template-columns: 280px 1fr 240px; gap: 12px; align-items: stretch; }
@media (max-width: 1280px) { .ic-grid { grid-template-columns: 240px 1fr; } .ic-apply { grid-column: 1 / -1; } }
@media (max-width: 800px) { .ic-grid { grid-template-columns: 1fr; } }

.ic-input { padding: 5px 10px; font-size: 12px; border: 1px solid var(--color-parchment-darker); border-radius: 6px; background: white; flex: 1; min-width: 0; }
.ic-toggle { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: var(--color-ink-light); cursor: pointer; }
.ic-btn-primary { padding: 6px 12px; font-size: 12px; font-weight: 600; border-radius: 6px;
  background: var(--color-leather); color: var(--color-parchment); border: none; cursor: pointer; }
.ic-btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.ic-btn { padding: 6px 12px; font-size: 12px; border-radius: 6px;
  background: white; color: var(--color-ink); border: 1px solid var(--color-parchment-darker); cursor: pointer; }
.ic-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.ic-btn-danger { padding: 6px 12px; font-size: 12px; border-radius: 6px;
  background: white; color: #b91c1c; border: 1px solid #fecaca; cursor: pointer; }
.ic-btn-danger:disabled { opacity: 0.4; cursor: not-allowed; }
.ic-btn-mini { padding: 4px 8px; font-size: 11px; border-radius: 4px;
  background: white; color: var(--color-ink); border: 1px solid var(--color-parchment-darker); cursor: pointer; }

/* 左 */
.ic-library { display: flex; flex-direction: column; padding: 0; max-height: 720px; }
.ic-lib-head { padding: 10px; display: flex; gap: 6px; align-items: center; flex-wrap: wrap; border-bottom: 1px solid var(--color-parchment-darker); }
.ic-lib-list { overflow-y: auto; padding: 6px; flex: 1; }
.ic-item { display: block; width: 100%; text-align: left; padding: 8px 10px; margin-bottom: 4px;
  background: white; border: 1px solid var(--color-parchment-darker); border-radius: 6px; cursor: pointer; }
.ic-item:hover { background: var(--color-surface-muted); }
.ic-item.active { border-color: var(--color-leather); background: #fffaf2; }
.ic-item-top { display: flex; align-items: center; justify-content: space-between; gap: 6px; }
.ic-item-title { font-size: 12px; font-weight: 600; color: var(--color-ink); }
.ic-badge { font-size: 9px; padding: 1px 6px; border-radius: 999px; line-height: 1.3; }
.ic-badge.custom { background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; }
.ic-item-desc { font-size: 10px; color: var(--color-ink-light); margin-top: 2px; line-height: 1.4; }
.ic-item-vars { display: flex; flex-wrap: wrap; gap: 3px; margin-top: 4px; }
.ic-var-mini { font-size: 9px; padding: 1px 5px; border-radius: 3px; background: var(--color-surface-muted); color: var(--color-ink-light); font-family: ui-monospace, monospace; }

.ic-empty { padding: 18px; text-align: center; font-size: 12px; color: var(--color-ink-light); }
.ic-empty-large { padding: 60px 20px; }

/* 中 */
.ic-editor-pane { display: flex; flex-direction: column; padding: 14px; gap: 10px; }
.ic-editor-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
.ic-meta { font-size: 11px; color: var(--color-ink-light); margin-top: 2px; }
.ic-key { padding: 1px 6px; background: var(--color-surface-muted); border-radius: 4px; font-size: 10px; margin-right: 4px; }
.ic-editor-body { flex: 1; display: flex; flex-direction: column; gap: 8px; min-height: 0; }
.ic-editor { width: 100%; min-height: 440px; padding: 10px 12px; font-size: 12px;
  border: 1px solid var(--color-parchment-darker); border-radius: 6px; font-family: ui-monospace, monospace;
  line-height: 1.55; resize: vertical; background: #fffefb; }
.ic-preview-details summary { font-size: 11px; color: var(--color-ink-light); cursor: pointer; padding: 4px 0; }
.ic-preview-box { padding: 10px; background: var(--color-surface-muted); border-radius: 6px;
  font-family: ui-monospace, monospace; font-size: 11px; line-height: 1.55; white-space: pre-wrap;
  max-height: 400px; overflow-y: auto; word-break: break-word; }
:deep(.ic-var) { padding: 0 3px; border-radius: 3px; font-weight: 600; }
:deep(.ic-var.ok) { background: #fde68a; color: #78350f; }
:deep(.ic-var.unknown) { background: #fecaca; color: #991b1b; }

.ic-diff { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.ic-diff-col { display: flex; flex-direction: column; gap: 4px; }
.ic-diff-label { font-size: 11px; font-weight: 600; color: var(--color-ink-light); }

.ic-warn { padding: 8px 10px; background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px;
  font-size: 11px; color: #78350f; display: flex; flex-direction: column; gap: 4px; }
.ic-var-inline { padding: 1px 5px; border-radius: 3px; font-family: ui-monospace, monospace; font-size: 10px;
  background: var(--color-surface-muted); color: var(--color-ink); margin: 0 2px; display: inline-block; cursor: pointer; }
.ic-var-inline.missing { background: #fee2e2; color: #991b1b; }
.ic-var-inline.unknown { background: #fee2e2; color: #991b1b; }

/* 右 */
.ic-apply { display: flex; flex-direction: column; padding: 14px; gap: 10px; }
.ic-apply-actions { display: flex; flex-direction: column; gap: 6px; }
.ic-apply-actions button { width: 100%; padding: 7px 12px; font-size: 12px; }
.ic-vars-section { padding: 8px 10px; background: var(--color-surface-muted); border-radius: 6px; }
.ic-vars-title { font-size: 11px; font-weight: 600; color: var(--color-ink-light); margin-bottom: 4px; }
.ic-vars-list { display: flex; flex-wrap: wrap; gap: 3px; }
.ic-vars-stat { display: flex; justify-content: space-between; font-size: 11px; padding: 2px 0; }
.ic-vars-stat.warn strong { color: #b91c1c; }
.ic-vars-stat strong { color: var(--color-ink); }
</style>
