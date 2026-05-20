<script setup lang="ts">
import { computed } from 'vue'

interface Issue {
  level?: string
  shot_id?: string
  message?: string
  [k: string]: unknown
}

interface Shot {
  id: string
  chapter_num: number
  shot_no: number
  characters?: string
  location?: string
  [k: string]: unknown
}

const props = defineProps<{ issues: Issue[]; shots: Shot[] }>()
const emit = defineEmits<{ (e: 'jumpShot', shotId: string): void }>()

const shotMap = computed(() => Object.fromEntries(props.shots.map((s) => [s.id, s])))

const grouped = computed(() => {
  const errors = props.issues.filter((i) => i.level === 'error')
  const warnings = props.issues.filter((i) => i.level === 'warning')
  const infos = props.issues.filter((i) => i.level === 'info' || !i.level)
  return { errors, warnings, infos }
})

function suggest(message: string): string {
  if (message.includes('未锁定')) return '建议：进入角色卡，勾选「锁定」固化外貌描述'
  if (message.includes('缺少背景场景')) return '建议：补全分镜的「场景/地点」字段，或在场景库引用已有场景'
  if (message.includes('缺少光影')) return '建议：补充光影/时间字段（晨光、夜雨、黄昏等）以稳定氛围'
  if (message.includes('转场')) return '建议：在「连续性」字段添加转场说明（如「切到」「来到」）'
  if (message.includes('提示词')) return '建议：使用「提示词增强」自动补全或手动修订该分镜 prompt'
  return ''
}

function shotLabel(id?: string) {
  if (!id) return ''
  const s = shotMap.value[id]
  return s ? `第 ${s.chapter_num} 章 · 镜 ${s.shot_no}` : id
}

function shotChars(id?: string): string {
  if (!id) return ''
  return String(shotMap.value[id]?.characters ?? '')
}
</script>

<template>
  <div v-if="issues.length" class="ci-root">
    <div class="ci-summary">
      <span class="ci-pill error" v-if="grouped.errors.length">{{ grouped.errors.length }} 错误</span>
      <span class="ci-pill warning" v-if="grouped.warnings.length">{{ grouped.warnings.length }} 警告</span>
      <span class="ci-pill info" v-if="grouped.infos.length">{{ grouped.infos.length }} 提示</span>
    </div>
    <ul class="ci-list">
      <li v-for="(item, idx) in issues" :key="idx" :class="`level-${item.level || 'info'}`">
        <div class="ci-row">
          <span class="ci-level">{{ item.level || 'info' }}</span>
          <button v-if="item.shot_id" class="ci-locator" @click="emit('jumpShot', item.shot_id)" type="button">
            {{ shotLabel(item.shot_id) }}
          </button>
          <span v-if="shotChars(item.shot_id)" class="ci-chars" :title="`涉及角色：${shotChars(item.shot_id)}`">
            {{ shotChars(item.shot_id) }}
          </span>
        </div>
        <div class="ci-msg">{{ item.message }}</div>
        <div v-if="suggest(String(item.message || ''))" class="ci-sugg">{{ suggest(String(item.message || '')) }}</div>
      </li>
    </ul>
  </div>
  <div v-else class="ci-empty">尚未运行连续性检查，或当前数据无可识别的连续性问题。</div>
</template>

<style scoped>
.ci-root { display: flex; flex-direction: column; gap: 8px; }
.ci-summary { display: flex; gap: 6px; }
.ci-pill { padding: 3px 10px; border-radius: 999px; font-size: 11px; font-weight: 600; }
.ci-pill.error { background: #fee2e2; color: #991b1b; }
.ci-pill.warning { background: #fef3c7; color: #92400e; }
.ci-pill.info { background: #dbeafe; color: #1e40af; }
.ci-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 6px; max-height: 360px; overflow-y: auto; }
.ci-list li { padding: 8px 10px; border-radius: 8px; background: var(--color-surface); border-left: 3px solid var(--color-control-border); }
.ci-list li.level-error { border-left-color: #dc2626; background: #fef2f2; }
.ci-list li.level-warning { border-left-color: var(--color-warning); background: #fffbeb; }
.ci-list li.level-info { border-left-color: var(--color-leather-light); background: #eff6ff; }
.ci-row { display: flex; gap: 6px; align-items: center; font-size: 11px; margin-bottom: 4px; }
.ci-level { text-transform: uppercase; font-weight: 700; letter-spacing: 0.06em; color: var(--color-ink-light); font-size: 10px; }
.ci-locator { background: transparent; border: 0; padding: 0; color: var(--color-leather-light); font-weight: 600; cursor: pointer; text-decoration: underline; }
.ci-chars { color: var(--color-ink-light); margin-left: auto; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 200px; }
.ci-msg { font-size: 13px; color: var(--color-ink); }
.ci-sugg { margin-top: 4px; padding: 4px 8px; background: rgba(0,0,0,0.04); border-radius: 4px; font-size: 11px; color: var(--color-ink-light); font-style: italic; }
.ci-empty { padding: 16px; font-size: 12px; color: var(--color-ink-light); text-align: center; }
</style>
