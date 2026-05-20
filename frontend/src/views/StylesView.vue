<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { stylesApi, postSSE, configApi } from '@/api/client'
import { useConfigStore } from '@/stores/config'
import { useProjectStore } from '@/stores/project'
import { useFeedbackStore } from '@/stores/feedback'
import StreamOutput from '@/components/StreamOutput.vue'

const configStore = useConfigStore()
const projectStore = useProjectStore()
const feedback = useFeedbackStore()

interface StyleDetail {
  style_name: string
  style_instruction: string
  analysis_result: string
  source_sample: string
  calibration_reference: string
  has_calibration_snapshot: boolean
  snapshot_timestamp: string
  narrative_for_architecture: string
  narrative_for_blueprint: string
  narrative_for_chapter: string
}

const styleList = ref<string[]>([])
const styleDetails = ref<Record<string, StyleDetail>>({})
const selectedStyle = ref('')

// 默认文风（全局）
const defaultStyle = ref({ arch_style: '', bp_style: '', ch_style: '', ch_narrative_style: '' })

// 编辑表单（绑定到选中文风）
const styleInstruction = ref('')
const analysisResult = ref('')
const sourceSample = ref('')
const calibrationReference = ref('')
const hasCalibrationSnapshot = ref(false)
const snapshotTimestamp = ref('')
const narrativeForArch = ref('')
const narrativeForBp = ref('')
const narrativeForCh = ref('')

const search = ref('')
const filterHasDNA = ref<'all' | 'with' | 'without'>('all')
const previewMode = ref<'instruction' | 'dna' | 'sample'>('instruction')
const dnaLayer = ref<'arch' | 'bp' | 'ch'>('arch')

const analyzeLLM = ref('')
const sampleText = ref('')
const newStyleName = ref('')
const analyzeState = ref({ running: false, progress: '', result: '', error: '' })

const dnaSampleText = ref('')
const dnaState = ref({ running: false, progress: '', result: '', error: '' })

const calibrateMaxIter = ref(5)
const calibrateState = ref({ running: false, progress: '', result: '', error: '' })

const narrativeCalibrateMaxIter = ref(5)
const narrativeCalibrateState = ref({ running: false, progress: '', result: '', error: '' })

const mergeSelected = ref<string[]>([])
const mergeName = ref('')
const mergePreference = ref('')
const mergeState = ref({ running: false, progress: '', result: '', error: '' })

const unlock = ref(false)

const authorRefFiles = ref<File[]>([])
const authorRefImporting = ref(false)
const authorRefStatus = ref<Record<string, boolean>>({})
const authorRefEmbConfig = ref('')
const authorRefImportTags = ref('')
const authorRefRebuilding = ref(false)

interface AuthorRefRecord {
  file_id: string
  filename: string
  tags: string[]
  author?: string
  size_bytes: number
  chunks: number
  imported_at: string
  status: 'ok' | 'indexing' | 'error'
  error?: string
}
interface AuthorRefStats {
  exists: boolean
  file_count: number
  manifest_chunks: number
  vector_count: number | null
  error_count: number
  indexing_count: number
  orphan_warning: string
}
interface AuthorRefHit {
  file_id: string
  filename: string
  chunk_idx: number
  score: number
  snippet: string
}

const authorRefList = ref<AuthorRefRecord[]>([])
const authorRefStatsData = ref<AuthorRefStats | null>(null)
const authorRefQuery = ref('')
const authorRefSearching = ref(false)
const authorRefHits = ref<AuthorRefHit[]>([])
const authorRefSourcePreview = ref<{ filename: string; text: string } | null>(null)

function onAuthorRefFile(e: Event) {
  const files = (e.target as HTMLInputElement).files
  authorRefFiles.value = files ? Array.from(files) : []
}

async function loadAuthorRefStatus(name: string) {
  if (!name) return
  try {
    const res = await stylesApi.authorRefStatus(name)
    authorRefStatus.value[name] = res.data.has_author_reference
  } catch { authorRefStatus.value[name] = false }
}

async function loadAuthorRefDetail(name: string) {
  if (!name) {
    authorRefList.value = []
    authorRefStatsData.value = null
    return
  }
  try {
    const [fRes, sRes] = await Promise.all([
      stylesApi.authorRefFiles(name),
      stylesApi.authorRefStats(name, authorRefEmbConfig.value),
    ])
    authorRefList.value = fRes.data.files || []
    authorRefStatsData.value = sRes.data
    authorRefStatus.value[name] = (sRes.data.file_count || 0) > 0
  } catch (e: unknown) {
    authorRefList.value = []
    authorRefStatsData.value = null
  }
}

async function importAuthorRef() {
  if (!selectedStyle.value || !authorRefFiles.value.length || !authorRefEmbConfig.value) return
  authorRefImporting.value = true
  let success = 0, failed = 0
  for (const file of authorRefFiles.value) {
    try {
      const fd = new FormData()
      fd.append('emb_config_name', authorRefEmbConfig.value)
      fd.append('file', file)
      if (authorRefImportTags.value.trim()) fd.append('tags', authorRefImportTags.value.trim())
      await stylesApi.importAuthorRef(selectedStyle.value, fd)
      success++
    } catch { failed++ }
  }
  authorRefImporting.value = false
  if (failed) feedback.warning(`参考库导入完成：${success} 成功 / ${failed} 失败`)
  else feedback.success(`✅ 参考库 ${success} 个文件全部导入`)
  authorRefFiles.value = []
  authorRefImportTags.value = ''
  await loadAuthorRefDetail(selectedStyle.value)
}

async function deleteAuthorRefFile(rec: AuthorRefRecord) {
  if (!selectedStyle.value) return
  if (!confirm(`确认删除「${rec.filename}」？`)) return
  try {
    await stylesApi.deleteAuthorRefFile(selectedStyle.value, rec.file_id, authorRefEmbConfig.value)
    feedback.success(`已删除「${rec.filename}」`)
    await loadAuthorRefDetail(selectedStyle.value)
  } catch (e: unknown) {
    feedback.error('删除失败', (e as Error).message)
  }
}

async function renameAuthorRefFile(rec: AuthorRefRecord) {
  if (!selectedStyle.value) return
  const next = window.prompt('新文件名', rec.filename)
  if (!next || next === rec.filename) return
  try {
    await stylesApi.updateAuthorRefFile(selectedStyle.value, rec.file_id, { filename: next })
    feedback.success('已更新')
    await loadAuthorRefDetail(selectedStyle.value)
  } catch (e: unknown) {
    feedback.error('更新失败', (e as Error).message)
  }
}

