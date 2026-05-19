<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { postSSE } from '@/api/client'
import { useConfigStore } from '@/stores/config'
import { useProjectStore } from '@/stores/project'
import StreamOutput from '@/components/StreamOutput.vue'

const configStore = useConfigStore()
const projectStore = useProjectStore()
const llmConfig = ref('')
const chapterNum = ref(1)
const state = ref({ running: false, progress: '', result: '', error: '' })

function doCheck() {
  state.value = { running: true, progress: '', result: '', error: '' }
  postSSE(
    '/consistency/check',
    {
      llm_config_name: llmConfig.value,
      filepath: projectStore.filepath,
      chapter_num: chapterNum.value,
    },
    (msg) => { state.value.progress = msg },
    (content) => { state.value.result = content },
    (err) => { state.value.error = err; state.value.running = false },
    () => { state.value.running = false },
  )
}

onMounted(async () => {
  await Promise.all([configStore.loadAll(), projectStore.loadActive()])
  if (configStore.llmChoices.length) llmConfig.value = configStore.llmChoices[0]
})

watch(() => configStore.llmChoices.slice(), (choices) => {
  if (!choices.length) {
    llmConfig.value = ''
    return
  }
  if (!llmConfig.value || !choices.includes(llmConfig.value)) {
    llmConfig.value = choices[0]
  }
})
</script>

<template>
  <div class="module-page compact space-y-5">
    <h2 class="text-2xl font-bold" style="color: var(--color-ink)">🔍 一致性检查</h2>
    <div class="module-toolbar">
      <div>
        <div class="module-kicker">Continuity</div>
        <div class="module-subtitle">检查指定章节与架构、角色状态、全局摘要之间的一致性。</div>
      </div>
    </div>

    <div class="module-panel p-5 space-y-4">
      <div class="flex gap-4 flex-wrap">
        <div class="flex-1">
          <label class="block text-xs text-[var(--color-ink-light)] mb-1">LLM 配置</label>
          <select v-model="llmConfig" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm">
            <option v-for="c in configStore.llmChoices" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-[var(--color-ink-light)] mb-1">章节号</label>
          <input v-model.number="chapterNum" type="number" min="1" class="w-24 border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm" />
        </div>
      </div>
      <div class="flex justify-end">
        <button @click="doCheck" :disabled="state.running || !llmConfig"
          class="px-5 py-2 rounded-md text-sm font-semibold disabled:opacity-50" style="background-color: var(--color-leather); color: var(--color-parchment)" type="button">
          {{ state.running ? '检查中…' : '▶ 开始检查' }}
        </button>
      </div>
      <StreamOutput v-bind="state" placeholder="一致性检查结果将在此显示…" />
    </div>
  </div>
</template>
