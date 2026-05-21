<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { manjuApi, postSSE, type SSEHandle } from '@/api/client'
import { useConfigStore } from '@/stores/config'
import { useProjectStore } from '@/stores/project'
import { useFeedbackStore } from '@/stores/feedback'
import { confirmDialog } from '@/stores/confirm'
import { useManjuHistory } from '@/composables/useManjuHistory'
import StreamOutput from '@/components/StreamOutput.vue'
import ManjuSteps from '@/components/manju/ManjuSteps.vue'
import PromptTemplatePreview from '@/components/manju/PromptTemplatePreview.vue'
import EnhanceDiff from '@/components/manju/EnhanceDiff.vue'
import ContinuityIssues from '@/components/manju/ContinuityIssues.vue'
import BatchToolbar from '@/components/manju/BatchToolbar.vue'
import ShotImageInline from '@/components/manju/ShotImageInline.vue'
import VersionHistory from '@/components/manju/VersionHistory.vue'

type ChapterInfo = {
  num: number
  title: string
  chars: number
  content?: string
}

type StepState = {
  running: boolean
  progress: string
  result: string
  error: string
  progressValue?: number
  sseHandle?: SSEHandle | null
}

type ManjuSettings = {
  llm_config_name: string
  start_chapter: number
  end_chapter: number
  shots_per_chapter: number
  visual_style: string
  extra_guidance: string
}

type CharacterCard = {
  id: string
  name: string
  locked: boolean
  identity?: string
  appearance?: string
  costume?: string
  prompt_positive?: string
  prompt_negative?: string
  prompt_quality_flags?: string[]
  [key: string]: unknown
}

type StoryboardShot = {
  id: string
  chapter_num: number
  shot_no: number
  locked: boolean
  subject?: string
  characters?: string
  location?: string
  light?: string
  prompt_positive?: string
  prompt_negative?: string
  prompt_quality_flags?: string[]
  continuity?: string
  image_path?: string
  image_url?: string
  image_download_url?: string
  [key: string]: unknown
}

type StyleTemplate = {
  name: string
  visual_style: string
  extra_guidance: string
}

const mkState = (): StepState => ({
  running: false,
  progress: '',
  result: '',
  error: '',
  progressValue: undefined,
  sseHandle: null,
})

const configStore = useConfigStore()
const projectStore = useProjectStore()

const llmConfig = ref('')
const file = ref<File | null>(null)
const importing = ref(false)
const importMsg = ref('')
const chapters = ref<ChapterInfo[]>([])
const meta = ref<Record<string, unknown> | null>(null)
const startChapter = ref(1)
const endChapter = ref(1)
const shotsPerChapter = ref(12)
const visualStyle = ref('国漫竖屏短剧，电影级构图，统一角色设定，高细节，适合文生图')
const extraGuidance = ref('')
const savingSettings = ref(false)
const settingsMsg = ref('')
const appliedSettings = ref<ManjuSettings | null>(null)

const characters = ref(mkState())
const scenes = ref(mkState())
const storyboards = ref(mkState())
const scriptAdapt = ref(mkState())
const characterCards = ref<CharacterCard[]>([])
const storyboardShots = ref<StoryboardShot[]>([])
const styleTemplates = ref<StyleTemplate[]>([])
const selectedStyle = ref('')
const dataMsg = ref('')
const continuityIssues = ref<Array<Record<string, unknown>>>([])
const continuityChecked = ref(false)
const statsRows = ref<Array<{ name: string; count: number }>>([])
const relationRows = ref<Array<{ source: string; target: string; count: number }>>([])
const queueRows = ref<Array<Record<string, unknown>>>([])
const generatingImageIds = ref<Set<string>>(new Set())
const selectedImageConfig = ref('')
const scriptTargetChapters = ref(12)
const scriptRenameCharacters = ref(false)
const scriptAdaptationLevel = ref('中度改编')
const scriptEpisodeDuration = ref('3-5分钟')
const scriptStyle = ref('竖屏漫剧，强钩子，快节奏，适合后续分镜和AI绘图')
const scriptGuidance = ref('')
const enhancingPrompts = ref(false)
const filepath = computed(() => projectStore.filepath)
const chapterOptions = computed(() => chapters.value.map((c) => ({ value: c.num, label: `第${c.num}章 ${c.title}` })))
const currentSettings = computed<ManjuSettings>(() => ({
  llm_config_name: llmConfig.value,
  start_chapter: startChapter.value,
  end_chapter: endChapter.value,
  shots_per_chapter: shotsPerChapter.value,
  visual_style: visualStyle.value,
  extra_guidance: extraGuidance.value,
}))
const settingsDirty = computed(() => JSON.stringify(currentSettings.value) !== JSON.stringify(appliedSettings.value))
// M10: 脚本步骤只用 scriptBody()，不需要 appliedSettings；其他下游步骤才依赖
const canRunScript = computed(() => Boolean(llmConfig.value && chapters.value.length))
const canRunDownstream = computed(() => Boolean(llmConfig.value && chapters.value.length && appliedSettings.value && !settingsDirty.value))
const canGenerate = canRunDownstream

function onFileChange(e: Event) {
  file.value = (e.target as HTMLInputElement).files?.[0] ?? null
}

async function loadStatus() {
  try {
    const res = await manjuApi.status(filepath.value)
    meta.value = res.data.meta
    chapters.value = res.data.chapters ?? []
    characters.value.result = res.data.characters ?? ''
    scriptAdapt.value.result = res.data.script ?? ''
    scenes.value.result = res.data.scenes ?? ''
    storyboards.value.result = res.data.storyboards ?? ''
    characterCards.value = res.data.character_cards ?? []
    storyboardShots.value = res.data.storyboard_shots ?? []
    styleTemplates.value = res.data.style_templates ?? []
    queueRows.value = res.data.queue ?? []
    const saved = res.data.settings as Partial<ManjuSettings> | undefined
    if (chapters.value.length) {
      startChapter.value = saved?.start_chapter ?? Math.min(startChapter.value || 1, chapters.value.length)
      endChapter.value = saved?.end_chapter ?? chapters.value.length
    }
    if (saved) {
      if (saved.llm_config_name) llmConfig.value = saved.llm_config_name
      shotsPerChapter.value = saved.shots_per_chapter ?? shotsPerChapter.value
      visualStyle.value = saved.visual_style ?? visualStyle.value
      extraGuidance.value = saved.extra_guidance ?? extraGuidance.value
      appliedSettings.value = { ...currentSettings.value }
      settingsMsg.value = ''
    }
  } catch (e: unknown) {
    feedback.error('加载漫剧状态失败', (e as Error).message)
  }
}

