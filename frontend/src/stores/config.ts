import { defineStore } from 'pinia'
import { ref } from 'vue'
import { configApi } from '@/api/client'

export const LLM_DEFAULT_SLOTS = [
  { key: 'architecture_llm', label: '架构生成' },
  { key: 'chapter_outline_llm', label: '章节细纲' },
  { key: 'final_chapter_llm', label: '章节定稿' },
  { key: 'consistency_review_llm', label: '一致性审查' },
  { key: 'prompt_draft_llm', label: '提示词草稿' },
] as const

export type LLMDefaultSlot = typeof LLM_DEFAULT_SLOTS[number]['key']

export const useConfigStore = defineStore('config', () => {
  const llmConfigs = ref<Record<string, Record<string, unknown>>>({})
  const llmChoices = ref<string[]>([])
  const llmDefaults = ref<Record<string, string>>({})
  const embeddingConfigs = ref<Record<string, Record<string, unknown>>>({})
  const embeddingChoices = ref<string[]>([])
  const embeddingDefault = ref<string>('')
  const imageConfigs = ref<Record<string, Record<string, unknown>>>({})
  const imageChoices = ref<string[]>([])
  const imageDefault = ref<string>('')

  function sanitizeConfigMap(input: Record<string, Record<string, unknown>>) {
    const entries = Object.entries(input || {}).filter(([name]) => Boolean((name || '').trim()))
    return Object.fromEntries(entries)
  }

  function sanitizeChoices(input: string[]) {
    const seen = new Set<string>()
    const out: string[] = []
    for (const name of input || []) {
      const trimmed = (name || '').trim()
      if (!trimmed || seen.has(trimmed)) continue
      seen.add(trimmed)
      out.push(trimmed)
    }
    return out
  }

  function pruneHealth(type: 'llm' | 'embedding' | 'image', validNames: string[]) {
    const key = `nw_config_health_${type}`
    try {
      const raw = localStorage.getItem(key)
      if (!raw) return
      const data = JSON.parse(raw) as Record<string, unknown>
      const valid = new Set(validNames)
      let changed = false
      for (const k of Object.keys(data)) {
        if (!valid.has(k)) { delete data[k]; changed = true }
      }
      if (changed) localStorage.setItem(key, JSON.stringify(data))
    } catch { /* ignore */ }
  }

  async function loadAll() {
    const [llm, emb, image] = await Promise.all([
      configApi.listLLM(),
      configApi.listEmbedding(),
      configApi.listImage(),
    ])
    llmConfigs.value = sanitizeConfigMap(llm.data.configs)
    llmChoices.value = sanitizeChoices(llm.data.choices).filter((name) => name in llmConfigs.value)
    llmDefaults.value = (llm.data.choose ?? {}) as Record<string, string>
    embeddingConfigs.value = sanitizeConfigMap(emb.data.configs)
    embeddingChoices.value = sanitizeChoices(emb.data.choices).filter((name) => name in embeddingConfigs.value)
    embeddingDefault.value = String(emb.data.default ?? '')
    imageConfigs.value = sanitizeConfigMap(image.data.configs)
    imageChoices.value = sanitizeChoices(image.data.choices).filter((name) => name in imageConfigs.value)
    imageDefault.value = String(image.data.default ?? '')

    pruneHealth('llm', llmChoices.value)
    pruneHealth('embedding', embeddingChoices.value)
    pruneHealth('image', imageChoices.value)
  }

  function isSkeleton(type: 'llm' | 'embedding' | 'image', name: string): boolean {
    const map = type === 'llm' ? llmConfigs.value : type === 'embedding' ? embeddingConfigs.value : imageConfigs.value
    const c = map[name]
    if (!c) return false
    const apiKey = String(c.api_key ?? '')
    const model = String(c.model_name ?? c.model ?? '')
    return !apiKey.trim() && !model.trim()
  }

  return {
    llmConfigs,
    llmChoices,
    llmDefaults,
    embeddingConfigs,
    embeddingChoices,
    embeddingDefault,
    imageConfigs,
    imageChoices,
    imageDefault,
    loadAll,
    isSkeleton,
  }
})
