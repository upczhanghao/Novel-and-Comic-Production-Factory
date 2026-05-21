import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface ConfirmOptions {
  message: string
  title?: string
  okText?: string
  cancelText?: string
  danger?: boolean
}

interface PendingConfirm extends ConfirmOptions {
  resolve: (ok: boolean) => void
}

export const useConfirmStore = defineStore('confirm', () => {
  const current = ref<PendingConfirm | null>(null)

  function ask(opts: ConfirmOptions): Promise<boolean> {
    if (current.value) current.value.resolve(false)
    return new Promise<boolean>((resolve) => {
      current.value = { ...opts, resolve }
    })
  }

  function decide(ok: boolean) {
    const c = current.value
    if (!c) return
    current.value = null
    c.resolve(ok)
  }

  return { current, ask, decide }
})

export function confirmDialog(message: string, opts?: Omit<ConfirmOptions, 'message'>): Promise<boolean> {
  return useConfirmStore().ask({ message, ...opts })
}