async function importNovel() {
  if (!file.value) return
  importing.value = true
  importMsg.value = ''
  try {
    const fd = new FormData()
    fd.append('filepath', filepath.value)
    fd.append('file', file.value)
    const res = await manjuApi.importNovel(fd)
    meta.value = res.data.meta
    chapters.value = res.data.chapters ?? []
    startChapter.value = 1
    endChapter.value = chapters.value.length || 1
    importMsg.value = res.data.message
    appliedSettings.value = null
    settingsMsg.value = '请先保存左侧设置后再生成'
    characterCards.value = []
    storyboardShots.value = []
  } catch (e: unknown) {
    importMsg.value = `❌ ${(e as Error).message}`
  } finally {
    importing.value = false
  }
}

async function saveSettings() {
  if (!chapters.value.length) {
    settingsMsg.value = '❌ 请先导入小说 TXT'
    return
  }
  if (startChapter.value > endChapter.value) {
    settingsMsg.value = '❌ 起始章节不能大于结束章节'
    return
  }
  savingSettings.value = true
  settingsMsg.value = ''
  try {
    const res = await manjuApi.saveSettings({
      filepath: filepath.value,
      ...currentSettings.value,
    })
    const saved = res.data.settings as ManjuSettings
    llmConfig.value = saved.llm_config_name || llmConfig.value
    startChapter.value = saved.start_chapter
    endChapter.value = saved.end_chapter
    shotsPerChapter.value = saved.shots_per_chapter
    visualStyle.value = saved.visual_style
    extraGuidance.value = saved.extra_guidance
    appliedSettings.value = { ...currentSettings.value }
    settingsMsg.value = res.data.message
  } catch (e: unknown) {
    settingsMsg.value = `❌ ${(e as Error).message}`
  } finally {
    savingSettings.value = false
  }
}

function runSSE(state: StepState, url: string, body: Record<string, unknown>, afterDone?: () => void | Promise<void>) {
  state.running = true
  state.progress = ''
  state.error = ''
  state.progressValue = undefined
  const refresh = () => {
    if (afterDone) void afterDone()
  }
  const handle = postSSE(
    url,
    body,
    (msg, value, content) => {
      state.progress = msg
      if (value !== undefined) state.progressValue = value
      if (content) state.result = content
    },
    (content) => {
      state.result = content || state.result
    },
    (err) => {
      state.error = err
      state.running = false
      refresh()
    },
    () => {
      state.running = false
      state.sseHandle = null
      refresh()
    },
  )
  state.sseHandle = handle
}

function commonBody() {
  const settings = appliedSettings.value ?? currentSettings.value
  return {
    llm_config_name: settings.llm_config_name,
    filepath: filepath.value,
    start_chapter: settings.start_chapter,
    end_chapter: settings.end_chapter,
    shots_per_chapter: settings.shots_per_chapter,
    visual_style: settings.visual_style,
    extra_guidance: settings.extra_guidance,
  }
}

function generateCharacters() {
  runSSE(characters.value, manjuApi.charactersUrl(), commonBody())
}

function generateScenes() {
  runSSE(scenes.value, manjuApi.scenesUrl(), commonBody(), loadStatus)
}

function generateStoryboards() {
  runSSE(storyboards.value, manjuApi.storyboardsUrl(), commonBody(), loadStatus)
}

function generateAll() {
  generateCharacters()
}

function scriptBody() {
  const settings = appliedSettings.value ?? currentSettings.value
  return {
    llm_config_name: llmConfig.value,
    filepath: filepath.value,
    start_chapter: settings.start_chapter,
    end_chapter: settings.end_chapter,
    target_chapters: scriptTargetChapters.value,
    rename_characters: scriptRenameCharacters.value,
    adaptation_level: scriptAdaptationLevel.value,
    episode_duration: scriptEpisodeDuration.value,
    script_style: scriptStyle.value,
    extra_guidance: scriptGuidance.value,
  }
}

function generateScriptAdaptation() {
  runSSE(scriptAdapt.value, manjuApi.scriptUrl(), scriptBody())
}

function exportScriptTxt() {
  window.open(manjuApi.scriptExportUrl(filepath.value), '_blank')
}

async function refreshStructuredData() {
  await loadStatus()
  feedback.success('制片数据已刷新')
}

async function saveCharacterCards() {
  const res = await manjuApi.saveCharacters({ filepath: filepath.value, characters: characterCards.value })
  characterCards.value = res.data.characters ?? characterCards.value
  feedback.success(res.data.message)
}

async function saveStoryboardShots() {
  const res = await manjuApi.saveStoryboards({ filepath: filepath.value, shots: storyboardShots.value })
  storyboardShots.value = res.data.shots ?? storyboardShots.value
  feedback.success(res.data.message)
}

function applyStyleTemplate() {
  const tpl = styleTemplates.value.find((item) => item.name === selectedStyle.value)
  if (!tpl) return
  visualStyle.value = tpl.visual_style
  extraGuidance.value = tpl.extra_guidance
}

async function saveCurrentStyle() {
  const name = selectedStyle.value || `自定义模板 ${styleTemplates.value.length + 1}`
  const res = await manjuApi.saveStyle({
    filepath: filepath.value,
    name,
    visual_style: visualStyle.value,
    extra_guidance: extraGuidance.value,
  })
  styleTemplates.value = res.data.templates ?? styleTemplates.value
  selectedStyle.value = name
  feedback.success(res.data.message)
}

function exportAssets(kind: string, format: string) {
  window.open(manjuApi.exportUrl(kind, format, filepath.value), '_blank')
}

function exportPromptContent(kind: string, format = 'md') {
  window.open(manjuApi.exportContentUrl(kind, format, filepath.value), '_blank')
}

async function importImagePrompts(kind: string) {
  dataMsg.value = '正在导入图片生成模块...'
  try {
    const res = await manjuApi.importImagePrompts({
      filepath: filepath.value,
      kind,
      replace: false,
    })
    dataMsg.value = ''
    feedback.success(res.data.message)
  } catch (e: unknown) {
    dataMsg.value = ''
    feedback.error('导入失败', (e as Error).message)
  }
}

async function enhancePrompts(kind = 'all') {
  enhancingPrompts.value = true
  dataMsg.value = '正在增强生图提示词...'
  try {
    const res = await manjuApi.enhancePrompts({
      filepath: filepath.value,
      kind,
      overwrite_locked: false,
    })
    if (res.data.characters) characterCards.value = res.data.characters
    if (res.data.storyboards) storyboardShots.value = res.data.storyboards
    dataMsg.value = ''
    feedback.success(res.data.message)
  } catch (e: unknown) {
    dataMsg.value = ''
    feedback.error('提示词增强失败', (e as Error).message)
  } finally {
    enhancingPrompts.value = false
  }
}

async function runContinuityCheck() {
  const res = await manjuApi.continuityCheck(filepath.value)
  continuityIssues.value = res.data.issues ?? []
  continuityChecked.value = true
  feedback.success(`连续性检查完成：${res.data.issue_count ?? 0} 个提示`)
}