async function viewAuthorRefSource(rec: AuthorRefRecord) {
  if (!selectedStyle.value) return
  try {
    const res = await stylesApi.authorRefSource(selectedStyle.value, rec.file_id)
    authorRefSourcePreview.value = { filename: rec.filename, text: res.data.text }
  } catch (e: unknown) {
    feedback.error('读取原文失败', (e as Error).message)
  }
}

async function searchAuthorRef() {
  if (!selectedStyle.value || !authorRefQuery.value.trim()) return
  if (!authorRefEmbConfig.value) {
    feedback.warning('请先选择 Embedding')
    return
  }
  authorRefSearching.value = true
  authorRefHits.value = []
  try {
    const res = await stylesApi.searchAuthorRef(
      selectedStyle.value,
      authorRefQuery.value.trim(),
      authorRefEmbConfig.value,
      6,
    )
    authorRefHits.value = res.data.hits || []
    if (!authorRefHits.value.length) feedback.info('没有命中任何片段')
  } catch (e: unknown) {
    feedback.error('检索失败', (e as Error).message)
  } finally {
    authorRefSearching.value = false
  }
}

async function rebuildAuthorRef() {
  if (!selectedStyle.value) return
  if (!authorRefEmbConfig.value) {
    feedback.warning('请先选择 Embedding')
    return
  }
  if (!confirm('确认重建作者参考库索引？将基于已保存源文件重新嵌入。')) return
  authorRefRebuilding.value = true
  try {
    const res = await stylesApi.rebuildAuthorRef(selectedStyle.value, authorRefEmbConfig.value)
    feedback.success(res.data.message)
    await loadAuthorRefDetail(selectedStyle.value)
  } catch (e: unknown) {
    feedback.error('重建失败', (e as Error).message)
  } finally {
    authorRefRebuilding.value = false
  }
}

async function clearAuthorRef() {
  if (!selectedStyle.value) return
  if (!confirm(`确认清空文风「${selectedStyle.value}」的作者参考库？将删除全部源文件与向量。`)) return
  try {
    await stylesApi.clearAuthorRef(selectedStyle.value)
    authorRefStatus.value[selectedStyle.value] = false
    feedback.success('✅ 已清空参考库')
    await loadAuthorRefDetail(selectedStyle.value)
  } catch (e) { feedback.error('清空失败', (e as Error).message) }
}

