<script setup lang="ts">
import { computed } from 'vue'
import type { useWorkshopState } from '@/composables/useWorkshopState'

const props = defineProps<{ state: ReturnType<typeof useWorkshopState> }>()

const NO_STYLE = '不使用文风'

interface StyleItem { name: string; type: 'style' | 'dna'; active: boolean }

const items = computed<StyleItem[]>(() => {
  const s = props.state
  const list: StyleItem[] = []
  for (const name of s.styleList.value) {
    if (name === NO_STYLE) continue
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
  s.archStyle.value = next
  s.bpStyle.value = next
}

function toggleDNA(name: string) {
  const s = props.state
  s.chNarrativeStyle.value = s.chNarrativeStyle.value === name ? NO_STYLE : name
}
</script>

<template>
  <div class="ss-root">
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
      尚未创建文风或叙事 DNA。前往「文风与DNA」页面添加。
    </div>
  </div>
</template>

<style scoped>
.ss-root { display: flex; flex-direction: column; gap: 10px; }
.ss-section {}
.ss-title { font-size: 11px; font-weight: 600; color: var(--color-ink-light); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px; }
.ss-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.ss-chip { padding: 6px 14px; border-radius: 999px; border: 1px solid var(--color-control-border); background: white; font-size: 12px; color: var(--color-ink-light); cursor: pointer; transition: all 0.15s; }
.ss-chip:hover { border-color: var(--color-leather-light); color: var(--color-ink); }
.ss-chip.active { background: var(--color-ink); color: white; border-color: var(--color-ink); }
.ss-chip.none { font-style: italic; }
.ss-empty { font-size: 12px; color: var(--color-ink-light); padding: 8px 0; }
</style>