async function loadStats() {
  const res = await manjuApi.stats(filepath.value)
  statsRows.value = res.data.appearances ?? []
  relationRows.value = res.data.relations ?? []
  feedback.success('角色统计已刷新')
}

function openImagePreview(url: string) {
  if (url) window.open(url, '_blank')
}

async function generateShotImage(shot: StoryboardShot) {
  if (!selectedImageConfig.value) {
    feedback.error('请先选择图片生成配置')
    return
  }  const next = new Set(generatingImageIds.value)
  next.add(shot.id)
  generatingImageIds.value = next
  dataMsg.value = `正在生成图片：第${shot.chapter_num}章 镜${shot.shot_no}`
  try {
    const res = await manjuApi.generateImage({
      filepath: filepath.value,
      source_type: 'shot',
      source_id: shot.id,
      image_config_name: selectedImageConfig.value,
    })
    shot.image_path = res.data.path
    shot.image_url = res.data.url
    shot.image_download_url = res.data.download_url
    shot.image_relative_path = res.data.relative_path
    dataMsg.value = ''
    feedback.success(res.data.message)
  } catch (e: unknown) {
    dataMsg.value = ''
    feedback.error('图片生成失败', (e as Error).message)
  } finally {
    const rest = new Set(generatingImageIds.value)
    rest.delete(shot.id)
    generatingImageIds.value = rest
  }
}

async function regenerateShot(shot: StoryboardShot) {
  if (shot.locked) return
  dataMsg.value = `正在重写分镜：第${shot.chapter_num}章 镜${shot.shot_no}`
  try {
    const res = await manjuApi.regenerateShot({
      filepath: filepath.value,
      llm_config_name: llmConfig.value,
      shot_id: shot.id,
      visual_style: visualStyle.value,
      extra_guidance: extraGuidance.value,
    })
    const updated = res.data.shot as StoryboardShot
    const idx = storyboardShots.value.findIndex((item) => item.id === updated.id)
    if (idx >= 0) storyboardShots.value[idx] = updated
    dataMsg.value = ''
    feedback.success(res.data.message)
  } catch (e) {
    dataMsg.value = ''
    feedback.error('重写分镜失败', (e as Error).message)
  }
}

function stopSSE(state: StepState) {
  state.sseHandle?.abort()
  state.sseHandle = null
  state.running = false
  state.progress = '已停止'
}

async function createQueue() {
  const settings = appliedSettings.value ?? currentSettings.value
  const res = await manjuApi.createQueue({
    filepath: filepath.value,
    start_chapter: settings.start_chapter,
    end_chapter: settings.end_chapter,
    chunk_size: 5,
  })
  queueRows.value = res.data.queue ?? []
  feedback.success(res.data.message)
}

async function updateQueue(batchId: string, status: string) {
  const res = await manjuApi.updateQueue(batchId, filepath.value, status)
  queueRows.value = res.data.queue ?? []
  feedback.success(res.data.message)
}

onMounted(async () => {
  await Promise.all([configStore.loadAll(), projectStore.loadActive()])
  if (configStore.llmChoices.length) llmConfig.value = configStore.llmChoices[0]
  if (configStore.imageChoices.length) selectedImageConfig.value = configStore.imageChoices[0]
  await loadStatus()
})

watch([llmConfig, startChapter, endChapter, shotsPerChapter, visualStyle, extraGuidance], () => {
  if (appliedSettings.value && settingsDirty.value) settingsMsg.value = '设置已修改，请点击保存设置后再生成'
})

watch(() => configStore.llmChoices.slice(), (choices) => {
  if (!choices.length) {
    llmConfig.value = ''
    return
  }
  if (!llmConfig.value || !choices.includes(llmConfig.value)) {
    llmConfig.value = choices[0]
  }
})

watch(() => configStore.imageChoices.slice(), (choices) => {
  if (!choices.length) {
    selectedImageConfig.value = ''
    return
  }
  if (!selectedImageConfig.value || !choices.includes(selectedImageConfig.value)) {
    selectedImageConfig.value = choices[0]
  }
})

// ── 增量功能：步骤导航 / 批量选择 / 增强对比 / 版本历史 ─────────────────────
const feedback = useFeedbackStore()
const history = useManjuHistory()

const stepAnchors: Record<string, string> = {
  import: 'manju-import', script: 'manju-script', characters: 'manju-characters',
  scenes: 'manju-scenes', storyboards: 'manju-storyboards', images: 'manju-storyboards',
  export: 'manju-export',
}

