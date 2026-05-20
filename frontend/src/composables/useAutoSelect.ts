import { computed } from 'vue'
import { useConfigStore } from '@/stores/config'

export type ConfigKind = 'llm' | 'embedding' | 'image'

export interface AutoSelectResult {
  selected: string
  reason: string
}

export function useAutoSelect(kind: ConfigKind, preferred?: () => string | undefined) {
  const config = useConfigStore()

  const list = computed(() => {
    if (kind === 'llm') return config.llmChoices
    if (kind === 'embedding') return config.embeddingChoices
    return config.imageChoices
  })

  const all = computed(() => {
    if (kind === 'llm') return config.llmConfigs
    if (kind === 'embedding') return config.embeddingConfigs
    return config.imageConfigs
  })

  const result = computed<AutoSelectResult>(() => {
    const pref = preferred?.()
    if (pref && pref in all.value) return { selected: pref, reason: '' }

    if (list.value.length === 0) {
      if (Object.keys(all.value).length === 0) {
        return { selected: '', reason: `尚未添加任何${kindLabel(kind)}配置，请前往「模型配置」添加` }
      }
      return { selected: '', reason: `存在${kindLabel(kind)}配置但均未启用，请在「模型配置」勾选` }
    }

    const first = list.value[0]
    const entry = all.value[first] as Record<string, unknown> | undefined
    if (entry && !entry.api_key && kind !== 'embedding') {
      return { selected: first, reason: `已选「${first}」，但 API Key 为空，可能调用失败` }
    }
    return { selected: first, reason: '' }
  })

  return { selected: computed(() => result.value.selected), reason: computed(() => result.value.reason) }
}

function kindLabel(k: ConfigKind) {
  if (k === 'llm') return 'LLM'
  if (k === 'embedding') return 'Embedding'
  return '图片'
}
