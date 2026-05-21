<script setup lang="ts">
import { computed, ref } from 'vue'
import type { useWorkshopState } from '@/composables/useWorkshopState'

const props = defineProps<{ state: ReturnType<typeof useWorkshopState> }>()

const NO_STYLE = '不使用文风'

interface StyleItem { name: string; type: 'style' | 'dna'; active: boolean }

// 「应用到所有步骤」模式（开启时，文风同时设置到架构/蓝图/章节三步;关闭时仅设置到章节步骤）。
// 默认开启，与历史行为兼容；关闭时用户需要在各步面板单独选择文风。
const applyAll = ref(true)

const items = computed<StyleItem[]>(() => {
  const s = props.state
  const list: StyleItem[] = []
  for (const name of s.styleList.value) {
    if (name === NO_STYLE) continue
    // 启发式分类：当服务端未提供 kind 元数据时，按命名约定区分 style/DNA。
    // 真正的 kind 区分需要 A 级架构改动（见 docs/audit-2026-05-21.md A10）。
    const isStyle = !name.toLowerCase().includes('dna') && !name.includes('叙事')
    const isDNA = !isStyle
    const active = isStyle
      ? (s.chStyle.value === name || s.archStyle.value === name || s.bpStyle.value === name)
      : (s.chNarrativeStyle.value === name)
    list.push({ name, type: isDNA ? 'dna' : 'style', active })
  }
  return list
})

const styles = computed(() => items.value.filter((i) => i.type === 'style'))
const dnas = computed(() => items.value.filter((i) => i.type === 'dna'))

function toggleStyle(name: string) {
  const s = props.state
  const current = s.chStyle.value
  const next = current === name ? NO_STYLE : name
  s.chStyle.value = next
  if (applyAll.value) {
    s.archStyle.value = next
    s.bpStyle.value = next
  }
}

function toggleDNA(name: string) {
  const s = props.state
  s.chNarrativeStyle.value = s.chNarrativeStyle.value === name ? NO_STYLE : name
}

// 当前各步骤是否已用相同/不同文风
const styleScope = computed(() => {
  const s = props.state
  const ch = s.chStyle.value
  const ar = s.archStyle.value
  const bp = s.bpStyle.value
  if (ch === ar && ch === bp) return ch === NO_STYLE ? '未选择' : `三步均使用 ${ch}`
  return `架构: ${ar} · 蓝图: ${bp} · 章节: ${ch}`
})
</script>

<template>
  <div class="ss-root">
    <div class="ss-mode">
      <label class="ss-mode-label">
        <input type="checkbox" v-model="applyAll" />
        <span>应用到所有步骤（架构 / 蓝图 / 章节）</span>
      </label>
      <span class="ss-mode-hint" :title="styleScope">{{ applyAll ? '点击文风将同步到三个步骤' : '点击文风仅设置章节步骤（其他步骤请在对应面板设置）' }}</span>
    </div>
    <div class="ss-scope">当前：{{ styleScope }}</div>
    <div class="ss-section" v-if="styles.length">
      <div class="ss-title">文风模板</div>
      <div class="ss-chips">
        <button
          v-for="item in styles"
          :key="item.name"
          class="ss-chip"
          :class="{ active: item.active }"
          @click="toggleStyle(item.name)"
          type="button"
        >{{ item.name }}</button>
        <button
          class="ss-chip none"
          :class="{ active: props.state.chStyle.value === NO_STYLE }"
          @click="toggleStyle(NO_STYLE)"
          type="button"
        >不使用</button>
      </div>
    </div>
    <div class="ss-section" v-if="dnas.length">
      <div class="ss-title">叙事 DNA</div>
      <div class="ss-chips">
        <button
          v-for="item in dnas"
          :key="item.name"
          class="ss-chip"
          :class="{ active: item.active }"
          @click="toggleDNA(item.name)"
          type="button"
        >{{ item.name }}</button>
        <button
          class="ss-chip none"
          :class="{ active: props.state.chNarrativeStyle.value === NO_STYLE }"
          @click="toggleDNA(NO_STYLE)"
          type="button"
        >不使用</button>
      </div>
    </div>
    <div v-if="!styles.length && !dnas.length" class="ss-empty">
      尚未创建文风或叙事 DNA。前往
      <router-link to="/styles" class="ss-link">「文风与DNA」</router-link>
      页面添加。
    </div>
  </div>
</template>

<style scoped>
.ss-root { display: flex; flex-direction: column; gap: 10px; }
.ss-mode { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 6px 10px; background: var(--color-surface-muted); border-radius: 8px; }
.ss-mode-label { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--color-ink); cursor: pointer; }
.ss-mode-hint { font-size: 11px; color: var(--color-ink-light); }
.ss-scope { font-size: 11px; color: var(--color-ink-light); padding: 0 4px; }
.ss-section {}
.ss-title { font-size: 11px; font-weight: 600; color: var(--color-ink-light); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px; }
.ss-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.ss-chip { padding: 6px 14px; border-radius: 999px; border: 1px solid var(--color-control-border); background: white; font-size: 12px; color: var(--color-ink-light); cursor: pointer; transition: all 0.15s; }
.ss-chip:hover { border-color: var(--color-leather-light); color: var(--color-ink); }
.ss-chip.active { background: var(--color-ink); color: white; border-color: var(--color-ink); }
.ss-chip.none { font-style: italic; }
.ss-empty { font-size: 12px; color: var(--color-ink-light); padding: 8px 0; }
.ss-link { color: var(--color-leather); text-decoration: underline; }
</style>