function gotoStep(key: string) {
  const id = stepAnchors[key]
  if (id) document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const hasImages = computed(() => storyboardShots.value.some((s) => s.image_url || s.image_path))

// 选择
const selectedCharIds = ref<string[]>([])
const selectedShotIds = ref<string[]>([])

function toggleCharSel(id: string) {
  const i = selectedCharIds.value.indexOf(id)
  if (i >= 0) selectedCharIds.value.splice(i, 1)
  else selectedCharIds.value.push(id)
}
function toggleShotSel(id: string) {
  const i = selectedShotIds.value.indexOf(id)
  if (i >= 0) selectedShotIds.value.splice(i, 1)
  else selectedShotIds.value.push(id)
}

async function bulkCharLock(lock: boolean) {
  let n = 0
  for (const c of characterCards.value) {
    if (selectedCharIds.value.includes(c.id)) { c.locked = lock; n++ }
  }
  await saveCharacterCards()
  feedback.success(`已${lock ? '锁定' : '解锁'} ${n} 个角色`)
}
async function bulkCharDelete() {
  if (!(await confirmDialog(`删除 ${selectedCharIds.value.length} 个角色？`))) return
  const before = JSON.parse(JSON.stringify(characterCards.value))
  characterCards.value = characterCards.value.filter((c) => !selectedCharIds.value.includes(c.id))
  await saveCharacterCards()
  feedback.success('已删除', { undoFn: async () => { characterCards.value = before; await saveCharacterCards() } })
  selectedCharIds.value = []
}

async function bulkShotLock(lock: boolean) {
  let n = 0
  for (const s of storyboardShots.value) {
    if (selectedShotIds.value.includes(s.id)) { s.locked = lock; n++ }
  }
  await saveStoryboardShots()
  feedback.success(`已${lock ? '锁定' : '解锁'} ${n} 个分镜`)
}
async function bulkShotDelete() {
  if (!(await confirmDialog(`删除 ${selectedShotIds.value.length} 个分镜？`))) return
  const before = JSON.parse(JSON.stringify(storyboardShots.value))
  storyboardShots.value = storyboardShots.value.filter((s) => !selectedShotIds.value.includes(s.id))
  await saveStoryboardShots()
  feedback.success('已删除', { undoFn: async () => { storyboardShots.value = before; await saveStoryboardShots() } })
  selectedShotIds.value = []
}
async function bulkShotRegenerate() {
  let ok = 0
  for (const s of storyboardShots.value) {
    if (selectedShotIds.value.includes(s.id) && !s.locked) {
      try { await regenerateShot(s); ok++ } catch { /* ignore */ }
    }
  }
  feedback.success(`已重生成 ${ok} 个分镜`)
}
async function bulkShotImportToQueue() {
  try {
    const res = await manjuApi.importImagePrompts({
      filepath: filepath.value, kind: 'storyboards', replace: false,
      shot_ids: selectedShotIds.value,
    })
    feedback.success(res.data.message ?? '已导入图片队列')
  } catch (e) {
    feedback.error('导入图片队列失败', (e as Error).message)
  }
}

// 增强对比
interface PromptPair { id: string; label: string; before: string; after: string }
const enhanceDiff = ref<PromptPair[]>([])
const enhanceBefore = ref<{ characters: CharacterCard[]; storyboards: StoryboardShot[] } | null>(null)

async function enhancePromptsWithDiff(kind = 'all') {
  enhancingPrompts.value = true
  enhanceBefore.value = {
    characters: JSON.parse(JSON.stringify(characterCards.value)),
    storyboards: JSON.parse(JSON.stringify(storyboardShots.value)),
  }
  dataMsg.value = '正在增强生图提示词...'
  try {
    const res = await manjuApi.enhancePrompts({ filepath: filepath.value, kind, overwrite_locked: false })
    const newChars = (res.data.characters ?? characterCards.value) as CharacterCard[]
    const newShots = (res.data.storyboards ?? storyboardShots.value) as StoryboardShot[]
    const pairs: PromptPair[] = []
    if (kind !== 'storyboards') {
      for (const before of enhanceBefore.value.characters) {
        const after = newChars.find((c) => c.id === before.id)
        if (after) pairs.push({ id: `c:${before.id}`, label: `角色 · ${before.name}`, before: String(before.prompt_positive || ''), after: String(after.prompt_positive || '') })
      }
    }
    if (kind !== 'characters') {
      for (const before of enhanceBefore.value.storyboards) {
        const after = newShots.find((s) => s.id === before.id)
        if (after) pairs.push({ id: `s:${before.id}`, label: `分镜 · 第${before.chapter_num}章·镜${before.shot_no}`, before: String(before.prompt_positive || ''), after: String(after.prompt_positive || '') })
      }
    }
    enhanceDiff.value = pairs.filter((p) => p.before !== p.after)
    characterCards.value = newChars
    storyboardShots.value = newShots
    dataMsg.value = ''
    feedback.success(`增强完成：${enhanceDiff.value.length} 条变化，可逐条选择应用`)
  } catch (e) {
    feedback.error('提示词增强失败', (e as Error).message)
  } finally {
    enhancingPrompts.value = false
  }
}

function revertOne(id: string) {
  if (!enhanceBefore.value) return
  if (id.startsWith('c:')) {
    const before = enhanceBefore.value.characters.find((c) => `c:${c.id}` === id)
    const idx = characterCards.value.findIndex((c) => `c:${c.id}` === id)
    if (before && idx >= 0) characterCards.value[idx] = JSON.parse(JSON.stringify(before))
  } else {
    const before = enhanceBefore.value.storyboards.find((s) => `s:${s.id}` === id)
    const idx = storyboardShots.value.findIndex((s) => `s:${s.id}` === id)
    if (before && idx >= 0) storyboardShots.value[idx] = JSON.parse(JSON.stringify(before))
  }
  enhanceDiff.value = enhanceDiff.value.filter((p) => p.id !== id)
}

async function revertAllEnhance() {
  if (!enhanceBefore.value) return
  characterCards.value = enhanceBefore.value.characters
  storyboardShots.value = enhanceBefore.value.storyboards
  enhanceDiff.value = []
  await saveCharacterCards(); await saveStoryboardShots()
  feedback.info('已全部还原')
}

async function applyAllEnhance() {
  await saveCharacterCards(); await saveStoryboardShots()
  enhanceDiff.value = []
  feedback.success('增强结果已全部应用并保存')
}

function applyOne(id: string) {
  enhanceDiff.value = enhanceDiff.value.filter((p) => p.id !== id)
  // characters/storyboards already mutated; save to persist
  if (id.startsWith('c:')) saveCharacterCards()
  else saveStoryboardShots()
}

// 跳转到分镜
function jumpToShot(shotId: string) {
  const el = document.getElementById(`shot-${shotId}`)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    el.classList.add('shot-highlight')
    setTimeout(() => el.classList.remove('shot-highlight'), 2000)
  }
}

// 历史快照
const scriptHistory = history.list('script')
const charactersHistory = history.list('characters')
const storyboardsHistory = history.list('storyboards')
const scenesHistory = history.list('scenes')

function snapshotScript() { if (scriptAdapt.value.result) history.snapshot('script', scriptAdapt.value.result) }
function snapshotCharacters() { if (characterCards.value.length) history.snapshot('characters', JSON.parse(JSON.stringify(characterCards.value))) }
function snapshotStoryboards() { if (storyboardShots.value.length) history.snapshot('storyboards', JSON.parse(JSON.stringify(storyboardShots.value))) }
function snapshotScenes() { if (scenes.value.result) history.snapshot('scenes', scenes.value.result) }

async function restoreSnap(kind: 'script' | 'characters' | 'storyboards' | 'scenes', snap: { payload: unknown }) {
  if (kind === 'script' && typeof snap.payload === 'string') { scriptAdapt.value.result = snap.payload; feedback.success('剧本已回滚') }
  else if (kind === 'characters' && Array.isArray(snap.payload)) { characterCards.value = snap.payload as CharacterCard[]; await saveCharacterCards(); feedback.success('角色已回滚') }
  else if (kind === 'storyboards' && Array.isArray(snap.payload)) { storyboardShots.value = snap.payload as StoryboardShot[]; await saveStoryboardShots(); feedback.success('分镜已回滚') }
  else if (kind === 'scenes' && typeof snap.payload === 'string') { scenes.value.result = snap.payload; feedback.success('场景已回滚') }
}

// 在每次成功保存/生成结束后自动入栈
watch(() => scriptAdapt.value.running, (running, prev) => {
  if (prev && !running && scriptAdapt.value.result && !scriptAdapt.value.error) snapshotScript()
})
watch(() => scenes.value.running, (running, prev) => {
  if (prev && !running && scenes.value.result && !scenes.value.error) snapshotScenes()
})
watch(() => storyboards.value.running, (running, prev) => {
  if (prev && !running && storyboardShots.value.length && !storyboards.value.error) snapshotStoryboards()
})
watch(() => characters.value.running, (running, prev) => {
  if (prev && !running && characterCards.value.length && !characters.value.error) snapshotCharacters()
})
</script>

