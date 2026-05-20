<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
  kind: 'character' | 'scene' | 'storyboard'
  visualStyle: string
  extraGuidance: string
  sampleName?: string
}>()

const show = ref(false)

const template = computed(() => {
  if (props.kind === 'character') {
    return `[角色全身立绘]
${props.sampleName || '角色名'}, full body character sheet, front view,
${props.visualStyle || '国漫竖屏短剧，电影级构图'},
{角色外貌描述}, {服装描述},
white background, concept art, high detail,
${props.extraGuidance || ''}`
  }
  if (props.kind === 'scene') {
    return `[场景概念图]
{地点名称}, establishing shot, wide angle,
${props.visualStyle || '国漫竖屏短剧，电影级构图'},
{光影描述}, {氛围描述}, {时间段},
no characters, environment concept art,
${props.extraGuidance || ''}`
  }
  return `[分镜图]
{镜头描述}, {角色动作},
${props.visualStyle || '国漫竖屏短剧，电影级构图'},
{角色外貌引用}, {场景引用},
{光影}, {构图}, cinematic composition,
${props.extraGuidance || ''}`
})

const kindLabel = computed(() => {
  if (props.kind === 'character') return '角色卡'
  if (props.kind === 'scene') return '场景图'
  return '分镜图'
})
</script>

<template>
  <div class="tp-root">
    <button class="tp-toggle" @click="show = !show" type="button">
      {{ show ? '收起' : '预览' }}{{ kindLabel }}提示词模板
    </button>
    <div v-if="show" class="tp-preview">
      <div class="tp-label">生成后的提示词大致结构：</div>
      <pre class="tp-code">{{ template }}</pre>
      <div class="tp-note">花括号 {} 内的内容会被 AI 根据角色/场景/剧情自动填充。</div>
    </div>
  </div>
</template>

<style scoped>
.tp-root { margin-top: 6px; }
.tp-toggle { font-size: 11px; color: var(--color-leather-light); background: transparent; border: 0; padding: 0; cursor: pointer; text-decoration: underline; }
.tp-preview { margin-top: 8px; padding: 10px 12px; background: var(--color-surface-muted); border: 1px solid var(--color-control-border); border-radius: 8px; }
.tp-label { font-size: 11px; color: var(--color-ink-light); margin-bottom: 6px; }
.tp-code { font-family: var(--font-mono); font-size: 11px; white-space: pre-wrap; color: var(--color-ink); line-height: 1.6; margin: 0; }
.tp-note { font-size: 10px; color: var(--color-ink-light); margin-top: 8px; font-style: italic; }
</style>