function fmtAuthorRefBytes(n: number): string {
  if (!n) return '0 B'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(2)} MB`
}

async function loadStyles() {
  const res = await stylesApi.list()
  styleList.value = res.data.styles
}

async function loadStyleDetail(name: string) {
  if (!name) return
  try {
    const res = await stylesApi.get(name)
    const data = res.data as StyleDetail
    styleDetails.value[name] = data
    if (selectedStyle.value === name) {
      styleInstruction.value = data.style_instruction
      analysisResult.value = data.analysis_result
      sourceSample.value = data.source_sample ?? ''
      calibrationReference.value = data.calibration_reference ?? ''
      hasCalibrationSnapshot.value = data.has_calibration_snapshot ?? false
      snapshotTimestamp.value = data.snapshot_timestamp ?? ''
      narrativeForArch.value = data.narrative_for_architecture ?? ''
      narrativeForBp.value = data.narrative_for_blueprint ?? ''
      narrativeForCh.value = data.narrative_for_chapter ?? ''
    }
    loadAuthorRefStatus(name)
    loadAuthorRefDetail(name)
  } catch (e: unknown) {
    feedback.error('加载文风失败', (e as Error).message)
  }
}

watch(selectedStyle, (name) => { if (name) loadStyleDetail(name) })

async function saveStyle() {
  if (!selectedStyle.value) return
  try {
    await stylesApi.save(selectedStyle.value, {
      analysis_result: analysisResult.value,
      style_instruction: styleInstruction.value,
      source_sample: sourceSample.value,
      calibration_reference: calibrationReference.value,
      narrative_for_architecture: narrativeForArch.value,
      narrative_for_blueprint: narrativeForBp.value,
      narrative_for_chapter: narrativeForCh.value,
    })
    feedback.success(`✅ 文风「${selectedStyle.value}」已保存`)
    loadStyleDetail(selectedStyle.value)
  } catch (e: unknown) {
    feedback.error('保存失败', (e as Error).message)
  }
}

async function deleteStyle() {
  if (!selectedStyle.value) return
  if (!confirm(`确认删除文风「${selectedStyle.value}」？`)) return
  try {
    await stylesApi.delete(selectedStyle.value)
    await loadStyles()
    selectedStyle.value = ''
    feedback.success('✅ 已删除')
  } catch (e: unknown) { feedback.error('删除失败', (e as Error).message) }
}

async function copyInstruction() {
  if (!styleInstruction.value) return
  try {
    await navigator.clipboard.writeText(styleInstruction.value)
    feedback.info('已复制风格指令')
  } catch { feedback.warning('无法访问剪贴板') }
}

function runSSE(state: typeof analyzeState.value, url: string, body: Record<string, unknown>) {
  state.running = true; state.progress = ''; state.result = ''; state.error = ''
  postSSE(url, body,
    (msg) => { state.progress = msg },
    (content) => { state.result = content; loadStyles() },
    (err) => { state.error = err; state.running = false; feedback.error('任务失败', err) },
    () => { state.running = false },
  )
}

function doAnalyze() {
  if (!analyzeLLM.value || !newStyleName.value || !sampleText.value) return
  runSSE(analyzeState.value, '/styles/analyze', {
    llm_config_name: analyzeLLM.value,
    sample_text: sampleText.value,
    style_name: newStyleName.value,
    unlock: unlock.value,
  })
}

function doAnalyzeDNA() {
  if (!analyzeLLM.value || !selectedStyle.value || !dnaSampleText.value) return
  runSSE(dnaState.value, '/styles/analyze-dna', {
    llm_config_name: analyzeLLM.value,
    sample_text: dnaSampleText.value,
    style_name: selectedStyle.value,
    unlock: unlock.value,
  })
}

function doCalibrate() {
  if (!analyzeLLM.value || !selectedStyle.value) return
  const st = calibrateState.value
  st.running = true; st.progress = ''; st.result = ''; st.error = ''
  postSSE('/styles/calibrate', {
    llm_config_name: analyzeLLM.value, style_name: selectedStyle.value,
    max_iterations: calibrateMaxIter.value, unlock: unlock.value,
  },
    (msg) => { st.progress = msg },
    (content) => { st.result = content; loadStyleDetail(selectedStyle.value) },
    (err) => { st.error = err; st.running = false; feedback.error('校准失败', err) },
    () => { st.running = false },
  )
}

function doCalibrateNarrative() {
  if (!analyzeLLM.value || !selectedStyle.value) return
  const st = narrativeCalibrateState.value
  st.running = true; st.progress = ''; st.result = ''; st.error = ''
  postSSE('/styles/calibrate-narrative', {
    llm_config_name: analyzeLLM.value, style_name: selectedStyle.value,
    max_iterations: narrativeCalibrateMaxIter.value, unlock: unlock.value,
  },
    (msg) => { st.progress = msg },
    (content) => { st.result = content; loadStyleDetail(selectedStyle.value) },
    (err) => { st.error = err; st.running = false; feedback.error('叙事校准失败', err) },
    () => { st.running = false },
  )
}

async function doRollback() {
  if (!selectedStyle.value) return
  if (!confirm(`确认回滚文风「${selectedStyle.value}」到校准前状态？`)) return
  try {
    await stylesApi.rollbackCalibration(selectedStyle.value)
    await loadStyleDetail(selectedStyle.value)
    feedback.success(`✅ 已回滚到校准前状态`)
  } catch (e: unknown) { feedback.error('回滚失败', (e as Error).message) }
}

function doMerge() {
  if (!analyzeLLM.value || mergeSelected.value.length < 2 || !mergeName.value) return
  runSSE(mergeState.value, '/styles/merge', {
    llm_config_name: analyzeLLM.value, selected_styles: mergeSelected.value,
    merge_name: mergeName.value, user_preference: mergePreference.value, unlock: unlock.value,
  })
}

// 应用到当前项目
async function applyToProject(scope: 'arch' | 'bp' | 'ch' | 'all') {
  if (!selectedStyle.value || !projectStore.activeProject) {
    feedback.warning('请先选择文风并激活一个项目')
    return
  }
  const patch: Record<string, string> = {}
  if (scope === 'arch' || scope === 'all') patch.arch_style = selectedStyle.value
  if (scope === 'bp' || scope === 'all') patch.bp_style = selectedStyle.value
  if (scope === 'ch' || scope === 'all') {
    patch.ch_style = selectedStyle.value
    patch.ch_narrative_style = selectedStyle.value
  }
  try {
    await projectStore.saveProject(patch)
    const detail = scope === 'all' ? '所有阶段已切换' : `${scope === 'arch' ? '架构' : scope === 'bp' ? '蓝图' : '章节'}层已切换`
    feedback.success(`✅ 已应用文风「${selectedStyle.value}」到当前项目（${detail}）`)
  } catch (e: unknown) { feedback.error('应用失败', (e as Error).message) }
}

async function loadDefaultStyle() {
  try {
    const res = await configApi.getDefaultStyle()
    defaultStyle.value = {
      arch_style: res.data.arch_style ?? '',
      bp_style: res.data.bp_style ?? '',
      ch_style: res.data.ch_style ?? '',
      ch_narrative_style: res.data.ch_narrative_style ?? '',
    }
  } catch { /* 配置不存在时静默 */ }
}

async function setAsGlobalDefault(scope: 'arch' | 'bp' | 'ch' | 'all') {
  if (!selectedStyle.value) return
  const patch: Record<string, string> = {}
  if (scope === 'arch' || scope === 'all') patch.arch_style = selectedStyle.value
  if (scope === 'bp' || scope === 'all') patch.bp_style = selectedStyle.value
  if (scope === 'ch' || scope === 'all') {
    patch.ch_style = selectedStyle.value
    patch.ch_narrative_style = selectedStyle.value
  }
  try {
    await configApi.saveDefaultStyle(patch)
    await loadDefaultStyle()
    const detail = scope === 'all' ? '新建项目会自动应用' : `仅 ${scope} 层`
    feedback.success(`✅ 已设为全局默认文风（${detail}）`)
  } catch (e: unknown) { feedback.error('设置失败', (e as Error).message) }
}

// 选中文风派生信息
const selectedDetail = computed(() => selectedStyle.value ? styleDetails.value[selectedStyle.value] : null)
const hasDNA = computed(() => {
  const d = selectedDetail.value
  return Boolean(d && (d.narrative_for_architecture || d.narrative_for_blueprint || d.narrative_for_chapter))
})

const projectUsage = computed(() => {
  if (!selectedStyle.value || !projectStore.activeProjectData) return [] as string[]
  const p = projectStore.activeProjectData
  const used: string[] = []
  if (p.arch_style === selectedStyle.value) used.push('架构')
  if (p.bp_style === selectedStyle.value) used.push('蓝图')
  if (p.ch_style === selectedStyle.value) used.push('章节')
  if (p.ch_narrative_style === selectedStyle.value) used.push('章节DNA')
  return used
})

const isGlobalDefault = computed(() => {
  if (!selectedStyle.value) return [] as string[]
  const d = defaultStyle.value
  const used: string[] = []
  if (d.arch_style === selectedStyle.value) used.push('架构')
  if (d.bp_style === selectedStyle.value) used.push('蓝图')
  if (d.ch_style === selectedStyle.value) used.push('章节')
  if (d.ch_narrative_style === selectedStyle.value) used.push('章节DNA')
  return used
})

const filteredStyles = computed(() => {
  const kw = search.value.trim().toLowerCase()
  return styleList.value.filter((s) => {
    if (kw && !s.toLowerCase().includes(kw)) return false
    if (filterHasDNA.value !== 'all') {
      const d = styleDetails.value[s]
      const dnaExists = Boolean(d && (d.narrative_for_architecture || d.narrative_for_blueprint || d.narrative_for_chapter))
      if (filterHasDNA.value === 'with' && !dnaExists) return false
      if (filterHasDNA.value === 'without' && dnaExists) return false
    }
    return true
  })
})

const previewText = computed(() => {
  if (!selectedDetail.value) return ''
  if (previewMode.value === 'instruction') return styleInstruction.value
  if (previewMode.value === 'sample') return sourceSample.value || '（无原始样本）'
  // DNA
  if (dnaLayer.value === 'arch') return narrativeForArch.value || '（架构层 DNA 为空，请先在右侧分析叙事DNA）'
  if (dnaLayer.value === 'bp') return narrativeForBp.value || '（蓝图层 DNA 为空）'
  return narrativeForCh.value || '（章节层 DNA 为空）'
})

onMounted(async () => {
  await configStore.loadAll()
  await projectStore.loadActive()
  await loadStyles()
  await loadDefaultStyle()
  if (configStore.llmChoices.length) analyzeLLM.value = configStore.llmChoices[0]
  if (configStore.embeddingChoices.length) authorRefEmbConfig.value = configStore.embeddingChoices[0]
  // 预取所有文风详情以支持过滤/筛选
  for (const s of styleList.value) await loadStyleDetail(s)
})

watch(() => configStore.llmChoices.slice(), (c) => {
  if (!c.length) { analyzeLLM.value = ''; return }
  if (!analyzeLLM.value || !c.includes(analyzeLLM.value)) analyzeLLM.value = c[0]
})
watch(() => configStore.embeddingChoices.slice(), (c) => {
  if (!c.length) { authorRefEmbConfig.value = ''; return }
  if (!authorRefEmbConfig.value || !c.includes(authorRefEmbConfig.value)) authorRefEmbConfig.value = c[0]
})
</script>

<template>
  <div class="module-page space-y-4">
    <div class="module-toolbar">
      <div>
        <h2 class="text-2xl font-bold" style="color: var(--color-ink)">文风与叙事DNA</h2>
        <div class="module-kicker">Style & Narrative DNA</div>
        <div class="module-subtitle">
          库 + 预览 + 应用三段式：左侧选择文风，中间预览风格指令或分层叙事DNA，右侧一键应用到当前项目或设为全局默认。
        </div>
      </div>
      <div class="module-action-row">
        <label class="sv-toggle">
          <input type="checkbox" v-model="unlock" class="accent-amber-600" />
          内容解锁
        </label>
        <select v-model="analyzeLLM" class="sv-input">
          <option v-for="c in configStore.llmChoices" :key="c" :value="c">{{ c }}</option>
        </select>
      </div>
    </div>

    <!-- 概念说明 -->
    <details class="sv-explainer-wrap">
      <summary class="sv-explainer-summary">📖 文风 / 叙事 DNA 概念说明（点击展开）</summary>
      <section class="sv-explainer">
        <div class="sv-explainer-item">
          <div class="sv-explainer-head">🎨 风格指令（Style Instruction）</div>
          <div class="sv-explainer-body">
            一段紧凑的"文风摘要"，会被注入到<strong>章节正文草稿</strong>提示词，告诉 LLM 该用什么样的句式、用词、节奏写。<br />
            来源：从样本文本分析得到（"分析新文风"），可经"迭代校准"反复优化。
          </div>
        </div>
        <div class="sv-explainer-item">
          <div class="sv-explainer-head">🧬 叙事DNA（Narrative DNA）</div>
          <div class="sv-explainer-body">
            分层（架构 / 蓝图 / 章节）的叙事模式指令。分别注入到对应阶段的生成提示词，决定<strong>结构层面</strong>的风格——
            推进节奏、场景结构、对话密度等。<br />
            需要在该文风存在的前提下，再单独执行"分析叙事DNA"。
          </div>
        </div>
        <div class="sv-explainer-item">
          <div class="sv-explainer-head">⚙️ 在项目里如何生效？</div>
          <div class="sv-explainer-body">
            工坊每一步（架构/蓝图/章节）独立选择一个文风。如果选了某文风但它没有对应层的 DNA，将只使用风格指令；
            如果有 DNA，会一并注入。本页面"应用到当前项目"会一次性更新选中阶段的文风字段。
          </div>
        </div>
      </section>
    </details>

    <section class="sv-grid">
      <!-- 左：文风库 -->
      <aside class="module-panel sv-library">
        <div class="sv-lib-head">
          <input v-model="search" placeholder="搜索文风…" class="sv-input sv-search" />
          <select v-model="filterHasDNA" class="sv-input">
            <option value="all">全部</option>
            <option value="with">含叙事DNA</option>
            <option value="without">无叙事DNA</option>
          </select>
          <div class="sv-lib-count">共 {{ filteredStyles.length }} / {{ styleList.length }} 个文风</div>
        </div>
        <div class="sv-lib-list">
          <button
            v-for="s in filteredStyles"
            :key="s"
            type="button"
            class="sv-item"
            :class="{ active: s === selectedStyle }"
            @click="selectedStyle = s"
          >
            <div class="sv-item-top">
              <span class="sv-item-name">{{ s }}</span>
              <div class="sv-item-badges">
                <span v-if="styleDetails[s]?.narrative_for_architecture
                  || styleDetails[s]?.narrative_for_blueprint
                  || styleDetails[s]?.narrative_for_chapter"
                  class="sv-badge dna" title="已生成叙事DNA">DNA</span>
                <span v-if="styleDetails[s]?.has_calibration_snapshot" class="sv-badge cal" title="可回滚校准">校准</span>
                <span v-if="authorRefStatus[s]" class="sv-badge ref" title="已导入作者参考库">参考</span>
              </div>
            </div>
            <div class="sv-item-desc" v-if="styleDetails[s]?.style_instruction">
              {{ styleDetails[s]?.style_instruction.slice(0, 80) }}…
            </div>
          </button>
          <div v-if="!filteredStyles.length" class="sv-empty">没有匹配的文风</div>
        </div>
      </aside>

      <!-- 中：预览 / 编辑 -->
      <main class="module-panel sv-preview">
        <div class="sv-preview-head" v-if="selectedStyle">
          <div class="flex-1 min-w-0">
            <h3 class="module-panel-title flex items-center gap-2 flex-wrap">
              {{ selectedStyle }}
              <span v-if="hasDNA" class="sv-badge dna">含叙事DNA</span>
              <span v-if="projectUsage.length" class="sv-badge use" :title="`当前项目使用：${projectUsage.join('/')}`">
                项目使用中：{{ projectUsage.join(' · ') }}
              </span>
              <span v-if="isGlobalDefault.length" class="sv-badge def" :title="`全局默认：${isGlobalDefault.join('/')}`">
                全局默认：{{ isGlobalDefault.join(' · ') }}
              </span>
            </h3>
          </div>
          <div class="sv-mode-tabs">
            <button class="sv-mode-tab" :class="{ active: previewMode === 'instruction' }" type="button" @click="previewMode = 'instruction'">风格指令</button>
            <button class="sv-mode-tab" :class="{ active: previewMode === 'dna' }" type="button" @click="previewMode = 'dna'">叙事DNA</button>
            <button class="sv-mode-tab" :class="{ active: previewMode === 'sample' }" type="button" @click="previewMode = 'sample'">原始样本</button>
          </div>
        </div>

        <div v-if="selectedStyle" class="sv-preview-body">
          <div v-if="previewMode === 'dna'" class="sv-dna-layers">
            <button class="sv-layer-tab" :class="{ active: dnaLayer === 'arch' }" type="button" @click="dnaLayer = 'arch'">
              架构层 <span v-if="narrativeForArch" class="sv-dot ok">●</span><span v-else class="sv-dot off">○</span>
            </button>
            <button class="sv-layer-tab" :class="{ active: dnaLayer === 'bp' }" type="button" @click="dnaLayer = 'bp'">
              蓝图层 <span v-if="narrativeForBp" class="sv-dot ok">●</span><span v-else class="sv-dot off">○</span>
            </button>
            <button class="sv-layer-tab" :class="{ active: dnaLayer === 'ch' }" type="button" @click="dnaLayer = 'ch'">
              章节层 <span v-if="narrativeForCh" class="sv-dot ok">●</span><span v-else class="sv-dot off">○</span>
            </button>
          </div>

          <textarea
            v-if="previewMode === 'instruction'"
            v-model="styleInstruction"
            class="sv-editor"
            rows="8"
            placeholder="风格指令摘要…"
          />
          <textarea
            v-else-if="previewMode === 'dna' && dnaLayer === 'arch'"
            v-model="narrativeForArch"
            class="sv-editor"
            rows="12"
            placeholder="架构层叙事DNA…"
          />
          <textarea
            v-else-if="previewMode === 'dna' && dnaLayer === 'bp'"
            v-model="narrativeForBp"
            class="sv-editor"
            rows="12"
            placeholder="蓝图层叙事DNA…"
          />
          <textarea
            v-else-if="previewMode === 'dna' && dnaLayer === 'ch'"
            v-model="narrativeForCh"
            class="sv-editor"
            rows="12"
            placeholder="章节层叙事DNA…"
          />
          <textarea
            v-else-if="previewMode === 'sample'"
            v-model="sourceSample"
            class="sv-editor"
            rows="12"
            placeholder="原始样本（前 5000 字用于校准）…"
          />

          <details class="sv-extra">
            <summary>完整分析报告 / 校准参考样本</summary>
            <div class="space-y-3 pt-2">
              <div>
                <label class="sv-label">分析报告</label>
                <textarea v-model="analysisResult" rows="6" class="sv-editor" />
              </div>
              <div>
                <label class="sv-label">校准参考样本（同一作者另一段文本，盲测时与 AI 仿写混合）</label>
                <textarea v-model="calibrationReference" rows="6" class="sv-editor" />
              </div>
            </div>
          </details>
        </div>
        <div v-else class="sv-empty sv-empty-large">在左侧选择一个文风</div>
      </main>

      <!-- 右：应用 -->
      <aside class="module-panel sv-apply" v-if="selectedStyle">
        <h3 class="module-panel-title">应用</h3>
        <p class="module-panel-caption">将「{{ selectedStyle }}」一键应用到不同范围。</p>

        <div class="sv-apply-group">
          <div class="sv-apply-title">应用到当前项目
            <span v-if="projectStore.activeProject" class="sv-project-name">{{ projectStore.activeProject }}</span>
            <span v-else class="sv-empty-mini">无激活项目</span>
          </div>
          <div class="sv-apply-actions">
            <button @click="applyToProject('all')" :disabled="!projectStore.activeProject" type="button" class="sv-btn-primary">
              全部阶段（架构 + 蓝图 + 章节）
            </button>
            <div class="sv-apply-row">
              <button @click="applyToProject('arch')" :disabled="!projectStore.activeProject" type="button" class="sv-btn">仅架构</button>
              <button @click="applyToProject('bp')" :disabled="!projectStore.activeProject" type="button" class="sv-btn">仅蓝图</button>
              <button @click="applyToProject('ch')" :disabled="!projectStore.activeProject" type="button" class="sv-btn">仅章节</button>
            </div>
          </div>
        </div>

        <div class="sv-apply-group">
          <div class="sv-apply-title">设为全局默认<br />
            <span class="sv-help">新建项目时自动应用</span>
          </div>
          <div class="sv-apply-actions">
            <button @click="setAsGlobalDefault('all')" type="button" class="sv-btn-primary">全部阶段</button>
            <div class="sv-apply-row">
              <button @click="setAsGlobalDefault('arch')" type="button" class="sv-btn">仅架构</button>
              <button @click="setAsGlobalDefault('bp')" type="button" class="sv-btn">仅蓝图</button>
              <button @click="setAsGlobalDefault('ch')" type="button" class="sv-btn">仅章节</button>
            </div>
          </div>
        </div>

        <div class="sv-apply-group">
          <div class="sv-apply-title">编辑操作</div>
          <div class="sv-apply-actions">
            <button @click="saveStyle" type="button" class="sv-btn-primary">保存当前编辑</button>
            <button @click="copyInstruction" type="button" class="sv-btn">复制风格指令</button>
            <button @click="deleteStyle" type="button" class="sv-btn-danger">删除文风</button>
          </div>
        </div>
      </aside>
    </section>

    <!-- 进阶操作折叠区 -->
    <details class="module-panel sv-advanced" open>
      <summary>进阶：分析 / 校准 / 融合 / 作者参考库</summary>
      <div class="sv-adv-body">
        <!-- 校准 -->
        <div v-if="selectedStyle" class="sv-adv-section">
          <h4 class="sv-adv-title">迭代校准（图灵盲测）</h4>
          <p class="sv-help">对「{{ selectedStyle }}」的风格指令做迭代优化：自动生成测试文本与参考样本混合后进行图灵盲测。</p>
          <div class="sv-adv-row">
            <label class="sv-label-inline">最大轮次</label>
            <input v-model.number="calibrateMaxIter" type="number" min="1" max="10" class="sv-input sv-input-num" />
            <div class="flex-1" />
            <button v-if="hasCalibrationSnapshot" @click="doRollback" type="button" class="sv-btn-warn">
              回滚{{ snapshotTimestamp ? `（${snapshotTimestamp.slice(0, 16)}）` : '' }}
            </button>
            <button @click="doCalibrate" :disabled="calibrateState.running" type="button" class="sv-btn-primary">
              {{ calibrateState.running ? '校准中…' : '▶ 迭代校准（风格）' }}
            </button>
            <button @click="doCalibrateNarrative" :disabled="narrativeCalibrateState.running" type="button" class="sv-btn-primary">
              {{ narrativeCalibrateState.running ? '校准中…' : '▶ 迭代校准（叙事DNA）' }}
            </button>
          </div>
          <StreamOutput v-if="calibrateState.running || calibrateState.result || calibrateState.error" v-bind="calibrateState" placeholder="" />
          <StreamOutput v-if="narrativeCalibrateState.running || narrativeCalibrateState.result || narrativeCalibrateState.error" v-bind="narrativeCalibrateState" placeholder="" />
        </div>

        <!-- 作者参考库 -->
        <div v-if="selectedStyle" class="sv-adv-section">
          <h4 class="sv-adv-title">
            作者参考库
            <span v-if="authorRefStatsData?.file_count" class="sv-badge ref">{{ authorRefStatsData.file_count }} 文件 · {{ authorRefStatsData.manifest_chunks }} 切片</span>
            <span v-else class="sv-badge off">未导入</span>
          </h4>
          <p class="sv-help">上传目标作者作品 (.txt)；生成章节时自动检索相关片段辅助仿写。每个文件单独管理、可独立删除/重建。</p>

          <div v-if="!configStore.embeddingChoices.length" class="sv-help" style="color: #b54708; padding: 6px 0;">
            ⚠️ 尚未配置 Embedding，请到「配置 → Embedding」创建。
          </div>

          <div v-if="authorRefStatsData?.orphan_warning" class="sv-help" style="color: #b54708; padding: 6px 0;">
            ⚠️ {{ authorRefStatsData.orphan_warning }}
          </div>

          <!-- 导入 -->
          <div class="sv-adv-row">
            <select v-model="authorRefEmbConfig" class="sv-input">
              <option v-for="c in configStore.embeddingChoices" :key="c" :value="c">{{ c }}</option>
            </select>
            <input type="file" accept=".txt,.md" multiple @change="onAuthorRefFile" class="text-sm" />
            <input v-model="authorRefImportTags" type="text" placeholder="标签（逗号分隔，可选）" class="sv-input" />
            <button @click="importAuthorRef" :disabled="authorRefImporting || !authorRefFiles.length || !authorRefEmbConfig"
              type="button" class="sv-btn-primary">
              {{ authorRefImporting ? '导入中…' : `▶ 导入 (${authorRefFiles.length})` }}
            </button>
          </div>

          <!-- 文件列表 -->
          <div v-if="authorRefList.length" class="sv-author-files">
            <table class="sv-author-table">
              <thead>
                <tr>
                  <th>文件名</th>
                  <th>标签</th>
                  <th>大小</th>
                  <th>切片</th>
                  <th>导入时间</th>
                  <th>状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="f in authorRefList" :key="f.file_id">
                  <td :title="f.filename">{{ f.filename }}</td>
                  <td>
                    <span v-for="t in f.tags" :key="t" class="sv-tag">{{ t }}</span>
                  </td>
                  <td>{{ fmtAuthorRefBytes(f.size_bytes) }}</td>
                  <td>{{ f.chunks }}</td>
                  <td class="sv-cell-light">{{ f.imported_at }}</td>
                  <td>
                    <span class="sv-status" :class="`sv-status-${f.status}`">
                      {{ f.status === 'ok' ? '已索引' : f.status === 'indexing' ? '索引中' : '失败' }}
                    </span>
                  </td>
                  <td class="sv-row-actions">
                    <button @click="viewAuthorRefSource(f)" type="button">原文</button>
                    <button @click="renameAuthorRefFile(f)" type="button">重命名</button>
                    <button @click="deleteAuthorRefFile(f)" type="button" class="sv-row-danger">删除</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- 检索 -->
          <div v-if="authorRefList.length" class="sv-adv-row" style="margin-top: 10px;">
            <input v-model="authorRefQuery" @keyup.enter="searchAuthorRef" type="text" placeholder="检索作者参考库（验证可用性）" class="sv-input flex-1" />
            <button @click="searchAuthorRef" :disabled="authorRefSearching || !authorRefQuery.trim() || !authorRefEmbConfig"
              type="button" class="sv-btn-primary">
              {{ authorRefSearching ? '检索中…' : '🔍 检索' }}
            </button>
          </div>

          <div v-if="authorRefHits.length" class="sv-hits">
            <div v-for="(h, i) in authorRefHits" :key="i" class="sv-hit">
              <div class="sv-hit-meta">📄 {{ h.filename || '(未知)' }} · chunk #{{ h.chunk_idx }} · 相关度 {{ h.score.toFixed(3) }}</div>
              <pre class="sv-hit-body">{{ h.snippet }}</pre>
            </div>
          </div>

          <div class="sv-adv-row" v-if="authorRefList.length">
            <div class="flex-1" />
            <button @click="rebuildAuthorRef" :disabled="authorRefRebuilding || !authorRefEmbConfig"
              type="button" class="sv-btn-warn">
              {{ authorRefRebuilding ? '重建中…' : '🔄 重建索引' }}
            </button>
            <button @click="clearAuthorRef" type="button" class="sv-btn-danger">清空参考库</button>
          </div>

          <!-- 原文预览 -->
          <div v-if="authorRefSourcePreview" class="sv-modal" @click.self="authorRefSourcePreview = null">
            <div class="sv-modal-body">
              <div class="sv-modal-head">
                <span>📄 {{ authorRefSourcePreview.filename }}</span>
                <button @click="authorRefSourcePreview = null" type="button">✕</button>
              </div>
              <pre>{{ authorRefSourcePreview.text }}</pre>
            </div>
          </div>
        </div>

        <!-- 分析新文风 -->
        <div class="sv-adv-section">
          <h4 class="sv-adv-title">分析新文风</h4>
          <div class="sv-adv-row">
            <input v-model="newStyleName" placeholder="文风名称" class="sv-input" />
            <button @click="doAnalyze" :disabled="analyzeState.running || !analyzeLLM || !newStyleName || !sampleText"
              type="button" class="sv-btn-primary">
              {{ analyzeState.running ? '分析中…' : '▶ 分析' }}
            </button>
          </div>
          <textarea v-model="sampleText" rows="5" class="sv-editor" placeholder="样本文本（前 5000 字有效）…" />
          <StreamOutput v-if="analyzeState.running || analyzeState.result || analyzeState.error" v-bind="analyzeState" placeholder="" />
        </div>

        <!-- 分析叙事DNA -->
        <div v-if="selectedStyle" class="sv-adv-section">
          <h4 class="sv-adv-title">分析叙事DNA（{{ selectedStyle }}）</h4>
          <p class="sv-help">为已有文风分析叙事 DNA（架构/蓝图/章节分层指令）。</p>
          <textarea v-model="dnaSampleText" rows="5" class="sv-editor" placeholder="样本文本（前 5000 字有效）…" />
          <div class="sv-adv-row">
            <div class="flex-1" />
            <button @click="doAnalyzeDNA" :disabled="dnaState.running || !analyzeLLM || !dnaSampleText"
              type="button" class="sv-btn-primary">
              {{ dnaState.running ? '分析中…' : '▶ 分析叙事DNA' }}
            </button>
          </div>
          <StreamOutput v-if="dnaState.running || dnaState.result || dnaState.error" v-bind="dnaState" placeholder="" />
        </div>

        <!-- 融合 -->
        <div class="sv-adv-section">
          <h4 class="sv-adv-title">融合文风</h4>
          <div class="sv-adv-row">
            <input v-model="mergeName" placeholder="融合后名称" class="sv-input" />
            <input v-model="mergePreference" placeholder="融合偏好（可选）" class="sv-input" />
            <button @click="doMerge" :disabled="mergeState.running || mergeSelected.length < 2 || !mergeName"
              type="button" class="sv-btn-primary">
              {{ mergeState.running ? '融合中…' : '▶ 融合' }}
            </button>
          </div>
          <div class="sv-merge-list">
            <label v-for="s in styleList" :key="s" class="sv-merge-chip">
              <input type="checkbox" :value="s" v-model="mergeSelected" />
              {{ s }}
            </label>
          </div>
          <StreamOutput v-if="mergeState.running || mergeState.result || mergeState.error" v-bind="mergeState" placeholder="" />
        </div>
      </div>
    </details>
  </div>
</template>

<style scoped>
.sv-input { padding: 5px 10px; font-size: 12px; border: 1px solid var(--color-parchment-darker); border-radius: 6px; background: white; min-width: 0; }
.sv-input-num { width: 70px; }
.sv-search { flex: 1; }
.sv-toggle { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: var(--color-ink-light); cursor: pointer; }
.sv-label { display: block; font-size: 11px; color: var(--color-ink-light); margin-bottom: 4px; }
.sv-label-inline { font-size: 11px; color: var(--color-ink-light); white-space: nowrap; }
.sv-help { font-size: 11px; color: var(--color-ink-light); }
.sv-empty { padding: 18px; text-align: center; font-size: 12px; color: var(--color-ink-light); }
.sv-empty-large { padding: 60px 20px; }
.sv-empty-mini { font-size: 10px; color: var(--color-ink-light); margin-left: 4px; }

.sv-btn-primary { padding: 6px 12px; font-size: 12px; font-weight: 600; border-radius: 6px;
  background: var(--color-leather); color: var(--color-parchment); border: none; cursor: pointer; }
.sv-btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.sv-btn { padding: 6px 12px; font-size: 12px; border-radius: 6px;
  background: white; color: var(--color-ink); border: 1px solid var(--color-parchment-darker); cursor: pointer; }
.sv-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.sv-btn-danger { padding: 6px 12px; font-size: 12px; border-radius: 6px;
  background: white; color: #b91c1c; border: 1px solid #fecaca; cursor: pointer; }
.sv-btn-warn { padding: 6px 12px; font-size: 12px; border-radius: 6px;
  background: white; color: #c2410c; border: 1px solid #fdba74; cursor: pointer; }

/* 说明 */
.sv-explainer-wrap { background: var(--color-surface-muted); border: 1px solid var(--color-control-border); border-radius: 10px; padding: 0 12px; }
.sv-explainer-summary { padding: 8px 0; cursor: pointer; font-size: 12px; color: var(--color-ink-light); user-select: none; }
.sv-explainer-wrap[open] .sv-explainer-summary { border-bottom: 1px solid var(--color-control-border); margin-bottom: 8px; }
.sv-explainer { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; padding-bottom: 12px; }
@media (max-width: 1024px) { .sv-explainer { grid-template-columns: 1fr; } }
.sv-explainer-item { padding: 10px 12px; background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; }
.sv-explainer-head { font-size: 12px; font-weight: 700; color: #78350f; margin-bottom: 4px; }
.sv-explainer-body { font-size: 11px; line-height: 1.6; color: #78350f; }

/* 网格 */
.sv-grid { display: grid; grid-template-columns: 280px 1fr 280px; gap: 12px; align-items: stretch; }
@media (max-width: 1280px) { .sv-grid { grid-template-columns: 240px 1fr; } .sv-apply { grid-column: 1 / -1; } }
@media (max-width: 800px) { .sv-grid { grid-template-columns: 1fr; } }

/* 左 */
.sv-library { display: flex; flex-direction: column; padding: 0; max-height: 600px; }
.sv-lib-head { padding: 10px; display: flex; flex-direction: column; gap: 6px; border-bottom: 1px solid var(--color-parchment-darker); }
.sv-lib-count { font-size: 10px; color: var(--color-ink-light); }
.sv-lib-list { overflow-y: auto; padding: 6px; flex: 1; }
.sv-item { display: block; width: 100%; text-align: left; padding: 8px 10px; margin-bottom: 4px;
  background: white; border: 1px solid var(--color-parchment-darker); border-radius: 6px; cursor: pointer; }
.sv-item:hover { background: var(--color-surface-muted); }
.sv-item.active { border-color: var(--color-leather); background: #fffaf2; }
.sv-item-top { display: flex; align-items: center; justify-content: space-between; gap: 6px; }
.sv-item-name { font-size: 12px; font-weight: 600; color: var(--color-ink); }
.sv-item-badges { display: flex; gap: 3px; }
.sv-badge { font-size: 9px; padding: 1px 6px; border-radius: 999px; line-height: 1.4; }
.sv-badge.dna { background: #ede9fe; color: #5b21b6; }
.sv-badge.cal { background: #fef3c7; color: #92400e; }
.sv-badge.ref { background: #d1fae5; color: #065f46; }
.sv-badge.use { background: #dbeafe; color: #1e40af; }
.sv-badge.def { background: #fce7f3; color: #831843; }
.sv-badge.off { background: var(--color-surface-muted); color: var(--color-ink-light); }
.sv-item-desc { font-size: 10px; color: var(--color-ink-light); margin-top: 2px; line-height: 1.4; word-break: break-all; }

/* 中 */
.sv-preview { display: flex; flex-direction: column; padding: 14px; gap: 10px; }
.sv-preview-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; flex-wrap: wrap; }
.sv-mode-tabs { display: flex; gap: 2px; background: var(--color-surface-muted); padding: 2px; border-radius: 6px; }
.sv-mode-tab { padding: 4px 10px; font-size: 11px; border-radius: 4px; background: transparent; border: none; cursor: pointer; color: var(--color-ink-light); }
.sv-mode-tab.active { background: white; color: var(--color-ink); font-weight: 600; }
.sv-preview-body { display: flex; flex-direction: column; gap: 8px; }
.sv-dna-layers { display: flex; gap: 4px; }
.sv-layer-tab { padding: 4px 12px; font-size: 11px; border-radius: 4px;
  background: white; border: 1px solid var(--color-parchment-darker); cursor: pointer;
  display: inline-flex; align-items: center; gap: 4px; }
.sv-layer-tab.active { background: var(--color-leather); color: var(--color-parchment); border-color: var(--color-leather); }
.sv-dot.ok { color: #16a34a; }
.sv-dot.off { color: #d1d5db; }
.sv-editor { width: 100%; padding: 10px 12px; font-size: 12px;
  border: 1px solid var(--color-parchment-darker); border-radius: 6px; font-family: ui-monospace, monospace;
  line-height: 1.55; resize: vertical; background: #fffefb; }
.sv-extra summary { font-size: 11px; color: var(--color-ink-light); cursor: pointer; padding: 4px 0; }

/* 右 */
.sv-apply { display: flex; flex-direction: column; padding: 14px; gap: 12px; }
.sv-apply-group { padding: 10px; background: var(--color-surface-muted); border-radius: 6px; }
.sv-apply-title { font-size: 12px; font-weight: 600; color: var(--color-ink); margin-bottom: 6px; line-height: 1.4; }
.sv-project-name { font-size: 10px; padding: 1px 6px; border-radius: 4px; background: white; color: var(--color-ink-light); margin-left: 6px; }
.sv-apply-actions { display: flex; flex-direction: column; gap: 4px; }
.sv-apply-actions button { width: 100%; padding: 6px 10px; font-size: 11px; }
.sv-apply-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; }
.sv-apply-row button { width: 100%; padding: 5px 4px; font-size: 11px; }

/* 进阶 */
.sv-advanced { padding: 14px; }
.sv-advanced > summary { font-size: 13px; font-weight: 600; color: var(--color-ink); cursor: pointer; padding: 4px 0; }
.sv-adv-body { display: flex; flex-direction: column; gap: 16px; padding-top: 10px; }
.sv-adv-section { padding: 10px; background: var(--color-surface-muted); border-radius: 8px; display: flex; flex-direction: column; gap: 6px; }
.sv-adv-title { font-size: 13px; font-weight: 600; color: var(--color-ink); display: flex; align-items: center; gap: 6px; }
.sv-adv-row { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.sv-merge-list { display: flex; flex-wrap: wrap; gap: 6px; }
.sv-merge-chip { display: inline-flex; align-items: center; gap: 4px; padding: 3px 8px;
  background: white; border: 1px solid var(--color-parchment-darker); border-radius: 999px; font-size: 11px; cursor: pointer; }

/* 作者参考库 */
.sv-author-files { margin-top: 8px; max-height: 320px; overflow: auto; border: 1px solid var(--color-parchment-darker); border-radius: 6px; background: white; }
.sv-author-table { width: 100%; font-size: 11px; border-collapse: collapse; }
.sv-author-table th, .sv-author-table td { padding: 6px 8px; text-align: left; border-bottom: 1px solid var(--color-parchment-darker); }
.sv-author-table th { background: var(--color-surface-muted); font-weight: 600; color: var(--color-ink-light); }
.sv-author-table td { vertical-align: middle; }
.sv-cell-light { color: var(--color-ink-light); }
.sv-tag { display: inline-block; padding: 1px 5px; border-radius: 4px; background: var(--color-parchment-darker); color: var(--color-ink-light); font-size: 10px; margin-right: 3px; }
.sv-status { font-size: 10px; padding: 1px 6px; border-radius: 4px; }
.sv-status-ok { background: #dcfce7; color: #166534; }
.sv-status-indexing { background: #fef3c7; color: #92400e; }
.sv-status-error { background: #fee2e2; color: #991b1b; }
.sv-row-actions { display: flex; gap: 6px; }
.sv-row-actions button { font-size: 10px; color: var(--color-leather); background: none; border: none; padding: 0; cursor: pointer; }
.sv-row-actions button:hover { text-decoration: underline; }
.sv-row-actions .sv-row-danger { color: #dc2626; }
.sv-hits { display: flex; flex-direction: column; gap: 6px; margin-top: 6px; }
.sv-hit { padding: 8px; background: white; border: 1px solid var(--color-parchment-darker); border-radius: 6px; }
.sv-hit-meta { font-size: 10px; color: var(--color-ink-light); margin-bottom: 4px; }
.sv-hit-body { font-size: 11px; white-space: pre-wrap; margin: 0; line-height: 1.5; }
.sv-modal { position: fixed; inset: 0; z-index: 60; display: flex; align-items: center; justify-content: center; background: rgba(0, 0, 0, 0.4); }
.sv-modal-body { background: white; border-radius: 8px; box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2); width: 90%; max-width: 720px; max-height: 80vh; display: flex; flex-direction: column; padding: 14px; }
.sv-modal-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; font-weight: 600; }
.sv-modal-head button { background: none; border: none; cursor: pointer; color: var(--color-ink-light); font-size: 14px; }
.sv-modal-body pre { flex: 1; overflow: auto; padding: 8px; background: var(--color-surface-muted); border-radius: 6px; font-size: 11px; white-space: pre-wrap; margin: 0; }
</style>
