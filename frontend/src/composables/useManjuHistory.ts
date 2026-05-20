import { ref, computed } from 'vue'
import { useProjectStore } from '@/stores/project'

export type HistoryKind = 'script' | 'characters' | 'scenes' | 'storyboards'

export interface HistorySnapshot {
  ts: number
  kind: HistoryKind
  label: string
  payload: unknown
}

const MAX_PER_KIND = 20
const KEY_PREFIX = 'nw_manju_history:'

function storageKey(project: string) { return `${KEY_PREFIX}${project || '_default'}` }

interface Store { [kind: string]: HistorySnapshot[] }

function readAll(project: string): Store {
  try {
    const raw = localStorage.getItem(storageKey(project))
    return raw ? JSON.parse(raw) as Store : {}
  } catch { return {} }
}

function writeAll(project: string, store: Store) {
  try { localStorage.setItem(storageKey(project), JSON.stringify(store)) } catch { /* quota */ }
}

export function useManjuHistory() {
  const projectStore = useProjectStore()
  const all = ref<Store>(readAll(projectStore.activeProject))

  function refresh() { all.value = readAll(projectStore.activeProject) }

  function snapshot(kind: HistoryKind, payload: unknown, label?: string) {
    const project = projectStore.activeProject
    if (!project) return
    const store = readAll(project)
    const list = store[kind] || []
    list.push({ ts: Date.now(), kind, label: label ?? new Date().toLocaleString(), payload })
    while (list.length > MAX_PER_KIND) list.shift()
    store[kind] = list
    writeAll(project, store)
    all.value = store
  }

  function list(kind: HistoryKind) {
    return computed(() => (all.value[kind] || []).slice().reverse())
  }

  function get(kind: HistoryKind, ts: number) {
    return (all.value[kind] || []).find((s) => s.ts === ts)
  }

  function remove(kind: HistoryKind, ts: number) {
    const project = projectStore.activeProject
    if (!project) return
    const store = readAll(project)
    store[kind] = (store[kind] || []).filter((s) => s.ts !== ts)
    writeAll(project, store)
    all.value = store
  }

  function clear(kind?: HistoryKind) {
    const project = projectStore.activeProject
    if (!project) return
    if (!kind) {
      localStorage.removeItem(storageKey(project))
      all.value = {}
    } else {
      const store = readAll(project)
      delete store[kind]
      writeAll(project, store)
      all.value = store
    }
  }

  return { snapshot, list, get, remove, clear, refresh }
}
