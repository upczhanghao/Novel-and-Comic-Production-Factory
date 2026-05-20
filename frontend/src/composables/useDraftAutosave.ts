import { watch, ref, onMounted } from 'vue'
import { useProjectStore } from '@/stores/project'
import { useFeedbackStore } from '@/stores/feedback'

interface DraftSnapshot {
  ts: number
  fields: Record<string, unknown>
}

const KEY_PREFIX = 'nw_workshop_draft:'

function key(project: string) { return `${KEY_PREFIX}${project || '_default'}` }

export function useDraftAutosave(getter: () => Record<string, unknown>, setter: (data: Record<string, unknown>) => void) {
  const projectStore = useProjectStore()
  const feedback = useFeedbackStore()
  const lastSaved = ref<number | null>(null)
  const restorable = ref<DraftSnapshot | null>(null)

  let timer: ReturnType<typeof setTimeout> | null = null

  function persist() {
    const project = projectStore.activeProject
    if (!project) return
    try {
      const snapshot: DraftSnapshot = { ts: Date.now(), fields: getter() }
      localStorage.setItem(key(project), JSON.stringify(snapshot))
      lastSaved.value = snapshot.ts
    } catch { /* quota / serialization errors ignored */ }
  }

  function schedule() {
    if (timer) clearTimeout(timer)
    timer = setTimeout(persist, 1500)
  }

  function readSnapshot(): DraftSnapshot | null {
    const project = projectStore.activeProject
    if (!project) return null
    try {
      const raw = localStorage.getItem(key(project))
      return raw ? JSON.parse(raw) as DraftSnapshot : null
    } catch { return null }
  }

  function restore() {
    const snap = restorable.value
    if (!snap) return
    setter(snap.fields)
    restorable.value = null
    feedback.success('已恢复上次的草稿')
  }

  function discard() {
    const project = projectStore.activeProject
    if (project) localStorage.removeItem(key(project))
    restorable.value = null
  }

  onMounted(() => {
    const snap = readSnapshot()
    if (snap && Date.now() - snap.ts < 1000 * 60 * 60 * 24 * 7) {
      restorable.value = snap
    }
  })

  watch(() => projectStore.activeProject, () => {
    const snap = readSnapshot()
    restorable.value = snap && Date.now() - snap.ts < 1000 * 60 * 60 * 24 * 7 ? snap : null
  })

  return { schedule, persist, restore, discard, lastSaved, restorable }
}
