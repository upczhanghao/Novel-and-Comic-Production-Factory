<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useProjectStore } from '@/stores/project'
import { useConfigStore } from '@/stores/config'
import { useFeedbackStore } from '@/stores/feedback'

const projectStore = useProjectStore()
const configStore = useConfigStore()
const feedback = useFeedbackStore()

const showCreate = ref(false)
const newName = ref('')
const newPath = ref('')
const creating = ref(false)
const deleting = ref(false)
const discovering = ref(false)
const saveStatus = ref<'idle' | 'saving' | 'saved' | 'error'>('idle')

const filepath = computed(() => projectStore.activeProjectData?.filepath ?? '')
const updatedAt = computed(() => projectStore.activeProjectData?.updated_at ?? '')

function formatDate(s?: string) {
  if (!s) return '—'
  const d = new Date(s)
  if (isNaN(d.getTime())) return s
  const diff = (Date.now() - d.getTime()) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} 天前`
  return d.toLocaleDateString()
}

onMounted(async () => {
  await Promise.all([projectStore.loadProjects(), projectStore.loadActive(), configStore.loadAll()])
})

async function onSelectProject(name: string) {
  if (!name || name === projectStore.activeProject) return
  saveStatus.value = 'saving'
  try {
    await projectStore.activateProject(name)
    saveStatus.value = 'saved'
    feedback.info(`已切换到「${name}」，正在加载内容…`)
    setTimeout(() => (saveStatus.value = 'idle'), 1500)
  } catch (e) {
    saveStatus.value = 'error'
    feedback.error('切换项目失败', (e as Error).message)
  }
}

async function copyPath() {
  if (!filepath.value) return
  try {
    await navigator.clipboard.writeText(filepath.value)
    feedback.info('项目路径已复制')
  } catch {
    feedback.warning('无法访问剪贴板')
  }
}

async function onDelete() {
  const name = projectStore.activeProject
  if (!name) return
  if (!confirm(`确定要删除项目「${name}」吗？项目文件将被移至 trash 目录。`)) return
  deleting.value = true
  try {
    await projectStore.deleteProject(name)
    feedback.success(`已删除项目「${name}」（已移至 trash，可手动恢复）`)
  } catch (e) {
    feedback.error('删除项目失败', (e as Error).message)
  } finally {
    deleting.value = false
  }
}

async function onDiscover() {
  discovering.value = true
  try {
    const res = await projectStore.discoverProjects()
    feedback.success(res.message || '已扫描')
  } catch (e) {
    feedback.error('扫描项目失败', (e as Error).message)
  } finally {
    discovering.value = false
  }
}

async function onCreate() {
  if (!newName.value.trim()) return
  creating.value = true
  try {
    await projectStore.createProject(newName.value.trim(), newPath.value.trim())
    feedback.success(`项目「${newName.value}」已创建`)
    showCreate.value = false
    newName.value = ''
    newPath.value = ''
  } catch (e) {
    feedback.error('创建项目失败', (e as Error).message)
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <div class="project-bar enhanced">
    <div class="pb-main">
      <div class="project-selector">
        <label class="project-label">当前项目</label>
        <select
          :value="projectStore.activeProject"
          @change="onSelectProject(($event.target as HTMLSelectElement).value)"
          class="project-select"
        >
          <option value="" disabled>— 选择项目 —</option>
          <option v-for="p in projectStore.projects" :key="p" :value="p">{{ p }}</option>
        </select>
      </div>

      <div v-if="filepath" class="pb-meta">
        <button class="pb-path" :title="filepath" @click="copyPath" type="button">
          <span class="pb-icon">📁</span>
          <span class="pb-path-text">{{ filepath }}</span>
        </button>
        <span class="pb-divider">·</span>
        <span class="pb-saved" :class="saveStatus">
          <span class="pb-dot" />
          <span v-if="saveStatus === 'saving'">保存中…</span>
          <span v-else-if="saveStatus === 'saved'">已保存</span>
          <span v-else-if="saveStatus === 'error'">保存失败</span>
          <span v-else>已同步</span>
        </span>
        <span class="pb-divider">·</span>
        <span class="pb-updated">更新 {{ formatDate(updatedAt) }}</span>
      </div>

      <div class="pb-actions">
        <button @click="showCreate = !showCreate" class="project-action" type="button">新建</button>
        <button @click="onDiscover" :disabled="discovering" class="project-action" type="button"
          title="扫描 output 目录，自动发现并注册已有项目">
          {{ discovering ? '扫描中...' : '发现' }}
        </button>
        <button v-if="projectStore.activeProject" @click="onDelete" :disabled="deleting"
          class="project-action danger" type="button">
          {{ deleting ? '删除中...' : '删除' }}
        </button>
      </div>
    </div>

    <Transition name="slide">
      <div v-if="showCreate" class="project-create">
        <input v-model="newName" placeholder="项目名称" class="project-input" />
        <input v-model="newPath" placeholder="输出路径（可选）" class="project-input" />
        <button @click="onCreate" :disabled="creating" class="project-action primary" type="button">
          {{ creating ? '创建中...' : '创建' }}
        </button>
        <button @click="showCreate = false" class="project-action" type="button">取消</button>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.project-bar.enhanced { display: flex; flex-direction: column; gap: 6px; }
.pb-main { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }
.pb-meta { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--color-ink-light); flex: 1; min-width: 0; }
.pb-path { display: inline-flex; align-items: center; gap: 4px; max-width: 320px; padding: 4px 8px; border-radius: 6px; background: var(--color-surface-muted); border: 1px solid var(--color-control-border); color: var(--color-ink-light); cursor: pointer; transition: background 0.15s; }
.pb-path:hover { background: var(--color-parchment-darker); color: var(--color-ink); }
.pb-path-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: var(--font-mono); font-size: 11px; }
.pb-icon { font-size: 11px; }
.pb-divider { opacity: 0.4; }
.pb-saved { display: inline-flex; align-items: center; gap: 4px; }
.pb-saved .pb-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--color-success); }
.pb-saved.saving .pb-dot { background: var(--color-warning); animation: pulse 1s infinite; }
.pb-saved.error .pb-dot { background: var(--color-error); }
.pb-actions { display: flex; gap: 6px; flex-shrink: 0; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
</style>
