<script setup lang="ts">
import { computed } from 'vue'

interface DefaultSlot { label: string; value: string; missing?: boolean }

const props = defineProps<{
  title: string
  subtitle?: string
  icon?: string
  defaults: DefaultSlot[]
  accent?: string
}>()

const accentStyle = computed(() => ({ ['--section-accent' as string]: props.accent ?? 'var(--color-leather)' }))
</script>

<template>
  <header class="csh-root" :style="accentStyle">
    <div class="csh-bar" />
    <div class="csh-main">
      <div class="csh-title-row">
        <span v-if="icon" class="csh-icon">{{ icon }}</span>
        <h3 class="csh-title">{{ title }}</h3>
      </div>
      <p v-if="subtitle" class="csh-subtitle">{{ subtitle }}</p>
      <div v-if="defaults.length" class="csh-defaults">
        <span v-for="(d, i) in defaults" :key="i" class="csh-chip" :class="{ missing: d.missing }">
          <span class="csh-chip-label">{{ d.label }}</span>
          <span class="csh-chip-value">{{ d.value || '未设置' }}</span>
        </span>
      </div>
    </div>
  </header>
</template>

<style scoped>
.csh-root { display: flex; gap: 12px; padding: 12px 14px; background: var(--color-parchment); border: 1px solid var(--color-control-border); border-radius: 10px 10px 0 0; border-bottom: none; }
.csh-bar { width: 3px; border-radius: 2px; background: var(--section-accent); flex-shrink: 0; }
.csh-main { flex: 1; min-width: 0; }
.csh-title-row { display: flex; align-items: center; gap: 8px; }
.csh-icon { font-size: 16px; }
.csh-title { font-size: 15px; font-weight: 700; color: var(--color-ink); margin: 0; }
.csh-subtitle { font-size: 12px; color: var(--color-ink-light); margin: 2px 0 6px; }
.csh-defaults { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
.csh-chip { display: inline-flex; align-items: center; gap: 6px; padding: 3px 8px; font-size: 11px; background: white; border: 1px solid var(--color-control-border); border-radius: 999px; }
.csh-chip-label { color: var(--color-ink-light); }
.csh-chip-value { color: var(--color-ink); font-weight: 600; }
.csh-chip.missing { background: #fef9e7; border-color: #fde68a; }
.csh-chip.missing .csh-chip-value { color: #92400e; font-weight: 500; }
</style>
