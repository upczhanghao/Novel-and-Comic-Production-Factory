import { ref, computed, watch } from 'vue'
import { useProjectStore } from '@/stores/project'
import { manjuApi } from '@/api/client'

// A5: 服务端持久化的漫剧版本历史。每个项目按 kind 存储于 manju/history/{kind}.json。
// 单实例单项目；切换 active project 时自动重载。

export type HistoryKind = 'script' | 'characters' | 'scenes' | 'storyboards'

export interface HistorySnapshot {
  ts: number
  kind: HistoryKind
  label: string
  payload: unknown
}

const KINDS: HistoryKind[] = ['script', 'characters', 'scenes', 'storyboards']

interface Store { script: HistorySnapshot[]; characters: HistorySnapshot[]; scenes: HistorySnapshot[]; storyboards: HistorySnapshot[] }

const empty = (): Store => ({ script: [], characters: [], scenes: [], storyboards: [] })

export function useManjuHistory() {
  const projectStore = useProjectStore()
  const all = ref<Store>(empty())

  async function refresh() {
    const fp = projectStore.filepath
    if (!fp) { all.value = empty(); return }
    try {
      const results = await Promise.all(KINDS.map((k) => manjuApi.historyList(fp, k)))
      const next = empty()
      KINDS.forEach((k, i) => { next[k] = (results[i].data?.snapshots ?? []) as HistorySnapshot[] })
      all.value = next
    } catch {
      all.value = empty()
    }
  }

  async function snapshot(kind: HistoryKind, payload: unknown, label?: string) {
    const fp = projectStore.filepath
    if (!fp) return
    try {
      const res = await manjuApi.historyCreate(fp, { kind, label, payload })
      const snap = res.data?.snapshot as HistorySnapshot | undefined
      if (snap) {
        const list = all.value[kind].slice()
        list.unshift(snap)
        all.value = { ...all.value, [kind]: list }
      }
    } catch { /* swallow — UI will show next refresh */ }
  }

  function list(kind: HistoryKind) {
    return computed(() => all.value[kind] || [])
  }

  function get(kind: HistoryKind, ts: number) {
    return (all.value[kind] || []).find((s) => s.ts === ts)
  }

  async function remove(kind: HistoryKind, ts: number) {
    const fp = projectStore.filepath
    if (!fp) return
    try {
      await manjuApi.historyDelete(fp, kind, ts)
      all.value = { ...all.value, [kind]: all.value[kind].filter((s) => s.ts !== ts) }
    } catch { /* ignore */ }
  }

  async function clear(kind?: HistoryKind) {
    const fp = projectStore.filepath
    if (!fp) return
    try {
      if (kind) {
        await manjuApi.historyClear(fp, kind)
        all.value = { ...all.value, [kind]: [] }
      } else {
        await Promise.all(KINDS.map((k) => manjuApi.historyClear(fp, k)))
        all.value = empty()
      }
    } catch { /* ignore */ }
  }

  watch(() => projectStore.filepath, () => { refresh() }, { immediate: true })

  return { snapshot, list, get, remove, clear, refresh }
}
