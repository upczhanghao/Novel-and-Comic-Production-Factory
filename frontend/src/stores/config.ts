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

  async function loadAll() {
    const [llm, emb, image] = await Promise.all([
      configApi.listLLM(),
      configApi.listEmbedding(),
      configApi.listImage(),
    ])
    llmConfigs.value = llm.data.configs
    llmChoices.value = llm.data.choices
    embeddingConfigs.value = emb.data.configs
    embeddingChoices.value = emb.data.choices
    imageConfigs.value = image.data.configs
    imageChoices.value = image.data.choices
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
