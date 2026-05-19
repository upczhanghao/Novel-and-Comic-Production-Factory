import { defineStore } from 'pinia'
import { ref } from 'vue'
import { configApi } from '@/api/client'

export const useConfigStore = defineStore('config', () => {
  const llmConfigs = ref<Record<string, Record<string, unknown>>>({})
  const llmChoices = ref<string[]>([])
  const embeddingConfigs = ref<Record<string, Record<string, unknown>>>({})
  const embeddingChoices = ref<string[]>([])
  const imageConfigs = ref<Record<string, Record<string, unknown>>>({})
  const imageChoices = ref<string[]>([])

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

  async function loadAll() {
    const [llm, emb, image] = await Promise.all([
      configApi.listLLM(),
      configApi.listEmbedding(),
      configApi.listImage(),
    ])
    llmConfigs.value = sanitizeConfigMap(llm.data.configs)
    llmChoices.value = sanitizeChoices(llm.data.choices).filter((name) => name in llmConfigs.value)
    embeddingConfigs.value = sanitizeConfigMap(emb.data.configs)
    embeddingChoices.value = sanitizeChoices(emb.data.choices).filter((name) => name in embeddingConfigs.value)
    imageConfigs.value = sanitizeConfigMap(image.data.configs)
    imageChoices.value = sanitizeChoices(image.data.choices).filter((name) => name in imageConfigs.value)
  }

  return {
    llmConfigs,
    llmChoices,
    embeddingConfigs,
    embeddingChoices,
    imageConfigs,
    imageChoices,
    loadAll,
  }
})
