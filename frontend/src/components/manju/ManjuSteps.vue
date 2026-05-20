<script setup lang="ts">
import { computed } from 'vue'

interface StepInfo {
  key: string
  label: string
  done: boolean
  current?: boolean
  produces?: string
  dependsOn?: string
  hint?: string
}

const props = defineProps<{
  hasImport: boolean
  hasScript: boolean
  hasCharacters: boolean
  hasScenes: boolean
  hasStoryboards: boolean
  hasImages: boolean
  hasExport?: boolean
}>()

const emit = defineEmits<{ (e: 'goto', key: string): void }>()

const steps = computed<StepInfo[]>(() => {
  const s = [
    { key: 'import', label: '导入小说', done: props.hasImport, produces: '章节目录 + 元数据', dependsOn: 'TXT 文件', hint: '上传 TXT 解析章节' },
    { key: 'script', label: '剧本改编', done: props.hasScript, produces: 'script.txt 漫剧脚本', dependsOn: '已导入章节', hint: '把小说重构为竖屏脚本' },
    { key: 'characters', label: '角色卡', done: props.hasCharacters, produces: 'characters.json', dependsOn: '剧本或章节', hint: '锁定外观/服装/禁忌' },
    { key: 'scenes', label: '场景库', done: props.hasScenes, produces: 'scenes.txt', dependsOn: '角色卡', hint: '沉淀地点与光影' },
    { key: 'storyboards', label: '分镜表', done: props.hasStoryboards, produces: 'storyboards.json', dependsOn: '角色 + 场景', hint: '拆解为可执行镜头' },
    { key: 'images', label: '分镜生图', done: props.hasImages, produces: 'images/*.png', dependsOn: '分镜表 + 图片配置', hint: '为每个镜头生成参考图' },
    { key: 'export', label: '导出', done: props.hasExport || props.hasStoryboards, produces: 'csv / md / txt / zip', dependsOn: '上述任意产物', hint: '导出制片包' },
  ]
  // current = 第一个未完成
  const currentIdx = s.findIndex((it) => !it.done)
  return s.map((it, idx) => ({ ...it, current: idx === currentIdx }))
})
</script>

<template>
  <div class="ms-root">
    <div class="ms-track">
      <button
        v-for="(step, idx) in steps"
        :key="step.key"
        class="ms-step"
        :class="{ done: step.done, current: step.current }"
        @click="emit('goto', step.key)"
        type="button"
      >
        <div class="ms-head">
          <span class="ms-num">{{ idx + 1 }}</span>
          <span class="ms-label">{{ step.label }}</span>
          <span v-if="step.done" class="ms-flag">✓</span>
        </div>
        <div class="ms-meta">
          <div class="ms-row"><span>产物</span><strong>{{ step.produces }}</strong></div>
          <div class="ms-row"><span>依赖</span><strong>{{ step.dependsOn }}</strong></div>
        </div>
        <div class="ms-hint">{{ step.hint }}</div>
      </button>
    </div>
  </div>
</template>

<style scoped>
.ms-root { padding: 8px; background: var(--color-surface-muted); border-radius: 12px; border: 1px solid var(--color-control-border); }
.ms-track { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; }
@media (max-width: 1100px) { .ms-track { grid-template-columns: repeat(4, 1fr); } }
@media (max-width: 640px) { .ms-track { grid-template-columns: repeat(2, 1fr); } }
.ms-step { text-align: left; padding: 10px; background: white; border: 1px solid var(--color-control-border); border-radius: 8px; cursor: pointer; transition: all 0.15s; }
.ms-step:hover { border-color: var(--color-leather-light); }
.ms-step.done { border-color: var(--color-success); background: linear-gradient(to bottom, #ecfdf5, white); }
.ms-step.current { border-color: var(--color-gold); box-shadow: 0 0 0 2px var(--color-gold-light); }
.ms-head { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.ms-num { width: 20px; height: 20px; border-radius: 50%; background: var(--color-control-border); color: white; display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; }
.ms-step.done .ms-num { background: var(--color-success); }
.ms-step.current .ms-num { background: var(--color-gold); }
.ms-label { font-weight: 600; font-size: 13px; color: var(--color-ink); flex: 1; }
.ms-flag { color: var(--color-success); font-weight: 700; }
.ms-meta { display: flex; flex-direction: column; gap: 2px; margin-bottom: 6px; }
.ms-row { display: flex; gap: 4px; font-size: 10px; color: var(--color-ink-light); }
.ms-row strong { font-weight: 500; color: var(--color-ink); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ms-hint { font-size: 11px; color: var(--color-ink-light); line-height: 1.4; }
</style>
