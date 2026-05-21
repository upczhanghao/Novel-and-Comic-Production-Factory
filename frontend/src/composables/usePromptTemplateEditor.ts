import { computed, ref, watch, type Ref } from 'vue'
import { useFeedbackStore } from '@/stores/feedback'
import { confirmDialog } from '@/stores/confirm'

// A8: 共享 PresetsView 与 InstructionConfigView 的 prompt 模板编辑逻辑。
// - 变量分析（提取 / 缺失 / 多余）
// - HTML 高亮（变量用 <span class="<prefix>-var [ok|unknown]">…</span>）
// - 编辑器状态（selectedKey / editorContent / hasChanges）
// - save / reset / copy / applyDefault 通过 adapter 调用各自 API

const VARIABLE_RE = /\{([a-zA-Z_][\w]*)\}/g

export function extractVariables(text: string): string[] {
  const set = new Set<string>()
  let m: RegExpExecArray | null
  const re = new RegExp(VARIABLE_RE.source, 'g')
  while ((m = re.exec(text)) !== null) set.add(m[1])
  return Array.from(set).sort()
}

const ESC_RE = /[&<>]/g
const ESC_MAP: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;' }

export function highlightVariables(
  text: string,
  options: { classPrefix?: string; expected?: string[] } = {},
): string {
  const prefix = options.classPrefix ?? 'pv'
  const expected = options.expected
  const ok = expected ? new Set(expected) : null
  const escaped = text.replace(ESC_RE, (c) => ESC_MAP[c])
  return escaped.replace(/\{([a-zA-Z_][\w]*)\}/g, (_, name) => {
    if (!ok) return `<span class="${prefix}-var">{${name}}</span>`
    const cls = ok.has(name) ? `${prefix}-var ok` : `${prefix}-var unknown`
    return `<span class="${cls}">{${name}}</span>`
  })
}

export interface PromptTemplateAdapter {
  save: (key: string, content: string) => Promise<{ message?: string; content?: string }>
  reset: (key: string) => Promise<{ message?: string; content?: string }>
}

export interface PromptTemplateEditorOptions {
  /** Returns the saved content for the currently selected key. Used to compute hasChanges and reset baseline on selection change. */
  savedContent: () => string
  /** Default content for the currently selected key (used by applyDefault). */
  defaultContent: () => string
  /** Optional: expected variable list — when provided, highlight distinguishes ok / unknown. */
  expectedVariables?: () => string[]
  /** CSS class prefix for highlighted variables (e.g. 'pv', 'ic'). Defaults to 'pv'. */
  classPrefix?: string
  adapter: Ref<PromptTemplateAdapter | null>
}

export function usePromptTemplateEditor(opts: PromptTemplateEditorOptions) {
  const feedback = useFeedbackStore()

  const selectedKey = ref('')
  const editorContent = ref('')
  const saving = ref(false)

  const savedContent = computed(() => opts.savedContent())
  const defaultContent = computed(() => opts.defaultContent())
  const expectedVariables = computed(() => opts.expectedVariables?.() ?? [])

  const hasChanges = computed(() => editorContent.value !== savedContent.value)

  const usedVariables = computed(() => extractVariables(editorContent.value))
  const defaultVariables = computed(() => extractVariables(defaultContent.value))
  const missingVariables = computed(() => {
    const exp = expectedVariables.value.length ? expectedVariables.value : defaultVariables.value
    return exp.filter((v) => !usedVariables.value.includes(v))
  })
  const extraVariables = computed(() => {
    const exp = expectedVariables.value.length ? expectedVariables.value : defaultVariables.value
    return usedVariables.value.filter((v) => !exp.includes(v))
  })

  const previewHtml = computed(() =>
    highlightVariables(editorContent.value, {
      classPrefix: opts.classPrefix,
      expected: opts.expectedVariables ? expectedVariables.value : undefined,
    }),
  )
  const defaultHtml = computed(() =>
    highlightVariables(defaultContent.value, {
      classPrefix: opts.classPrefix,
      expected: opts.expectedVariables ? expectedVariables.value : undefined,
    }),
  )

  watch(selectedKey, () => {
    editorContent.value = savedContent.value
  })

  function syncFromSaved() {
    editorContent.value = savedContent.value
  }

  async function save(): Promise<boolean> {
    if (!opts.adapter.value || !selectedKey.value) return false
    saving.value = true
    try {
      const res = await opts.adapter.value.save(selectedKey.value, editorContent.value)
      feedback.success(res.message ?? '已保存')
      return true
    } catch (e: unknown) {
      feedback.error('保存失败', (e as Error).message)
      return false
    } finally {
      saving.value = false
    }
  }

  async function reset(confirmText?: string): Promise<boolean> {
    if (!opts.adapter.value || !selectedKey.value) return false
    if (!(await confirmDialog(confirmText ?? '确认重置为默认内容？此操作不可撤销。'))) return false
    saving.value = true
    try {
      const res = await opts.adapter.value.reset(selectedKey.value)
      if (typeof res.content === 'string') editorContent.value = res.content
      feedback.success(res.message ?? '已恢复默认')
      return true
    } catch (e: unknown) {
      feedback.error('重置失败', (e as Error).message)
      return false
    } finally {
      saving.value = false
    }
  }

  async function copy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(editorContent.value)
      feedback.info('已复制到剪贴板')
    } catch {
      feedback.warning('无法访问剪贴板')
    }
  }

  function applyDefault(message = '已加载默认内容，需点击保存才会生效'): void {
    editorContent.value = defaultContent.value
    feedback.info(message)
  }

  function insertVariable(name: string): void {
    editorContent.value = (editorContent.value || '') + `{${name}}`
  }

  return {
    selectedKey,
    editorContent,
    saving,
    hasChanges,
    usedVariables,
    defaultVariables,
    missingVariables,
    extraVariables,
    previewHtml,
    defaultHtml,
    syncFromSaved,
    save,
    reset,
    copy,
    applyDefault,
    insertVariable,
  }
}
