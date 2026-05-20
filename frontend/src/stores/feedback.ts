import { defineStore } from 'pinia'
import { ref } from 'vue'

export type FeedbackType = 'success' | 'error' | 'warning' | 'info'

export interface FeedbackItem {
  id: number
  type: FeedbackType
  message: string
  detail?: string
  undoFn?: () => Promise<void> | void
  timestamp: number
  dismissed?: boolean
}

let _id = 0

export const useFeedbackStore = defineStore('feedback', () => {
  const items = ref<FeedbackItem[]>([])

  function push(type: FeedbackType, message: string, opts?: { detail?: string; undoFn?: () => Promise<void> | void }) {
    const item: FeedbackItem = { id: ++_id, type, message, detail: opts?.detail, undoFn: opts?.undoFn, timestamp: Date.now() }
    items.value.push(item)
    if (type !== 'error') {
      setTimeout(() => dismiss(item.id), 5000)
    }
    if (items.value.length > 20) items.value.shift()
  }

  function dismiss(id: number) {
    const idx = items.value.findIndex((i) => i.id === id)
    if (idx !== -1) items.value.splice(idx, 1)
  }

  async function undo(id: number) {
    const item = items.value.find((i) => i.id === id)
    if (item?.undoFn) {
      await item.undoFn()
      dismiss(id)
      push('info', `已撤销: ${item.message}`)
    }
  }

  function success(msg: string, opts?: { undoFn?: () => Promise<void> | void }) { push('success', msg, opts) }
  function error(msg: string, detail?: string) { push('error', msg, { detail }) }
  function warning(msg: string) { push('warning', msg) }
  function info(msg: string) { push('info', msg) }

  return { items, push, dismiss, undo, success, error, warning, info }
})
