<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ prompt: string; negative?: string }>()

const STYLE_KEYWORDS = ['cinematic', '电影', '国漫', '油画', 'concept art', 'photoreal', 'anime', 'studio ghibli', '8k', 'hdr', 'dramatic', 'surreal']
const QUALITY_KEYWORDS = ['high detail', 'masterpiece', 'best quality', 'ultra', '4k', '8k', 'hdr', 'sharp', 'highly detailed', 'professional']
const COMPOSITION_KEYWORDS = ['wide angle', 'close up', 'portrait', 'full body', 'dynamic', 'low angle', 'top down', 'over the shoulder', '景别', '构图', '视角']
const LIGHT_KEYWORDS = ['light', '光', 'sunset', 'dawn', 'night', '黄昏', '夜', 'rim light', 'backlight', 'soft light']

function pickHits(text: string, dict: string[]) {
  const lower = text.toLowerCase()
  return dict.filter((k) => lower.includes(k.toLowerCase()))
}

const stats = computed(() => {
  const text = props.prompt || ''
  const segments = text.split(/[,，\n]/).map((s) => s.trim()).filter(Boolean)
  return {
    chars: text.length,
    segments: segments.length,
    style: pickHits(text, STYLE_KEYWORDS),
    quality: pickHits(text, QUALITY_KEYWORDS),
    composition: pickHits(text, COMPOSITION_KEYWORDS),
    light: pickHits(text, LIGHT_KEYWORDS),
    negChars: (props.negative || '').length,
  }
})

const warnings = computed(() => {
  const w: string[] = []
  if (stats.value.chars > 1500) w.push('提示词过长（>1500 字符），部分模型会截断尾部')
  if (stats.value.chars < 30) w.push('提示词过短，模型可能自由发挥过度')
  if (!stats.value.style.length && !stats.value.quality.length) w.push('缺少风格 / 质量关键词，画面可能偏随机')
  if (!stats.value.light.length) w.push('未指定光影信息，氛围一致性较弱')
  if (!stats.value.composition.length) w.push('缺少景别 / 构图描述，可能出现重复构图')
  return w
})
</script>

<template>
  <div class="pb-root">
    <div class="pb-grid">
      <div class="pb-cell"><span>字符</span><strong>{{ stats.chars }}</strong></div>
      <div class="pb-cell"><span>分段</span><strong>{{ stats.segments }}</strong></div>
      <div class="pb-cell"><span>负向</span><strong>{{ stats.negChars }}</strong></div>
    </div>
    <div class="pb-tags" v-if="stats.style.length || stats.quality.length || stats.composition.length || stats.light.length">
      <span v-for="k in stats.style" :key="`s-${k}`" class="pb-tag style">风格 · {{ k }}</span>
      <span v-for="k in stats.quality" :key="`q-${k}`" class="pb-tag quality">质量 · {{ k }}</span>
      <span v-for="k in stats.composition" :key="`c-${k}`" class="pb-tag comp">构图 · {{ k }}</span>
      <span v-for="k in stats.light" :key="`l-${k}`" class="pb-tag light">光影 · {{ k }}</span>
    </div>
    <ul v-if="warnings.length" class="pb-warn">
      <li v-for="(w, i) in warnings" :key="i">⚠ {{ w }}</li>
    </ul>
  </div>
</template>

<style scoped>
.pb-root { padding: 8px 10px; background: var(--color-surface-muted); border-radius: 8px; font-size: 11px; }
.pb-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
.pb-cell { display: flex; justify-content: space-between; padding: 4px 8px; background: white; border-radius: 4px; }
.pb-cell span { color: var(--color-ink-light); }
.pb-cell strong { font-weight: 600; }
.pb-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
.pb-tag { padding: 2px 8px; border-radius: 999px; font-size: 10px; }
.pb-tag.style { background: #fef3c7; color: #78350f; }
.pb-tag.quality { background: #d1fae5; color: #064e3b; }
.pb-tag.comp { background: #dbeafe; color: #1e40af; }
.pb-tag.light { background: #fce7f3; color: #831843; }
.pb-warn { list-style: none; padding: 0; margin: 6px 0 0; display: flex; flex-direction: column; gap: 2px; color: var(--color-warning); font-size: 10px; }
</style>
