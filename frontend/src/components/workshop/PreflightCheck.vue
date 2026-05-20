<script setup lang="ts">
import { computed } from 'vue'
import type { useWorkshopState } from '@/composables/useWorkshopState'

const props = defineProps<{ state: ReturnType<typeof useWorkshopState>; step: string }>()
const emit = defineEmits<{ (e: 'dismiss'): void }>()

interface CheckItem { ok: boolean; label: string; hint: string }

const checks = computed<CheckItem[]>(() => {
  const s = props.state
  const items: CheckItem[] = []

  items.push({
    ok: Boolean(s.llmConfig.value),
    label: 'LLM 配置',
    hint: s.llmConfig.value ? `使用「${s.llmConfig.value}」` : '请先在「模型配置」中添加并选择 LLM',
  })

  if (['chapter', 'finalize'].includes(props.step)) {
    items.push({
      ok: Boolean(s.embConfig.value),
      label: 'Embedding 配置',
      hint: s.embConfig.value ? `使用「${s.embConfig.value}」` : '知识库检索需要 Embedding，可选但建议配置',
    })
  }

  if (props.step === 'blueprint' || props.step === 'chapter') {
    items.push({
      ok: Boolean(s.arch.value.result || s.seedText.value),
      label: '架构/核心种子',
      hint: s.arch.value.result ? '已生成' : '请先完成架构生成',
    })
  }

  if (props.step === 'chapter') {
    items.push({
      ok: Boolean(s.bp.value.result),
      label: '章节目录',
      hint: s.bp.value.result ? '已生成' : '请先完成目录生成',
    })
  }

  if (props.step === 'chapter' || props.step === 'expand') {
    const hasStyle = s.chStyle.value && s.chStyle.value !== '不使用文风'
    items.push({
      ok: Boolean(hasStyle),
      label: '文风模板',
      hint: hasStyle ? `使用「${s.chStyle.value}」` : '未选择文风，生成将使用默认风格（可选）',
    })
    const hasDNA = s.chNarrativeStyle.value && s.chNarrativeStyle.value !== '不使用文风'
    items.push({
      ok: Boolean(hasDNA),
      label: '叙事 DNA',
      hint: hasDNA ? `使用「${s.chNarrativeStyle.value}」` : '未选择叙事 DNA（可选）',
    })
  }

  return items
})

const allOk = computed(() => checks.value.every((c) => c.ok))
const criticalFail = computed(() => checks.value.some((c) => !c.ok && c.label === 'LLM 配置'))
</script>

<template>
  <div v-if="!allOk" class="pf-card" :class="{ critical: criticalFail }">
    <div class="pf-header">
      <strong>生成前检查</strong>
      <button class="pf-close" @click="emit('dismiss')" type="button">×</button>
    </div>
    <ul class="pf-list">
      <li v-for="c in checks" :key="c.label" :class="{ ok: c.ok }">
        <span class="pf-icon">{{ c.ok ? '✓' : '○' }}</span>
        <span class="pf-label">{{ c.label }}</span>
        <span class="pf-hint">{{ c.hint }}</span>
      </li>
    </ul>
    <p v-if="criticalFail" class="pf-warn">缺少必要配置，无法生成。</p>
  </div>
</template>

<style scoped>
.pf-card { padding: 12px 14px; border-radius: 10px; background: #fffbeb; border: 1px solid #fde68a; margin-bottom: 8px; }
.pf-card.critical { background: #fef2f2; border-color: #fecaca; }
.pf-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.pf-header strong { font-size: 13px; color: #78350f; }
.pf-close { background: transparent; border: 0; font-size: 18px; color: #78350f; cursor: pointer; }
.pf-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 4px; }
.pf-list li { display: grid; grid-template-columns: 18px 100px 1fr; gap: 6px; font-size: 12px; align-items: center; }
.pf-icon { font-weight: 700; color: var(--color-warning); }
.pf-list li.ok .pf-icon { color: var(--color-success); }
.pf-label { font-weight: 500; color: var(--color-ink); }
.pf-hint { color: var(--color-ink-light); }
.pf-warn { margin-top: 8px; font-size: 12px; color: var(--color-error); font-weight: 500; }
</style>
