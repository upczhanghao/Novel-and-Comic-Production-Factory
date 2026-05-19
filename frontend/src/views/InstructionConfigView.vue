<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { configApi } from '@/api/client'

type InstructionTemplate = {
  key: string
  title: string
  description: string
  content: string
  variables: string[]
  customized: boolean
}

const templates = ref<Record<string, InstructionTemplate>>({})
const selectedKey = ref('')
const editorContent = ref('')
const loading = ref(false)
const saving = ref(false)
const statusMsg = ref('')

const orderedTemplates = computed(() => Object.values(templates.value))
const selectedTemplate = computed(() => templates.value[selectedKey.value])
const hasChanges = computed(() => Boolean(selectedTemplate.value && editorContent.value !== selectedTemplate.value.content))

async function loadTemplates() {
  loading.value = true
  try {
    const res = await configApi.listManjuInstructions()
    templates.value = res.data.templates ?? {}
    if (!selectedKey.value || !templates.value[selectedKey.value]) {
      selectedKey.value = orderedTemplates.value[0]?.key ?? ''
    }
    editorContent.value = selectedTemplate.value?.content ?? ''
  } catch (e: unknown) {
    statusMsg.value = `❌ ${(e as Error).message}`
  } finally {
    loading.value = false
  }
}

function selectTemplate(key: string) {
  selectedKey.value = key
  editorContent.value = templates.value[key]?.content ?? ''
}

async function saveTemplate() {
  if (!selectedTemplate.value) return
  saving.value = true
  try {
    const res = await configApi.saveManjuInstruction(selectedKey.value, editorContent.value)
    templates.value = res.data.templates ?? templates.value
    editorContent.value = templates.value[selectedKey.value]?.content ?? editorContent.value
    statusMsg.value = res.data.message
  } catch (e: unknown) {
    statusMsg.value = `❌ ${(e as Error).message}`
  } finally {
    saving.value = false
  }
}

async function resetTemplate() {
  if (!selectedTemplate.value) return
  saving.value = true
  try {
    const res = await configApi.resetManjuInstruction(selectedKey.value)
    templates.value = res.data.templates ?? templates.value
    editorContent.value = res.data.content ?? templates.value[selectedKey.value]?.content ?? ''
    statusMsg.value = res.data.message
  } catch (e: unknown) {
    statusMsg.value = `❌ ${(e as Error).message}`
  } finally {
    saving.value = false
  }
}

onMounted(loadTemplates)
</script>

<template>
  <div class="module-page space-y-5">
    <div class="module-toolbar">
      <div>
        <h2 class="text-2xl font-bold" style="color: var(--color-ink)">指令配置</h2>
        <div class="module-kicker">Instruction Lab</div>
        <p class="module-subtitle">
          漫剧制作模块发送给 AI 的核心指令模板，可手动调整并随时恢复默认。
        </p>
      </div>
      <router-link to="/manju" class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm hover:bg-white transition-colors">
        返回漫剧制作
      </router-link>
    </div>

    <Transition name="fade">
      <div
        v-if="statusMsg"
        class="px-4 py-2 rounded-md text-sm"
        :class="statusMsg.startsWith('✅') ? 'bg-green-50 text-green-800 border border-green-200' : 'bg-red-50 text-red-800 border border-red-200'"
      >
        {{ statusMsg }}
      </div>
    </Transition>

    <section class="module-grid">
      <aside class="module-panel overflow-hidden module-aside-sticky">
        <div class="module-panel-header">
          <h3 class="module-panel-title">漫剧指令模板</h3>
          <button @click="loadTemplates" :disabled="loading" class="px-2 py-1 rounded border border-[var(--color-parchment-darker)] text-xs disabled:opacity-50" type="button">
            {{ loading ? '加载中' : '刷新' }}
          </button>
        </div>
        <div class="p-3 space-y-2 max-h-[680px] overflow-auto">
          <button
            v-for="item in orderedTemplates"
            :key="item.key"
            @click="selectTemplate(item.key)"
            class="w-full text-left module-list-item px-3 py-2"
            :class="selectedKey === item.key ? 'active' : ''"
            type="button"
          >
            <div class="flex items-center justify-between gap-2">
              <span class="text-sm font-semibold text-[var(--color-ink)] truncate">{{ item.title }}</span>
              <span v-if="item.customized" class="shrink-0 text-[10px] text-green-700 bg-green-50 border border-green-100 rounded px-1.5 py-0.5">已自定义</span>
            </div>
            <div class="text-xs text-[var(--color-ink-light)] mt-1 line-clamp-2">{{ item.description }}</div>
          </button>
        </div>
      </aside>

      <main class="module-panel overflow-hidden">
        <div class="module-panel-header">
          <div class="flex items-center justify-between gap-3 flex-wrap">
            <div>
              <h3 class="module-panel-title">{{ selectedTemplate?.title || '请选择模板' }}</h3>
              <p v-if="selectedTemplate" class="text-xs text-[var(--color-ink-light)] mt-1">{{ selectedTemplate.description }}</p>
            </div>
            <div class="flex gap-2">
              <button
                @click="resetTemplate"
                :disabled="saving || !selectedTemplate"
                class="px-3 py-2 rounded-md border border-[var(--color-parchment-darker)] text-sm hover:bg-white disabled:opacity-50"
                type="button"
              >
                恢复默认
              </button>
              <button
                @click="saveTemplate"
                :disabled="saving || !selectedTemplate || !hasChanges"
                class="px-5 py-2 rounded-md text-sm font-semibold disabled:opacity-50"
                style="background-color: var(--color-leather); color: var(--color-parchment)"
                type="button"
              >
                {{ saving ? '保存中...' : '保存模板' }}
              </button>
            </div>
          </div>
        </div>

        <div v-if="selectedTemplate" class="p-5 space-y-4">
          <div>
            <label class="block text-xs text-[var(--color-ink-light)] mb-1">可用占位符</label>
            <div class="flex flex-wrap gap-1.5">
              <code
                v-for="variable in selectedTemplate.variables"
                :key="variable"
                class="px-2 py-1 rounded border border-[var(--color-parchment-darker)] bg-[var(--color-parchment)] text-xs"
              >
                {{ '{' + variable + '}' }}
              </code>
            </div>
          </div>

          <div>
            <label class="block text-xs text-[var(--color-ink-light)] mb-1">指令内容</label>
            <textarea
              v-model="editorContent"
              spellcheck="false"
              class="w-full min-h-[560px] border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm resize-y font-mono leading-6"
            />
          </div>
        </div>

        <div v-else class="p-8 text-sm text-[var(--color-ink-light)]">
          暂无可配置指令模板。
        </div>
      </main>
    </section>
  </div>
</template>
