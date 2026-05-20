import { ref } from 'vue'

export interface UndoEntry {
  label: string
  do: () => Promise<void> | void
  undo: () => Promise<void> | void
}

const stack = ref<UndoEntry[]>([])
const MAX = 30

export function useUndoStack() {
  async function execute(entry: UndoEntry) {
    await entry.do()
    stack.value.push(entry)
    if (stack.value.length > MAX) stack.value.shift()
  }

  async function undoLast(): Promise<string | null> {
    const e = stack.value.pop()
    if (!e) return null
    await e.undo()
    return e.label
  }

  function clear() { stack.value = [] }

  return { stack, execute, undoLast, clear }
}
