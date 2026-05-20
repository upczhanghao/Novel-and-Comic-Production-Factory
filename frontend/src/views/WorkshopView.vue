<script setup lang="ts">
import { ref, computed } from 'vue'
import { useWorkshopState } from '@/composables/useWorkshopState'
import { useDraftAutosave } from '@/composables/useDraftAutosave'
import { watch } from 'vue'
import GlobalParamsCard from '@/components/workshop/GlobalParamsCard.vue'
import ArchitectureStep from '@/components/workshop/ArchitectureStep.vue'
import BlueprintStep from '@/components/workshop/BlueprintStep.vue'
import DetailedOutlineStep from '@/components/workshop/DetailedOutlineStep.vue'
import ChapterStep from '@/components/workshop/ChapterStep.vue'
import BatchGenerate from '@/components/workshop/BatchGenerate.vue'
import FinalizeStep from '@/components/workshop/FinalizeStep.vue'
import ExpandStep from '@/components/workshop/ExpandStep.vue'
import HumanizerStep from '@/components/workshop/HumanizerStep.vue'
import ProfileExtractBar from '@/components/ProfileExtractBar.vue'
import WorkshopStepper from '@/components/workshop/WorkshopStepper.vue'
import CarryForward from '@/components/workshop/CarryForward.vue'
import DraftRestoreBanner from '@/components/workshop/DraftRestoreBanner.vue'
import PreflightCheck from '@/components/workshop/PreflightCheck.vue'
import ResultSummary from '@/components/workshop/ResultSummary.vue'
import QuickRevise from '@/components/workshop/QuickRevise.vue'
import StyleSelector from '@/components/workshop/StyleSelector.vue'
import '@/styles/workshop.css'

const state = useWorkshopState()
const showPreflight = ref(true)
const showStyleSelector = ref(true)

const draft = useDraftAutosave(
  () => ({
    topic: state.topic.value,
    genre: state.genre.value,
    userGuidance: state.userGuidance.value,
    chapterNum: state.chapterNum.value,
    charactersInvolved: state.charactersInvolved.value,
    sceneLocation: state.sceneLocation.value,
    keyItems: state.keyItems.value,
    timeConstraint: state.timeConstraint.value,
    chGuidance: state.chGuidance.value,
  }),
  (d) => {
    if (typeof d.topic === 'string') state.topic.value = d.topic
    if (typeof d.genre === 'string') state.genre.value = d.genre
    if (typeof d.userGuidance === 'string') state.userGuidance.value = d.userGuidance
    if (typeof d.chapterNum === 'number') state.chapterNum.value = d.chapterNum
    if (typeof d.charactersInvolved === 'string') state.charactersInvolved.value = d.charactersInvolved
    if (typeof d.sceneLocation === 'string') state.sceneLocation.value = d.sceneLocation
    if (typeof d.keyItems === 'string') state.keyItems.value = d.keyItems
    if (typeof d.timeConstraint === 'string') state.timeConstraint.value = d.timeConstraint
    if (typeof d.chGuidance === 'string') state.chGuidance.value = d.chGuidance
  },
)

watch([
  state.topic, state.genre, state.userGuidance, state.chapterNum,
  state.charactersInvolved, state.sceneLocation, state.keyItems,
  state.timeConstraint, state.chGuidance,
], draft.schedule)

const stepRefs: Record<string, string> = {
  arch: 'arch-anchor', blueprint: 'bp-anchor', outline: 'outline-anchor',
  chapter: 'chapter-anchor', finalize: 'finalize-anchor', humanize: 'humanize-anchor',
  continue: 'continue-anchor',
}

