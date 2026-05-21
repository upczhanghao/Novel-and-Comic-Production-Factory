<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { useWorkshopState } from '@/composables/useWorkshopState'
import { xpPresetsApi } from '@/api/client'

const props = defineProps<{ state: ReturnType<typeof useWorkshopState> }>()

// A6: 命名片段（曾名 XP 预设）的 CRUD 已移到 /profile「命名片段」tab。
// 此处只保留选择器；点击「管理片段」跳转 ProfileView。
type Snippet = { name: string; content: string }
const snippets = ref<Snippet[]>([])

function syncXpTypeFromSelection() {
  const parts: string[] = []
  for (const name of props.state.xpSelectedPresets.value) {
    const s = snippets.value.find(p => p.name === name)
    if (s) parts.push(`【${s.name}】\n${s.content}`)
  }
  props.state.xpType.value = parts.join('\n\n')
}

function toggleSnippet(name: string) {
  const list = props.state.xpSelectedPresets.value
  const idx = list.indexOf(name)
  if (idx >= 0) list.splice(idx, 1)
  else list.push(name)
  syncXpTypeFromSelection()
}

async function loadSnippets() {
  try {
    const res = await xpPresetsApi.list()
    snippets.value = res.data.presets
    if (props.state.xpSelectedPresets.value.length) syncXpTypeFromSelection()
  } catch { /* ignore */ }
}

onMounted(loadSnippets)
</script>

<template>
  <div class="rounded-xl border border-[var(--color-parchment-darker)] bg-white p-5 space-y-4">
    <h3 class="font-semibold text-[var(--color-leather)]">基础参数</h3>
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <div>
        <label class="block text-xs text-[var(--color-ink-light)] mb-1">LLM 配置</label>
        <select v-model="state.llmConfig.value" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm">
          <option v-for="c in state.configStore.llmChoices" :key="c" :value="c">{{ c }}</option>
        </select>
      </div>
      <div>
        <label class="block text-xs text-[var(--color-ink-light)] mb-1">Embedding 配置</label>
        <select v-model="state.embConfig.value" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm">
          <option v-for="c in state.configStore.embeddingChoices" :key="c" :value="c">{{ c }}</option>
        </select>
      </div>
      <div>
        <label class="block text-xs text-[var(--color-ink-light)] mb-1">题材/主题</label>
        <input v-model="state.topic.value" placeholder="请输入小说主题…" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm" />
      </div>
      <div>
        <label class="block text-xs text-[var(--color-ink-light)] mb-1">类型</label>
        <input v-model="state.genre.value" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm" />
      </div>
      <div>
        <label class="block text-xs text-[var(--color-ink-light)] mb-1">章节数</label>
        <input v-model.number="state.numChapters.value" type="number" min="1" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm" />
      </div>
      <div>
        <label class="block text-xs text-[var(--color-ink-light)] mb-1">每章字数</label>
        <input v-model.number="state.wordNumber.value" type="number" min="500" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm" />
      </div>

      <!-- XP 类型/核心玩法 -->
      <div class="sm:col-span-2 space-y-2">
        <div class="flex items-center justify-between">
          <label class="block text-xs text-[var(--color-ink-light)]">XP类型/核心玩法（可多选）</label>
          <router-link to="/profile?tab=snippets" class="text-xs text-blue-600 hover:text-blue-800">管理片段 →</router-link>
        </div>

        <!-- 预设选择区 -->
        <div v-if="snippets.length" class="flex flex-wrap gap-2">
          <label
            v-for="s in snippets" :key="s.name"
            class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm cursor-pointer transition-colors border"
            :class="state.xpSelectedPresets.value.includes(s.name)
              ? 'bg-blue-50 border-blue-300 text-blue-700'
              : 'bg-white border-[var(--color-parchment-darker)] text-[var(--color-ink-light)] hover:border-blue-200'"
            :title="s.content"
          >
            <input
              type="checkbox"
              :checked="state.xpSelectedPresets.value.includes(s.name)"
              @change="toggleSnippet(s.name)"
              class="sr-only"
            />
            <span>{{ s.name }}</span>
          </label>
        </div>
        <p v-else class="text-xs text-[var(--color-ink-light)]">
          暂无命名片段。<router-link to="/profile?tab=snippets" class="text-blue-600 hover:underline">前往「用户画像 → 命名片段」</router-link> 创建，或在下方直接输入。
        </p>

        <!-- 合并结果预览/手动编辑 -->
        <details class="text-sm">
          <summary class="text-xs text-[var(--color-ink-light)] cursor-pointer select-none">
            展开查看/手动编辑 XP 合并文本
          </summary>
          <textarea
            v-model="state.xpType.value"
            rows="3"
            placeholder="可留空，或选择上方片段自动填充"
            class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm resize-y mt-1"
          />
        </details>
      </div>

      <div class="sm:col-span-2">
        <label class="block text-xs text-[var(--color-ink-light)] mb-1">全局创作指导</label>
        <textarea v-model="state.userGuidance.value" rows="3" placeholder="整体写作风格、重点注意事项…" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm resize-y" />
      </div>
    </div>
  </div>
</template>