<template>
  <div class="module-page space-y-5">
    <div class="module-toolbar">
      <h2 class="text-2xl font-bold" style="color: var(--color-ink)">🎬 漫剧制作</h2>
      <div>
        <div class="module-kicker">Comic Studio</div>
        <div class="module-subtitle">小说导入、剧本改编、角色卡、场景图与分镜提示词的一体化制片台。</div>
      </div>
      <button
        @click="loadStatus"
        class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm hover:bg-white transition-colors"
        type="button"
      >
        刷新
      </button>
    </div>

    <ManjuSteps
      :has-import="chapters.length > 0"
      :has-script="Boolean(scriptAdapt.result)"
      :has-characters="characterCards.length > 0"
      :has-scenes="Boolean(scenes.result)"
      :has-storyboards="storyboardShots.length > 0"
      :has-images="hasImages"
      @goto="gotoStep"
    />

    <div id="manju-import" class="manju-anchor"></div>

    <div class="module-grid wide-aside">
      <aside class="space-y-4 module-aside-sticky">
        <section class="module-panel p-4 space-y-4">
          <div>
            <div class="module-panel-title">输入与模型</div>
            <div class="module-panel-caption">先选择模型并导入 TXT，生成章节目录后进入后续流程。</div>
          </div>
          <div>
            <label class="block text-xs text-[var(--color-ink-light)] mb-1">LLM 配置</label>
            <select v-model="llmConfig" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm">
              <option v-for="c in configStore.llmChoices" :key="c" :value="c">{{ c }}</option>
            </select>
          </div>

          <div>
            <label class="block text-xs text-[var(--color-ink-light)] mb-1">导入小说 TXT</label>
            <input
              type="file"
              accept=".txt,text/plain"
              @change="onFileChange"
              class="text-sm text-[var(--color-ink)] file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:font-medium file:cursor-pointer"
            />
          </div>
          <button
            @click="importNovel"
            :disabled="importing || !file"
            class="w-full px-4 py-2 rounded-md text-sm font-semibold disabled:opacity-50"
            style="background-color: var(--color-leather); color: var(--color-parchment)"
            type="button"
          >
            {{ importing ? '导入中...' : '解析章节目录' }}
          </button>
          <div v-if="importMsg" class="text-sm" :class="importMsg.startsWith('❌') ? 'text-red-600' : 'text-green-700'">
            {{ importMsg }}
          </div>
          <div v-if="meta" class="text-xs text-[var(--color-ink-light)] leading-6">
            <div>章节数：{{ meta.chapter_count }}</div>
            <div>总字数：{{ meta.total_chars }}</div>
            <div>文件：{{ meta.filename }}</div>
          </div>
        </section>

        <section class="module-panel p-4 space-y-4">
          <div>
            <div class="module-panel-title">范围与视觉约束</div>
            <div class="module-panel-caption">控制章节范围、镜头数量和全局画面风格。</div>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs text-[var(--color-ink-light)] mb-1">起始章节</label>
              <select v-model.number="startChapter" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm">
                <option v-for="c in chapterOptions" :key="c.value" :value="c.value">{{ c.label }}</option>
              </select>
            </div>
            <div>
              <label class="block text-xs text-[var(--color-ink-light)] mb-1">结束章节</label>
              <select v-model.number="endChapter" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm">
                <option v-for="c in chapterOptions" :key="c.value" :value="c.value">{{ c.label }}</option>
              </select>
            </div>
          </div>
          <div>
            <label class="block text-xs text-[var(--color-ink-light)] mb-1">每章分镜数</label>
            <input v-model.number="shotsPerChapter" type="number" min="1" max="80" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm" />
          </div>
          <div class="grid grid-cols-[1fr_auto] gap-2 items-end">
            <div>
              <label class="block text-xs text-[var(--color-ink-light)] mb-1">美术风格模板</label>
              <select v-model="selectedStyle" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm">
                <option value="">选择模板</option>
                <option v-for="tpl in styleTemplates" :key="tpl.name" :value="tpl.name">{{ tpl.name }}</option>
              </select>
            </div>
            <button @click="applyStyleTemplate" :disabled="!selectedStyle" class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm disabled:opacity-50" type="button">应用</button>
          </div>
          <div>
            <label class="block text-xs text-[var(--color-ink-light)] mb-1">统一视觉风格</label>
            <textarea v-model="visualStyle" rows="3" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm resize-y" />
          </div>
          <div>
            <label class="block text-xs text-[var(--color-ink-light)] mb-1">补充要求</label>
            <textarea v-model="extraGuidance" rows="3" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm resize-y" />
          </div>
          <button
            @click="saveSettings"
            :disabled="savingSettings || !chapters.length || startChapter > endChapter"
            class="w-full px-4 py-2 rounded-md text-sm font-semibold disabled:opacity-50"
            style="background-color: var(--color-leather); color: var(--color-parchment)"
            type="button"
          >
            {{ savingSettings ? '保存中...' : '保存设置' }}
          </button>
          <button
            @click="saveCurrentStyle"
            :disabled="!visualStyle"
            class="w-full px-4 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm font-semibold disabled:opacity-50"
            type="button"
          >
            保存为风格模板
          </button>
          <div v-if="settingsMsg" class="text-sm" :class="settingsMsg.startsWith('❌') ? 'text-red-600' : 'text-green-700'">
            {{ settingsMsg }}
          </div>
          <div v-if="appliedSettings" class="text-xs text-[var(--color-ink-light)] leading-6">
            已保存范围：第{{ appliedSettings.start_chapter }}章 - 第{{ appliedSettings.end_chapter }}章；
            每章 {{ appliedSettings.shots_per_chapter }} 镜
          </div>
        </section>

        <section class="module-panel p-4">
          <div class="module-panel-title mb-3">章节目录</div>
          <div class="max-h-80 overflow-auto module-list pr-1">
            <div v-for="ch in chapters" :key="ch.num" class="module-list-item px-3 py-2 text-sm">
              <div class="font-medium text-[var(--color-ink)]">第{{ ch.num }}章 {{ ch.title }}</div>
              <div class="text-xs text-[var(--color-ink-light)]">{{ ch.chars }} 字</div>
            </div>
            <div v-if="!chapters.length" class="text-sm text-[var(--color-ink-light)]">暂无章节</div>
          </div>
        </section>
      </aside>

      <main class="space-y-5">
        <section class="module-panel space-y-4 overflow-hidden" id="manju-script">
          <div class="module-panel-header">
            <div>
              <h3 class="module-panel-title">小说改编漫剧剧本</h3>
              <p class="module-panel-caption">将原文重构为更适合短剧节奏的章节脚本。</p>
            </div>
            <div class="module-action-row">
              <button
                @click="generateScriptAdaptation"
                :disabled="scriptAdapt.running || !canRunScript"
                class="px-4 py-2 rounded-md text-sm font-semibold disabled:opacity-50"
                style="background-color: var(--color-leather); color: var(--color-parchment)"
                type="button"
              >
                {{ scriptAdapt.running ? '改编中...' : '生成漫剧剧本' }}
              </button>
              <button v-if="scriptAdapt.running" @click="stopSSE(scriptAdapt)" class="px-3 py-2 rounded-md text-xs bg-red-600 text-white hover:bg-red-700" type="button">停止</button>
              <button
                @click="exportScriptTxt"
                :disabled="!scriptAdapt.result"
                class="px-4 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm font-semibold disabled:opacity-50"
                type="button"
              >
                导出 TXT
              </button>
            </div>
          </div>

          <div class="px-4 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
            <div>
              <label class="block text-xs text-[var(--color-ink-light)] mb-1">改编章节数</label>
              <input v-model.number="scriptTargetChapters" type="number" min="1" max="120" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm" />
            </div>
            <div>
              <label class="block text-xs text-[var(--color-ink-light)] mb-1">剧情改编幅度</label>
              <select v-model="scriptAdaptationLevel" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm">
                <option>轻度改编</option>
                <option>中度改编</option>
                <option>重度改编</option>
                <option>魔改爽剧化</option>
              </select>
            </div>
            <div>
              <label class="block text-xs text-[var(--color-ink-light)] mb-1">单章时长</label>
              <input v-model="scriptEpisodeDuration" placeholder="3-5分钟" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm" />
            </div>
            <label class="flex items-center gap-2 text-sm pt-6">
              <input v-model="scriptRenameCharacters" type="checkbox" />
              允许修改人物名称
            </label>
          </div>

          <div class="px-4">
            <label class="block text-xs text-[var(--color-ink-light)] mb-1">剧本风格</label>
            <textarea v-model="scriptStyle" rows="2" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm resize-y" />
          </div>
          <div class="px-4">
            <label class="block text-xs text-[var(--color-ink-light)] mb-1">剧本改编补充要求</label>
            <textarea v-model="scriptGuidance" rows="2" placeholder="例如：加强女主戏份、弱化支线、每章结尾必须反转..." class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm resize-y" />
          </div>

          <div class="px-4 pb-4">
            <StreamOutput v-bind="scriptAdapt" placeholder="改编后的漫剧剧本将在此显示，可导出 TXT..." />
          </div>
        </section>

        <section class="module-panel space-y-3 overflow-hidden" id="manju-characters">
          <div class="module-panel-header">
            <div>
              <h3 class="module-panel-title">角色信息与角色卡提示词</h3>
              <p class="module-panel-caption">沉淀角色设定与单张全身角色图提示词。</p>
              <PromptTemplatePreview kind="character" :visual-style="visualStyle" :extra-guidance="extraGuidance" />
            </div>
            <div class="module-action-row">
              <button @click="exportPromptContent('characters', 'md')" :disabled="!characters.result" class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm disabled:opacity-50" type="button">导出 MD</button>
              <button @click="exportPromptContent('characters', 'txt')" :disabled="!characters.result" class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm disabled:opacity-50" type="button">导出 TXT</button>
              <button @click="importImagePrompts('characters')" :disabled="!characters.result" class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm disabled:opacity-50" type="button">导入生图</button>
              <button
                @click="generateCharacters"
                :disabled="characters.running || !canGenerate"
                class="px-4 py-2 rounded-md text-sm font-semibold disabled:opacity-50"
                style="background-color: var(--color-leather); color: var(--color-parchment)"
                type="button"
              >
                {{ characters.running ? '生成中...' : '生成角色卡' }}
              </button>
              <button v-if="characters.running" @click="stopSSE(characters)" class="px-3 py-2 rounded-md text-xs bg-red-600 text-white hover:bg-red-700" type="button">停止</button>
            </div>
          </div>
          <div class="p-4 pt-0">
            <StreamOutput v-bind="characters" placeholder="角色信息、外貌设定和角色卡提示词将在此显示..." />
          </div>
        </section>

        <section class="module-panel space-y-3 overflow-hidden" id="manju-scenes">
          <div class="module-panel-header">
            <div>
              <h3 class="module-panel-title">章节场景图提示词</h3>
              <p class="module-panel-caption">为章节主场景生成稳定的环境、氛围和构图描述。</p>
              <PromptTemplatePreview kind="scene" :visual-style="visualStyle" :extra-guidance="extraGuidance" />
            </div>
            <div class="module-action-row">
              <button @click="exportPromptContent('scenes', 'md')" :disabled="!scenes.result" class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm disabled:opacity-50" type="button">导出 MD</button>
              <button @click="exportPromptContent('scenes', 'txt')" :disabled="!scenes.result" class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm disabled:opacity-50" type="button">导出 TXT</button>
              <button @click="importImagePrompts('scenes')" :disabled="!scenes.result" class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm disabled:opacity-50" type="button">导入生图</button>
              <button
                @click="generateScenes"
                :disabled="scenes.running || !canGenerate"
                class="px-4 py-2 rounded-md text-sm font-semibold disabled:opacity-50"
                style="background-color: var(--color-leather); color: var(--color-parchment)"
                type="button"
              >
                {{ scenes.running ? '生成中...' : '生成场景提示词' }}
              </button>
              <button v-if="scenes.running" @click="stopSSE(scenes)" class="px-3 py-2 rounded-md text-xs bg-red-600 text-white hover:bg-red-700" type="button">停止</button>
            </div>
          </div>
          <div class="p-4 pt-0">
            <StreamOutput v-bind="scenes" placeholder="每章关键场景、镜头氛围和文生图提示词将在此显示..." />
          </div>
        </section>

        <section class="module-panel space-y-3 overflow-hidden" id="manju-storyboards">
          <div class="module-panel-header">
            <div>
              <h3 class="module-panel-title">章节分镜图提示词</h3>
              <p class="module-panel-caption">按镜头拆解主体、景别、动作和连续性。</p>
              <PromptTemplatePreview kind="storyboard" :visual-style="visualStyle" :extra-guidance="extraGuidance" />
            </div>
            <div class="module-action-row">
              <button @click="exportPromptContent('storyboards', 'md')" :disabled="!storyboards.result" class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm disabled:opacity-50" type="button">导出 MD</button>
              <button @click="exportPromptContent('storyboards', 'txt')" :disabled="!storyboards.result" class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm disabled:opacity-50" type="button">导出 TXT</button>
              <button @click="importImagePrompts('storyboards')" :disabled="!storyboards.result" class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm disabled:opacity-50" type="button">导入生图</button>
              <button
                @click="generateStoryboards"
                :disabled="storyboards.running || !canGenerate"
                class="px-4 py-2 rounded-md text-sm font-semibold disabled:opacity-50"
                style="background-color: var(--color-leather); color: var(--color-parchment)"
                type="button"
              >
                {{ storyboards.running ? '生成中...' : '生成分镜提示词' }}
              </button>
              <button v-if="storyboards.running" @click="stopSSE(storyboards)" class="px-3 py-2 rounded-md text-xs bg-red-600 text-white hover:bg-red-700" type="button">停止</button>
            </div>
          </div>
          <div class="p-4 pt-0">
            <StreamOutput v-bind="storyboards" placeholder="按用户指定数量生成的连续分镜图提示词将在此显示..." />
          </div>
        </section>

        <section class="module-panel space-y-4 overflow-hidden">
          <div class="module-panel-header">
            <div>
              <h3 class="module-panel-title">制片数据与连续性</h3>
              <p class="module-panel-caption">编辑角色锁定、分镜表、队列和一致性检查结果。</p>
            </div>
            <div class="module-action-row">
              <button @click="refreshStructuredData" class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm" type="button">刷新数据</button>
              <button @click="runContinuityCheck" class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm" type="button">连续性检查</button>
              <button @click="loadStats" class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm" type="button">出场统计</button>
              <button @click="createQueue" class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm" type="button">创建批量队列</button>
              <button
                @click="enhancePromptsWithDiff('all')"
                :disabled="enhancingPrompts || (!characterCards.length && !storyboardShots.length)"
                class="px-3 py-2 rounded-md border border-[var(--color-leather)] text-[var(--color-leather)] text-sm disabled:opacity-50"
                type="button"
              >
                {{ enhancingPrompts ? '增强中...' : '增强全部提示词（对比模式）' }}
              </button>
            </div>
          </div>

          <EnhanceDiff
            v-if="enhanceDiff.length"
            :pairs="enhanceDiff"
            @apply="applyOne"
            @revert="revertOne"
            @apply-all="applyAllEnhance"
            @revert-all="revertAllEnhance"
          />
          <div
            v-if="dataMsg"
            class="mx-4 text-sm module-status"
            :class="dataMsg.startsWith('✅') ? 'text-green-700' : dataMsg.startsWith('❌') ? 'text-red-600' : 'text-[var(--color-ink-light)]'"
          >
            {{ dataMsg }}
          </div>

          <div id="manju-export" class="px-4 module-action-row">
            <button @click="exportAssets('characters', 'json')" class="px-3 py-1.5 rounded border border-[var(--color-parchment-darker)] text-sm" type="button">角色 JSON</button>
            <button @click="exportAssets('storyboards', 'csv')" class="px-3 py-1.5 rounded border border-[var(--color-parchment-darker)] text-sm" type="button">分镜 CSV</button>
            <button @click="exportAssets('storyboards', 'xlsx')" class="px-3 py-1.5 rounded border border-[var(--color-parchment-darker)] text-sm" type="button">分镜 Excel</button>
            <button @click="exportAssets('all', 'json')" class="px-3 py-1.5 rounded border border-[var(--color-parchment-darker)] text-sm" type="button">全部 JSON</button>
            <button @click="enhancePromptsWithDiff('characters')" :disabled="enhancingPrompts || !characterCards.length" class="px-3 py-1.5 rounded border border-[var(--color-parchment-darker)] text-sm disabled:opacity-50" type="button">增强角色提示词</button>
            <button @click="enhancePromptsWithDiff('storyboards')" :disabled="enhancingPrompts || !storyboardShots.length" class="px-3 py-1.5 rounded border border-[var(--color-parchment-darker)] text-sm disabled:opacity-50" type="button">增强分镜提示词</button>
            <button @click="importImagePrompts('all')" class="px-3 py-1.5 rounded border border-[var(--color-parchment-darker)] text-sm" type="button">全部导入生图</button>
          </div>

          <div class="px-4">
            <div class="flex items-center justify-between mb-2">
              <h4 class="text-sm font-semibold text-[var(--color-ink)]">角色一致性锁定</h4>
              <button @click="saveCharacterCards" class="px-3 py-1.5 rounded border border-[var(--color-parchment-darker)] text-sm" type="button">保存角色锁定</button>
            </div>
            <BatchToolbar
              :total="characterCards.length"
              :selected="selectedCharIds"
              @select-all="selectedCharIds = characterCards.map(c => c.id)"
              @clear="selectedCharIds = []"
              @lock="bulkCharLock(true)"
              @unlock="bulkCharLock(false)"
              @delete="bulkCharDelete"
            />
            <VersionHistory kind="characters" label="角色" :list="charactersHistory" @restore="snap => restoreSnap('characters', snap)" @remove="ts => history.remove('characters', ts)" />
            <div class="data-table-shell max-h-96">
              <table class="min-w-[1020px] w-full text-xs">
                <thead class="bg-[var(--color-parchment)] sticky top-0">
                  <tr>
                    <th class="p-2 text-left w-10"><input type="checkbox" :checked="selectedCharIds.length === characterCards.length && characterCards.length > 0" @change="selectedCharIds = ($event.target as HTMLInputElement).checked ? characterCards.map(c => c.id) : []" /></th>
                    <th class="p-2 text-left w-16">锁定</th>
                    <th class="p-2 text-left w-28">角色</th>
                    <th class="p-2 text-left w-36">身份</th>
                    <th class="p-2 text-left">外貌</th>
                    <th class="p-2 text-left">服装</th>
                    <th class="p-2 text-left">角色卡提示词</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="card in characterCards" :key="card.id" class="border-t border-[var(--color-parchment)] align-top">
                    <td class="p-2"><input type="checkbox" :checked="selectedCharIds.includes(card.id)" @change="toggleCharSel(card.id)" /></td>
                    <td class="p-2"><input v-model="card.locked" type="checkbox" /></td>
                    <td class="p-2"><input v-model="card.name" class="w-full border rounded px-2 py-1" /></td>
                    <td class="p-2"><textarea v-model="card.identity" rows="3" class="w-full border rounded px-2 py-1 resize-y" /></td>
                    <td class="p-2"><textarea v-model="card.appearance" rows="3" class="w-full border rounded px-2 py-1 resize-y" /></td>
                    <td class="p-2"><textarea v-model="card.costume" rows="3" class="w-full border rounded px-2 py-1 resize-y" /></td>
                    <td class="p-2">
                      <textarea v-model="card.prompt_positive" rows="3" class="w-full border rounded px-2 py-1 resize-y" />
                      <div v-if="card.prompt_quality_flags?.length" class="mt-1 text-[10px] text-amber-700">
                        {{ card.prompt_quality_flags.join(' / ') }}
                      </div>
                    </td>
                  </tr>
                  <tr v-if="!characterCards.length"><td colspan="7" class="p-3 text-[var(--color-ink-light)]">暂无结构化角色卡，生成角色卡后点击刷新数据。</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="px-4">
            <div class="flex items-center justify-between mb-2">
              <h4 class="text-sm font-semibold text-[var(--color-ink)]">分镜表格编辑器</h4>
              <button @click="saveStoryboardShots" class="px-3 py-1.5 rounded border border-[var(--color-parchment-darker)] text-sm" type="button">保存分镜表</button>
            </div>
            <BatchToolbar
              :total="storyboardShots.length"
              :selected="selectedShotIds"
              :show-regenerate="true"
              :show-queue-import="true"
              @select-all="selectedShotIds = storyboardShots.map(s => s.id)"
              @clear="selectedShotIds = []"
              @lock="bulkShotLock(true)"
              @unlock="bulkShotLock(false)"
              @delete="bulkShotDelete"
              @regenerate="bulkShotRegenerate"
              @queue-import="bulkShotImportToQueue"
            />
            <VersionHistory kind="storyboards" label="分镜" :list="storyboardsHistory" @restore="snap => restoreSnap('storyboards', snap)" @remove="ts => history.remove('storyboards', ts)" />
            <div class="data-table-shell max-h-[520px]">
              <table class="min-w-[1220px] w-full text-xs">
                <thead class="bg-[var(--color-parchment)] sticky top-0">
                  <tr>
                    <th class="p-2 text-left w-10"><input type="checkbox" :checked="selectedShotIds.length === storyboardShots.length && storyboardShots.length > 0" @change="selectedShotIds = ($event.target as HTMLInputElement).checked ? storyboardShots.map(s => s.id) : []" /></th>
                    <th class="p-2 text-left w-16">锁定</th>
                    <th class="p-2 text-left w-20">章节</th>
                    <th class="p-2 text-left w-16">镜号</th>
                    <th class="p-2 text-left w-36">主体</th>
                    <th class="p-2 text-left w-32">角色</th>
                    <th class="p-2 text-left w-36">地点</th>
                    <th class="p-2 text-left">正向提示词</th>
                    <th class="p-2 text-left w-44">连续性</th>
                    <th class="p-2 text-left w-28">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="shot in storyboardShots" :key="shot.id" :id="`shot-${shot.id}`" class="border-t border-[var(--color-parchment)] align-top">
                    <td class="p-2"><input type="checkbox" :checked="selectedShotIds.includes(shot.id)" @change="toggleShotSel(shot.id)" /></td>
                    <td class="p-2"><input v-model="shot.locked" type="checkbox" /></td>
                    <td class="p-2">第{{ shot.chapter_num }}章</td>
                    <td class="p-2">{{ shot.shot_no }}</td>
                    <td class="p-2"><textarea v-model="shot.subject" rows="3" class="w-full border rounded px-2 py-1 resize-y" /></td>
                    <td class="p-2"><textarea v-model="shot.characters" rows="3" class="w-full border rounded px-2 py-1 resize-y" /></td>
                    <td class="p-2"><textarea v-model="shot.location" rows="3" class="w-full border rounded px-2 py-1 resize-y" /></td>
                    <td class="p-2">
                      <textarea v-model="shot.prompt_positive" rows="3" class="w-full border rounded px-2 py-1 resize-y" />
                      <div v-if="shot.prompt_quality_flags?.length" class="mt-1 text-[10px] text-amber-700">
                        {{ shot.prompt_quality_flags.join(' / ') }}
                      </div>
                    </td>
                    <td class="p-2"><textarea v-model="shot.continuity" rows="3" class="w-full border rounded px-2 py-1 resize-y" /></td>
                    <td class="p-2">
                      <div class="flex flex-col gap-1">
                        <button @click="regenerateShot(shot)" :disabled="shot.locked || !llmConfig" class="px-2 py-1 rounded border border-[var(--color-parchment-darker)] disabled:opacity-50" type="button">重写</button>
                        <ShotImageInline
                          :shot="shot"
                          :image-configs="configStore.imageChoices"
                          :image-config="selectedImageConfig"
                          :generating="generatingImageIds.has(shot.id)"
                          @update:image-config="selectedImageConfig = $event"
                          @generate="generateShotImage($event as StoryboardShot)"
                          @preview="openImagePreview"
                        />
                      </div>
                    </td>
                  </tr>
                  <tr v-if="!storyboardShots.length"><td colspan="10" class="p-3 text-[var(--color-ink-light)]">暂无结构化分镜，生成分镜后点击刷新数据。</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="px-4 pb-4 grid grid-cols-1 xl:grid-cols-2 gap-4">
            <div class="module-status">
              <h4 class="text-sm font-semibold text-[var(--color-ink)] mb-2">分镜生图</h4>
              <div class="grid grid-cols-1 gap-2 text-sm">
                <select v-model="selectedImageConfig" class="border rounded px-2 py-1">
                  <option value="">请选择图片生成配置</option>
                  <option v-for="c in configStore.imageChoices" :key="c" :value="c">{{ c }}</option>
                </select>
              </div>
              <div class="mt-2 text-xs text-[var(--color-ink-light)]">
                图片接口已移到模型配置；本模块只选择配置并对单个分镜生图。
              </div>
              <div class="mt-2 flex gap-2">
                <router-link to="/config" class="px-3 py-1.5 rounded border border-[var(--color-parchment-darker)] text-sm">管理配置</router-link>
                <router-link to="/images" class="px-3 py-1.5 rounded border border-[var(--color-parchment-darker)] text-sm">打开图片生成模块</router-link>
              </div>
            </div>

            <div class="module-status">
              <h4 class="text-sm font-semibold text-[var(--color-ink)] mb-2">检查/统计/队列</h4>
              <ContinuityIssues
                :issues="continuityIssues"
                :shots="storyboardShots"
                :has-run="continuityChecked"
                @jump-shot="jumpToShot"
              />
              <div class="mt-3 grid grid-cols-2 gap-3 text-xs">
                <div>
                  <div class="font-semibold mb-1">角色出场</div>
                  <div v-for="row in statsRows.slice(0, 8)" :key="row.name">{{ row.name }}：{{ row.count }}</div>
                </div>
                <div>
                  <div class="font-semibold mb-1">关系共现</div>
                  <div v-for="row in relationRows.slice(0, 8)" :key="row.source + row.target">{{ row.source }} - {{ row.target }}：{{ row.count }}</div>
                </div>
              </div>
              <div class="mt-3 max-h-32 overflow-auto text-xs">
                <div v-for="item in queueRows" :key="String(item.id)" class="flex items-center justify-between border-b border-[var(--color-parchment)] py-1 gap-2">
                  <span>{{ item.id }}：第{{ item.start_chapter }}-{{ item.end_chapter }}章 · {{ item.status }}</span>
                  <span class="flex gap-1">
                    <button @click="updateQueue(String(item.id), 'paused')" class="px-2 py-0.5 border rounded" type="button">暂停</button>
                    <button @click="updateQueue(String(item.id), 'retry')" class="px-2 py-0.5 border rounded" type="button">重试</button>
                    <button @click="updateQueue(String(item.id), 'done')" class="px-2 py-0.5 border rounded" type="button">完成</button>
                  </span>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  </div>
</template>
