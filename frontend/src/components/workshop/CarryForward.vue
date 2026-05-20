<script setup lang="ts">
import { computed } from 'vue'
import type { useWorkshopState } from '@/composables/useWorkshopState'
import { useFeedbackStore } from '@/stores/feedback'

const props = defineProps<{ state: ReturnType<typeof useWorkshopState> }>()
const feedback = useFeedbackStore()

const canForwardToBlueprint = computed(() => Boolean(props.state.arch.value.result || props.state.plotText.value))
const canForwardToOutline = computed(() => Boolean(props.state.bp.value.result))
const canForwardToChapter = computed(() => Boolean(props.state.outlineText.value || props.state.bp.value.result))

function extractTitleAndChars(blueprint: string, chapterNum: number): { characters?: string; scene?: string; items?: string } {
  const re = new RegExp(`第\\s*${chapterNum}\\s*章[^\\n]*\\n([\\s\\S]*?)(?=第\\s*\\d+\\s*章|$)`, 'i')
  const m = blueprint.match(re)
  if (!m) return {}
  const block = m[1]
  const charMatch = block.match(/角色[：:]\s*([^\n]+)/)
  const sceneMatch = block.match(/场景[：:]\s*([^\n]+)/) || block.match(/地点[：:]\s*([^\n]+)/)
  const itemsMatch = block.match(/关键物品[：:]\s*([^\n]+)/) || block.match(/道具[：:]\s*([^\n]+)/)
  return {
    characters: charMatch?.[1]?.trim(),
    scene: sceneMatch?.[1]?.trim(),
    items: itemsMatch?.[1]?.trim(),
  }
}

function carryArchToBlueprint() {
  const s = props.state
  if (!s.userGuidance.value && s.plotText.value) {
    const summary = s.plotText.value.split('\n').slice(0, 4).join('\n')
    s.userGuidance.value = `承接架构主线：\n${summary}`
    feedback.info('已将架构主线注入到目录生成指导')
  } else {
    feedback.info('全局指导已填写，未覆盖')
  }
}

function carryBlueprintToOutline() {
  const s = props.state
  s.outlineBatchStart.value = 1
  s.outlineBatchSize.value = Math.min(5, s.numChapters.value)
  feedback.success(`已重置为从第 1 章开始，批量 ${s.outlineBatchSize.value} 章`)
}

function carryToChapter() {
  const s = props.state
  const info = extractTitleAndChars(s.bp.value.result || '', s.chapterNum.value)
  let touched = 0
  if (info.characters && !s.charactersInvolved.value) { s.charactersInvolved.value = info.characters; touched++ }
  if (info.scene && !s.sceneLocation.value) { s.sceneLocation.value = info.scene; touched++ }
  if (info.items && !s.keyItems.value) { s.keyItems.value = info.items; touched++ }
  if (touched === 0) feedback.info('未在目录中匹配到该章节信息，或已填写过')
  else feedback.success(`已带入 ${touched} 项信息到第 ${s.chapterNum.value} 章`)
}
</script>

<template>
  <div class="cf-root">
    <button v-if="canForwardToBlueprint" class="cf-btn" @click="carryArchToBlueprint" type="button"
      :disabled="Boolean(props.state.userGuidance.value)"
      :title="props.state.userGuidance.value ? '全局指导已填写，无法覆盖' : '把架构主线注入到下一步的全局指导'">
      架构 → 目录指导
    </button>
    <button v-if="canForwardToOutline" class="cf-btn" @click="carryBlueprintToOutline" type="button"
      title="按目录章节数自动设置细纲生成范围">
      目录 → 细纲范围
    </button>
    <button v-if="canForwardToChapter" class="cf-btn" @click="carryToChapter" type="button"
      title="从目录/细纲解析当前章节的角色/场景/道具并填入章节字段">
      目录 → 第 {{ props.state.chapterNum.value }} 章字段
    </button>
  </div>
</template>

<style scoped>
.cf-root { display: flex; flex-wrap: wrap; gap: 6px; }
.cf-btn { padding: 4px 10px; border-radius: 6px; border: 1px dashed var(--color-leather-light); background: transparent; color: var(--color-leather-light); font-size: 11px; cursor: pointer; transition: all 0.15s; }
.cf-btn:hover:not(:disabled) { background: var(--color-leather-light); color: white; border-style: solid; }
.cf-btn:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