function goto(idx: number) {
  const keys = ['arch', 'blueprint', 'outline', 'chapter', 'finalize', 'humanize', 'continue']
  const key = keys[idx]
  const id = stepRefs[key]
  if (id) {
    const el = document.getElementById(id)
    if (el) {
      if (el.tagName === 'DETAILS') (el as HTMLDetailsElement).open = true
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }
}

const preflightStep = computed(() => {
  const s = state
  if (s.expand.value.running || s.expand.value.result) return 'expand'
  if (s.humanize.value.running || s.humanize.value.result) return 'humanize'
  if (s.finalize.value.running || s.finalize.value.result) return 'finalize'
  if (s.chapter.value.running || s.chapter.value.result) return 'chapter'
  if (s.detailedOutline.value.running) return 'outline'
  if (s.bp.value.running || s.bp.value.result) return 'blueprint'
  return 'arch'
})
</script>

<template>
  <div class="module-page space-y-4">
    <div class="module-toolbar">
      <div>
        <div class="module-kicker">Writing Workshop</div>
        <div class="module-subtitle">从架构、蓝图到正文与后处理的一体化工作台。</div>
      </div>
      <div class="module-action-row">
        <button @click="state.reloadProjectContent()" :disabled="state.reloading.value" class="btn-primary" type="button"
          title="重新加载当前项目的架构、蓝图等内容">
          {{ state.reloading.value ? '加载中…' : '重载项目' }}
        </button>
        <button @click="state.doExportNovel()" :disabled="state.exporting.value || state.numChapters.value < 1" class="btn-primary" type="button"
          :title="state.numChapters.value < 1 ? '尚无章节可导出' : ''">
          {{ state.exporting.value ? '导出中…' : '合并导出小说' }}
        </button>
      </div>
    </div>

    <WorkshopStepper :state="state" @goto="goto" />

    <DraftRestoreBanner :snapshot="draft.restorable.value" @restore="draft.restore" @discard="draft.discard" />

    <Transition name="fade">
      <div v-if="state.saveMsg.value" class="px-4 py-2 rounded-md text-sm"
        :class="state.saveMsg.value.startsWith('✅') ? 'bg-green-50 text-green-800 border border-green-200' : 'bg-red-50 text-red-800 border border-red-200'">
        {{ state.saveMsg.value }}
      </div>
    </Transition>

    <ProfileExtractBar
      :show="state.profileShowConfirm.value"
      :preferences="state.profileExtracted.value"
      :confirm-msg="state.profileConfirmMsg.value"
      @confirm="state.profileConfirmAppend()"
      @dismiss="state.profileDismiss()"
    />

    <PreflightCheck v-if="showPreflight" :state="state" :step="preflightStep" @dismiss="showPreflight = false" />

    <div class="rounded-xl border border-[var(--color-parchment-darker)] bg-white p-5 space-y-3"
         v-if="showStyleSelector">
      <div class="flex items-center justify-between">
        <h3 class="font-semibold text-[var(--color-leather)]">文风 / 叙事 DNA</h3>
        <button class="text-xs text-[var(--color-ink-light)]" @click="showStyleSelector = false" type="button">收起</button>
      </div>
      <StyleSelector :state="state" />
    </div>

    <CarryForward :state="state" />

    <GlobalParamsCard :state="state" />

    <div id="arch-anchor"><ArchitectureStep :state="state" /></div>
    <ResultSummary
      title="架构"
      :content="state.arch.value.result"
      :llm="state.llmConfig.value"
      :style-name="state.archStyle.value"
      :started-at="state.arch.value.startedAt"
      :ended-at="state.arch.value.endedAt"
    />

    <div id="bp-anchor"><BlueprintStep :state="state" /></div>
    <ResultSummary
      title="目录"
      :content="state.bp.value.result"
      :llm="state.llmConfig.value"
      :style-name="state.bpStyle.value"
      :started-at="state.bp.value.startedAt"
      :ended-at="state.bp.value.endedAt"
    />

    <div id="outline-anchor"><DetailedOutlineStep :state="state" /></div>

    <div id="chapter-anchor"><ChapterStep :state="state" /></div>
    <ResultSummary
      title="章节正文"
      :content="state.chapter.value.result"
      :llm="state.llmConfig.value"
      :embedding="state.embConfig.value"
      :style-name="state.chStyle.value"
      :narrative-style="state.chNarrativeStyle.value"
      :started-at="state.chapter.value.startedAt"
      :ended-at="state.chapter.value.endedAt"
    />
    <QuickRevise :state="state" />

    <div id="batch-anchor"><BatchGenerate :state="state" /></div>

    <div id="finalize-anchor"><FinalizeStep :state="state" /></div>
    <ResultSummary
      title="定稿"
      :content="state.finalize.value.result"
      :llm="state.llmConfig.value"
      :embedding="state.embConfig.value"
      :started-at="state.finalize.value.startedAt"
      :ended-at="state.finalize.value.endedAt"
    />

    <ExpandStep :state="state" />

    <div id="humanize-anchor"><HumanizerStep :state="state" /></div>
  </div>
</template>
