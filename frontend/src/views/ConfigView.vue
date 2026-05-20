<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useConfigStore } from '@/stores/config'
import RecommendedTemplates from '@/components/config/RecommendedTemplates.vue'
import { type RecommendedTemplate } from '@/components/config/templates'
import LLMConfigPanel from '@/components/config/LLMConfigPanel.vue'
import EmbeddingConfigPanel from '@/components/config/EmbeddingConfigPanel.vue'
import ImageConfigPanel from '@/components/config/ImageConfigPanel.vue'
import ProxyConfigPanel from '@/components/config/ProxyConfigPanel.vue'

const configStore = useConfigStore()

const llmPreset = ref<Record<string, unknown> | null>(null)
const embPreset = ref<Record<string, unknown> | null>(null)
const imgPreset = ref<Record<string, unknown> | null>(null)

function applyTemplate(t: RecommendedTemplate) {
  if (t.kind === 'llm') llmPreset.value = { ...t.preset }
  else if (t.kind === 'embedding') embPreset.value = { ...t.preset }
  else imgPreset.value = { ...t.preset }
  document.getElementById(`config-${t.kind}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

onMounted(() => { configStore.loadAll() })
</script>

<template>
  <div class="module-page compact space-y-5">
    <div class="module-toolbar">
      <h2 class="text-2xl font-bold" style="color: var(--color-ink)">⚙️ 模型配置</h2>
      <div>
        <div class="module-kicker">Model Hub</div>
        <div class="module-subtitle">三类模型分组管理；每组顶部显示当前默认配置；测试通过后可一键设为默认。</div>
      </div>
    </div>

    <RecommendedTemplates @apply="applyTemplate" />

    <div id="config-llm">
      <LLMConfigPanel :pending-preset="llmPreset" @consumed="llmPreset = null" />
    </div>
    <div id="config-embedding">
      <EmbeddingConfigPanel :pending-preset="embPreset" @consumed="embPreset = null" />
    </div>
    <div id="config-image">
      <ImageConfigPanel :pending-preset="imgPreset" @consumed="imgPreset = null" />
    </div>

    <ProxyConfigPanel />
  </div>
</template>
