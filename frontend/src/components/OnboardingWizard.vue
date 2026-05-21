<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import { useConfigStore } from '@/stores/config'
import { useUIStore } from '@/stores/ui'
import { useFeedbackStore } from '@/stores/feedback'
import { presetsApi } from '@/api/client'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const projectStore = useProjectStore()
const configStore = useConfigStore()
const uiStore = useUIStore()
const feedback = useFeedbackStore()
const router = useRouter()

const step = ref(1)
const presets = ref<string[]>([])
const activePreset = ref('')
const newProjectName = ref('')
const newProjectPath = ref('')
const creating = ref(false)

const hasLLM = computed(() => configStore.llmChoices.length > 0 || Object.keys(configStore.llmConfigs).length > 0)
const hasProject = computed(() => projectStore.projects.length > 0)
const hasPreset = computed(() => !!activePreset.value)

const canFinish = computed(() => hasLLM.value && hasProject.value)

const missingChecks = computed(() => {
  const out: string[] = []
  if (!hasLLM.value) out.push('LLM 配置')
  if (!hasProject.value) out.push('至少 1 个项目')
  return out
})

onMounted(async () => {
  await configStore.loadAll()
  await projectStore.loadProjects()
  try {
    const res = await presetsApi.list()
    presets.value = res.data.presets ?? []
    activePreset.value = res.data.active ?? ''
  } catch { /* ignore */ }
})

function nextStep() { if (step.value < 3) step.value += 1 }
function prevStep() { if (step.value > 1) step.value -= 1 }

async function createProject() {
  if (!newProjectName.value.trim()) return
  creating.value = true
  try {
    await projectStore.createProject(newProjectName.value.trim(), newProjectPath.value.trim())
    feedback.success(`项目「${newProjectName.value}」已创建`)
    newProjectName.value = ''
    newProjectPath.value = ''
  } catch (e) {
    feedback.error('创建项目失败', (e as Error).message)
  } finally {
    creating.value = false
  }
}

async function activatePreset(name: string) {
  try {
    await presetsApi.activate(name)
    activePreset.value = name
    feedback.success(`已激活提示词方案「${name}」`)
  } catch (e) {
    feedback.error('激活提示词方案失败', (e as Error).message)
  }
}

function finish() {
  uiStore.completeOnboarding()
  emit('close')
  feedback.success('欢迎进入工作台，开始你的创作之旅')
}

function skip() {
  uiStore.completeOnboarding()
  emit('close')
}

function goConfig() {
  emit('close')
  uiStore.completeOnboarding()
  router.push('/config')
}
</script>

<template>
  <Teleport to="body">
    <div v-if="props.open" class="onb-mask" @click.self="skip">
      <div class="onb-modal">
        <header class="onb-header">
          <div>
            <div class="onb-kicker">首次设置</div>
            <h2>欢迎使用 Storia</h2>
            <p>三步完成基础配置，进入工作台</p>
          </div>
          <button class="onb-skip" @click="skip" type="button">跳过</button>
        </header>

        <div class="onb-progress">
          <div class="onb-step" :class="{ active: step >= 1, done: step > 1 }"><span>1</span>模型配置</div>
          <div class="onb-step" :class="{ active: step >= 2, done: step > 2 }"><span>2</span>创建项目</div>
          <div class="onb-step" :class="{ active: step >= 3 }"><span>3</span>提示词方案</div>
        </div>

        <main class="onb-body">
          <section v-if="step === 1">
            <h3>步骤 1：模型配置</h3>
            <p class="onb-tip">三类模型：<strong>LLM</strong>（写作必需）、<strong>Embedding</strong>（知识检索可选）、<strong>图片</strong>（漫剧/插图可选）。至少配置一个 LLM 才能开始创作；Embedding/图片可后续添加，但跳过会导致对应模块不可用。</p>
            <ul class="onb-status">
              <li :class="{ ok: hasLLM }">
                <span>LLM 配置 <span class="onb-req">必需</span></span>
                <strong>{{ hasLLM ? `${Object.keys(configStore.llmConfigs).length} 个已配置` : '尚未配置' }}</strong>
              </li>
              <li :class="{ ok: configStore.embeddingChoices.length > 0 }">
                <span>Embedding 配置 <span class="onb-opt">可选</span></span>
                <strong>{{ configStore.embeddingChoices.length > 0 ? '已配置' : '未配置（知识库功能不可用）' }}</strong>
              </li>
              <li :class="{ ok: configStore.imageChoices.length > 0 }">
                <span>图片配置 <span class="onb-opt">可选</span></span>
                <strong>{{ configStore.imageChoices.length > 0 ? '已配置' : '未配置（漫剧生图不可用）' }}</strong>
              </li>
            </ul>
            <button class="onb-link" @click="goConfig" type="button">前往模型配置 →</button>
          </section>

          <section v-if="step === 2">
            <h3>步骤 2：创建或选择项目</h3>
            <p class="onb-tip">每个项目有独立的输出目录与配置，所有章节、漫剧数据都按项目保存。</p>
            <div v-if="hasProject" class="onb-projects">
              <div class="onb-existing">已有项目：</div>
              <select :value="projectStore.activeProject"
                @change="projectStore.activateProject(($event.target as HTMLSelectElement).value)">
                <option v-for="p in projectStore.projects" :key="p" :value="p">{{ p }}</option>
              </select>
            </div>
            <div class="onb-form">
              <input v-model="newProjectName" placeholder="新项目名称" />
              <input v-model="newProjectPath" placeholder="输出路径（可选，默认 ./output/项目名）" />
              <button class="btn-primary" :disabled="!newProjectName.trim() || creating" @click="createProject" type="button">
                {{ creating ? '创建中…' : '创建项目' }}
              </button>
            </div>
          </section>

          <section v-if="step === 3">
            <h3>步骤 3：选择提示词方案</h3>
            <p class="onb-tip">提示词方案决定了小说的创作风格基线。可后续在「提示词方案」页切换。</p>
            <div class="onb-presets">
              <button
                v-for="p in presets"
                :key="p"
                class="onb-preset"
                :class="{ active: p === activePreset }"
                @click="activatePreset(p)"
                type="button"
              >{{ p }}</button>
            </div>
            <p v-if="!presets.length" class="onb-empty">未发现提示词方案。可以稍后在 prompts/ 目录添加。</p>
          </section>
        </main>

        <footer class="onb-footer">
          <button class="btn-ghost" :disabled="step === 1" @click="prevStep" type="button">上一步</button>
          <div class="onb-spacer" />
          <button v-if="step < 3" class="btn-primary" @click="nextStep" type="button">下一步</button>
          <div v-else class="onb-finish-group">
            <span v-if="!canFinish" class="onb-missing">还需：{{ missingChecks.join('、') }}</span>
            <button class="btn-primary" :disabled="!canFinish" @click="finish" type="button">进入工作台</button>
          </div>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.onb-mask { position: fixed; inset: 0; background: rgba(9, 9, 11, 0.6); backdrop-filter: blur(8px); display: flex; align-items: center; justify-content: center; z-index: 50; padding: 1rem; }
