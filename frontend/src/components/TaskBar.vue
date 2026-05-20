<script setup lang="ts">
import { ref, computed } from 'vue'
import { useTasksStore, type TaskItem } from '@/stores/tasks'

const tasks = useTasksStore()
const expanded = ref(false)

const visibleTasks = computed(() => {
  const recent = tasks.tasks.slice().reverse().slice(0, 8)
  return recent
})

function pct(t: TaskItem) {
  if (t.progressValue == null) return null
  return Math.min(100, Math.round(t.progressValue * 100))
}

function statusLabel(t: TaskItem) {
  if (t.status === 'running') return '运行中'
  if (t.status === 'done') return '完成'
  if (t.status === 'error') return '失败'
  return '已取消'
}
</script>

<template>
  <Teleport to="body">
    <div v-if="tasks.tasks.length > 0" class="tb-root" :class="{ expanded }">
      <button class="tb-toggle" @click="expanded = !expanded" type="button">
        <span class="tb-spinner" v-if="tasks.hasRunning" />
        <span class="tb-count" v-else>{{ tasks.tasks.length }}</span>
        <span class="tb-label">{{ tasks.hasRunning ? `${tasks.activeTasks.length} 个任务进行中` : '任务记录' }}</span>
        <span class="tb-arrow">{{ expanded ? '▾' : '▴' }}</span>
      </button>

      <div v-if="expanded" class="tb-panel">
        <div class="tb-header">
          <span>任务列表</span>
          <button class="tb-clear" @click="tasks.tasks.filter(t => t.status !== 'running').forEach(t => tasks.remove(t.id))" type="button">清除已结束</button>
        </div>
        <div class="tb-items">
          <div v-for="t in visibleTasks" :key="t.id" class="tb-item" :class="`tb-${t.status}`">
            <div class="tb-row">
              <span class="tb-name">{{ t.label }}</span>
              <span class="tb-status">{{ statusLabel(t) }}</span>
            </div>
            <div class="tb-row">
              <span class="tb-progress">{{ t.progress || (t.status === 'running' ? '处理中…' : '') }}</span>
              <button
                v-if="t.status === 'running'"
                class="tb-cancel"
                @click="tasks.cancel(t.id)"
                type="button"
              >取消</button>
              <button
                v-else
                class="tb-cancel ghost"
                @click="tasks.remove(t.id)"
                type="button"
              >移除</button>
            </div>
            <div v-if="t.status === 'running'" class="tb-bar">
              <div class="tb-bar-fill" :style="{ width: pct(t) != null ? pct(t) + '%' : '40%' }" :class="{ indeterminate: pct(t) == null }" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.tb-root { position: fixed; bottom: 20px; left: 20px; z-index: 55; }
.tb-toggle { display: inline-flex; align-items: center; gap: 8px; padding: 8px 14px; background: var(--color-ink); color: white; border: 0; border-radius: 999px; box-shadow: 0 6px 20px rgba(0,0,0,0.18); font-size: 13px; }
.tb-toggle:hover { background: var(--color-leather-dark); }
.tb-spinner { width: 12px; height: 12px; border-radius: 50%; border: 2px solid rgba(255,255,255,0.3); border-top-color: var(--color-gold); animation: spin 0.8s linear infinite; }
.tb-count { width: 18px; height: 18px; border-radius: 50%; background: var(--color-gold); color: white; display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; }
.tb-arrow { opacity: 0.6; font-size: 10px; }
@keyframes spin { to { transform: rotate(360deg); } }
.tb-panel { margin-top: 8px; width: 360px; max-height: 60vh; overflow-y: auto; background: var(--color-surface); border: 1px solid var(--color-control-border); border-radius: 12px; box-shadow: 0 12px 32px rgba(0,0,0,0.18); }
.tb-header { display: flex; justify-content: space-between; padding: 10px 14px; border-bottom: 1px solid var(--color-control-border); font-size: 12px; font-weight: 600; color: var(--color-ink-light); }
.tb-clear { background: transparent; border: 0; color: var(--color-leather-light); font-size: 12px; padding: 0; }
.tb-items { padding: 8px; display: flex; flex-direction: column; gap: 6px; }
.tb-item { padding: 8px 10px; border-radius: 8px; background: var(--color-surface-muted); border-left: 3px solid var(--color-control-border); }
.tb-item.tb-running { border-left-color: var(--color-gold); }
.tb-item.tb-done { border-left-color: var(--color-success); opacity: 0.7; }
.tb-item.tb-error { border-left-color: var(--color-error); }
.tb-item.tb-cancelled { border-left-color: var(--color-ink-light); opacity: 0.6; }
.tb-row { display: flex; justify-content: space-between; align-items: center; gap: 8px; font-size: 12px; }
.tb-name { font-weight: 500; color: var(--color-ink); }
.tb-status { color: var(--color-ink-light); font-size: 11px; }
.tb-progress { color: var(--color-ink-light); font-size: 11px; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tb-cancel { background: var(--color-error); color: white; border: 0; padding: 2px 8px; border-radius: 6px; font-size: 11px; }
.tb-cancel.ghost { background: transparent; color: var(--color-ink-light); border: 1px solid var(--color-control-border); }
.tb-bar { margin-top: 6px; height: 3px; background: var(--color-control-border); border-radius: 2px; overflow: hidden; }
.tb-bar-fill { height: 100%; background: var(--color-gold); transition: width 0.3s; }
.tb-bar-fill.indeterminate { animation: indeterminate 1.5s infinite; }
@keyframes indeterminate { 0% { transform: translateX(-100%); } 100% { transform: translateX(250%); } }
@media (max-width: 640px) {
  .tb-root { left: 12px; bottom: 90px; }
  .tb-panel { width: calc(100vw - 24px); }
}
</style>
