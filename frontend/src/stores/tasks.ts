import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface TaskItem {
  id: string
  label: string
  progress: string
  progressValue?: number
  status: 'running' | 'done' | 'error' | 'cancelled'
  abortFn?: () => void
  startedAt: number
}

export const useTasksStore = defineStore('tasks', () => {
  const tasks = ref<TaskItem[]>([])
  const activeTasks = computed(() => tasks.value.filter((t) => t.status === 'running'))
  const hasRunning = computed(() => activeTasks.value.length > 0)

  function register(id: string, label: string, abortFn?: () => void): TaskItem {
    const existing = tasks.value.find((t) => t.id === id)
    if (existing) {
      existing.status = 'running'
      existing.progress = ''
      existing.progressValue = undefined
      existing.abortFn = abortFn
      existing.startedAt = Date.now()
      return existing
    }
    const task: TaskItem = { id, label, progress: '', status: 'running', abortFn, startedAt: Date.now() }
    tasks.value.push(task)
    if (tasks.value.length > 50) tasks.value = tasks.value.slice(-30)
    return task
  }

  function update(id: string, progress: string, value?: number) {
    const t = tasks.value.find((i) => i.id === id)
    if (t) { t.progress = progress; if (value !== undefined) t.progressValue = value }
  }

  function finish(id: string, status: 'done' | 'error' | 'cancelled' = 'done') {
    const t = tasks.value.find((i) => i.id === id)
    if (t) t.status = status
  }

  function cancel(id: string) {
    const t = tasks.value.find((i) => i.id === id)
    if (t?.abortFn) t.abortFn()
    finish(id, 'cancelled')
  }

  function remove(id: string) {
    tasks.value = tasks.value.filter((t) => t.id !== id)
  }

  return { tasks, activeTasks, hasRunning, register, update, finish, cancel, remove }
})
