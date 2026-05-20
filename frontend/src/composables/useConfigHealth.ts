import { ref, computed, type ComputedRef } from 'vue'

export type HealthStatus = 'untested' | 'ok' | 'fail'

export interface HealthRecord {
  status: HealthStatus
  lastTestedAt: string
  lastMessage: string
}

const DEFAULT_HEALTH: HealthRecord = { status: 'untested', lastTestedAt: '', lastMessage: '' }

export type ConfigKind = 'llm' | 'embedding' | 'image'

const cache: Record<ConfigKind, ReturnType<typeof createStore>> = {
  llm: undefined as never,
  embedding: undefined as never,
  image: undefined as never,
}

function storageKey(kind: ConfigKind) {
  return `nw_config_health_${kind}`
}

function createStore(kind: ConfigKind) {
  const data = ref<Record<string, HealthRecord>>(load(kind))

  function persist() {
    try { localStorage.setItem(storageKey(kind), JSON.stringify(data.value)) } catch { /* ignore */ }
  }

  function get(name: string): HealthRecord {
    return data.value[name] ?? { ...DEFAULT_HEALTH }
  }

  function set(name: string, record: HealthRecord) {
    data.value = { ...data.value, [name]: record }
    persist()
  }

  function markOk(name: string, message = '连通性测试成功') {
    set(name, { status: 'ok', lastTestedAt: new Date().toISOString(), lastMessage: message })
  }

  function markFail(name: string, message: string) {
    set(name, { status: 'fail', lastTestedAt: new Date().toISOString(), lastMessage: message })
  }

  const all: ComputedRef<Record<string, HealthRecord>> = computed(() => data.value)

  return { get, set, markOk, markFail, all }
}

function load(kind: ConfigKind): Record<string, HealthRecord> {
  try {
    const raw = localStorage.getItem(storageKey(kind))
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    if (parsed && typeof parsed === 'object') return parsed as Record<string, HealthRecord>
  } catch { /* ignore */ }
  return {}
}

export function useConfigHealth(kind: ConfigKind) {
  if (!cache[kind]) cache[kind] = createStore(kind)
  return cache[kind]
}

export function relativeTestTime(iso: string): string {
  if (!iso) return '从未测试'
  const d = new Date(iso).getTime()
  if (!Number.isFinite(d)) return iso
  const diff = (Date.now() - d) / 1000
  if (diff < 60) return '刚刚测试'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前测试`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前测试`
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} 天前测试`
  return new Date(iso).toLocaleDateString() + ' 测试'
}

export function statusIcon(s: HealthStatus): string {
  return s === 'ok' ? '🟢' : s === 'fail' ? '🔴' : '⚪'
}