.onb-modal { width: min(640px, 100%); background: var(--color-surface); border-radius: 16px; box-shadow: 0 25px 50px rgba(0, 0, 0, 0.25); display: flex; flex-direction: column; max-height: 90vh; }
.onb-header { display: flex; align-items: flex-start; justify-content: space-between; padding: 1.5rem 1.5rem 1rem; }
.onb-kicker { font-size: 11px; letter-spacing: 0.18em; text-transform: uppercase; color: var(--color-ink-light); margin-bottom: 4px; }
.onb-header h2 { font-size: 1.25rem; font-weight: 700; margin: 0; }
.onb-header p { margin: 4px 0 0; color: var(--color-ink-light); font-size: 0.875rem; }
.onb-skip { background: transparent; border: 1px solid var(--color-control-border); border-radius: 6px; padding: 4px 10px; font-size: 12px; color: var(--color-ink-light); }
.onb-progress { display: flex; gap: 0.5rem; padding: 0 1.5rem 1rem; border-bottom: 1px solid var(--color-control-border); }
.onb-step { flex: 1; display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--color-ink-light); padding: 6px 8px; border-radius: 6px; background: var(--color-surface-muted); }
.onb-step span { width: 20px; height: 20px; border-radius: 50%; background: var(--color-control-border); display: inline-flex; align-items: center; justify-content: center; font-weight: 600; color: white; }
.onb-step.active { color: var(--color-ink); background: var(--color-gold-light); }
.onb-step.active span { background: var(--color-gold); }
.onb-step.done span { background: var(--color-success); }
.onb-body { padding: 1.5rem; overflow-y: auto; flex: 1; }
.onb-body h3 { margin: 0 0 4px; font-size: 1rem; font-weight: 600; }
.onb-tip { color: var(--color-ink-light); font-size: 0.875rem; margin: 0 0 1rem; }
.onb-status { list-style: none; padding: 0; margin: 0 0 1rem; display: flex; flex-direction: column; gap: 8px; }
.onb-status li { display: flex; justify-content: space-between; padding: 10px 12px; background: var(--color-surface-muted); border-radius: 8px; font-size: 0.875rem; }
.onb-status li.ok { background: #ecfdf5; color: #065f46; }
.onb-status li strong { font-weight: 600; }
.onb-req { font-size: 10px; padding: 1px 6px; border-radius: 999px; background: #fee2e2; color: #b91c1c; margin-left: 4px; }
.onb-opt { font-size: 10px; padding: 1px 6px; border-radius: 999px; background: var(--color-surface-muted); color: var(--color-ink-light); margin-left: 4px; }
.onb-link { background: transparent; color: var(--color-leather-light); font-weight: 500; padding: 0; border: 0; }
.onb-projects { margin-bottom: 1rem; }
.onb-existing { font-size: 0.875rem; color: var(--color-ink-light); margin-bottom: 4px; }
.onb-projects select { width: 100%; padding: 8px 12px; }
.onb-form { display: flex; flex-direction: column; gap: 8px; }
.onb-form input { padding: 8px 12px; }
.onb-presets { display: flex; flex-wrap: wrap; gap: 8px; }
.onb-preset { padding: 8px 14px; border-radius: 999px; border: 1px solid var(--color-control-border); background: var(--color-surface-muted); font-size: 13px; }
.onb-preset.active { background: var(--color-gold); color: white; border-color: var(--color-gold-dark); }
.onb-empty { color: var(--color-ink-light); font-size: 0.875rem; }
.onb-footer { display: flex; padding: 1rem 1.5rem; border-top: 1px solid var(--color-control-border); gap: 8px; }
.onb-spacer { flex: 1; }
.btn-primary { background: var(--color-ink); color: white; padding: 8px 16px; border-radius: 8px; font-weight: 500; border: 0; }
.btn-primary:disabled { opacity: 0.4; }
.btn-ghost { background: transparent; border: 1px solid var(--color-control-border); padding: 8px 16px; border-radius: 8px; }
.btn-ghost:disabled { opacity: 0.4; }
.onb-finish-group { display: flex; align-items: center; gap: 10px; }
.onb-missing { font-size: 11px; color: #b91c1c; background: #fee2e2; padding: 3px 8px; border-radius: 999px; }
</style>
