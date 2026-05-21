<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import { useFeedbackStore } from '@/stores/feedback'

const projectStore = useProjectStore()
const feedback = useFeedbackStore()
const router = useRouter()

const newName = ref('')
const newPath = ref('')
const creating = ref(false)
const target = ref('/')

const hasProjects = computed(() => projectStore.projects.length > 0)

onMounted(async () => {
  const params = new URLSearchParams(window.location.search)
  target.value = params.get('to') || '/'
  await projectStore.loadProjects()
})

async function pick(name: string) {
  await projectStore.activateProject(name)
  feedback.success(`已切换到「${name}」`)
  router.push(target.value)
}

async function create() {
  if (!newName.value.trim()) return
  creating.value = true
  try {
    await projectStore.createProject(newName.value.trim(), newPath.value.trim())
    feedback.success(`项目「${newName.value}」已创建`)
    router.push(target.value)
  } catch (e) {
    feedback.error('创建项目失败', (e as Error).message)
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <div class="module-page np-page">
    <div class="np-card">
      <div class="np-kicker">需要项目</div>
      <h2>请选择或创建一个项目</h2>
      <p class="np-tip">
        当前模块需要一个激活的项目才能使用。每个项目有独立的输出目录与配置。
        <router-link to="/config" class="np-link">模型配置</router-link>
        模块不需要项目即可访问。
      </p>

      <section v-if="hasProjects" class="np-section">
        <h3>已有项目</h3>
        <div class="np-list">
          <button v-for="p in projectStore.projects" :key="p" class="np-item" @click="pick(p)" type="button">
            {{ p }}
          </button>
        </div>
      </section>

      <section class="np-section">
        <h3>创建新项目</h3>
        <div class="np-form">
          <input v-model="newName" placeholder="项目名称" class="np-input" />
          <input v-model="newPath" placeholder="输出路径（可选，默认 ./output/项目名）" class="np-input" />
          <button class="np-btn" :disabled="!newName.trim() || creating" @click="create" type="button">
            {{ creating ? '创建中…' : '创建并进入' }}
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.np-page { display: flex; align-items: center; justify-content: center; min-height: 60vh; padding: 2rem 1rem; }
.np-card { width: min(560px, 100%); background: var(--color-surface); border-radius: 14px; padding: 28px; box-shadow: 0 8px 32px rgba(0,0,0,0.08); border: 1px solid var(--color-control-border); }
.np-kicker { font-size: 11px; letter-spacing: 0.18em; text-transform: uppercase; color: var(--color-ink-light); margin-bottom: 4px; }
.np-card h2 { font-size: 1.35rem; font-weight: 700; margin: 0 0 8px; color: var(--color-ink); }
.np-tip { color: var(--color-ink-light); font-size: 0.875rem; margin: 0 0 20px; line-height: 1.6; }
.np-link { color: var(--color-leather-light); text-decoration: underline; }
.np-section { margin-top: 18px; }
.np-section h3 { font-size: 0.875rem; font-weight: 600; margin: 0 0 8px; color: var(--color-ink); }
.np-list { display: flex; flex-wrap: wrap; gap: 8px; }
.np-item { padding: 8px 14px; border-radius: 8px; border: 1px solid var(--color-control-border); background: white; cursor: pointer; font-size: 0.875rem; }
.np-item:hover { border-color: var(--color-leather-light); background: var(--color-surface-muted); }
.np-form { display: flex; flex-direction: column; gap: 8px; }
.np-input { padding: 8px 12px; border-radius: 6px; border: 1px solid var(--color-control-border); font-size: 0.875rem; }
.np-btn { padding: 8px 16px; border-radius: 8px; background: var(--color-ink); color: white; border: 0; font-weight: 500; cursor: pointer; }
.np-btn:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
