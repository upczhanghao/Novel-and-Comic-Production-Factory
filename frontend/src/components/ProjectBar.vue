<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useProjectStore } from '@/stores/project'
import { useConfigStore } from '@/stores/config'

const projectStore = useProjectStore()
const configStore = useConfigStore()

const showCreate = ref(false)
const newName = ref('')
const newPath = ref('')
const creating = ref(false)
const deleting = ref(false)
const discovering = ref(false)
const statusMsg = ref('')

onMounted(async () => {
  await Promise.all([
    projectStore.loadProjects(),
    projectStore.loadActive(),
    configStore.loadAll(),
  ])
})

async function onSelectProject(name: string) {
  if (!name || name === projectStore.activeProject) return
  try {
    await projectStore.activateProject(name)
    statusMsg.value = `已切换到「${name}」`
    setTimeout(() => (statusMsg.value = ''), 2000)
  } catch (e: unknown) {
    statusMsg.value = (e as Error).message
  }
}

async function onDelete() {
  const name = projectStore.activeProject
  if (!name) return
  if (!confirm(`确定要删除项目「${name}」吗？项目文件将被移至 trash 目录。`)) return
  deleting.value = true
  try {
    await projectStore.deleteProject(name)
    statusMsg.value = `已删除「${name}」`
    setTimeout(() => (statusMsg.value = ''), 2000)
  } catch (e: unknown) {
    statusMsg.value = (e as Error).message
  } finally {
    deleting.value = false
  }
}

async function onDiscover() {
  discovering.value = true
  try {
    const res = await projectStore.discoverProjects()
    statusMsg.value = res.message
    setTimeout(() => (statusMsg.value = ''), 3000)
  } catch (e: unknown) {
    statusMsg.value = (e as Error).message
  } finally {
    discovering.value = false
  }
}

async function onCreate() {
  if (!newName.value.trim()) return
  creating.value = true
  try {
    await projectStore.createProject(newName.value.trim(), newPath.value.trim())
    showCreate.value = false
    newName.value = ''
    newPath.value = ''
  } catch (e: unknown) {
    statusMsg.value = (e as Error).message
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <div class="project-bar">
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

    <button
      @click="showCreate = !showCreate"
      class="project-action"
      type="button"
    >
      新建
    </button>

    <button
      @click="onDiscover"
      :disabled="discovering"
      class="project-action"
      type="button"
      title="扫描 output 目录，自动发现并注册已有项目"
    >
      {{ discovering ? '扫描中...' : '发现' }}
    </button>

    <button
      v-if="projectStore.activeProject"
      @click="onDelete"
      :disabled="deleting"
      class="project-action danger"
      type="button"
    >
      {{ deleting ? '删除中...' : '删除项目' }}
    </button>

    <Transition name="slide">
      <div v-if="showCreate" class="project-create">
        <input
          v-model="newName"
          placeholder="项目名称"
        class="project-input"
        />
        <input
          v-model="newPath"
          placeholder="输出路径（可选）"
        class="project-input"
        />
        <button
          @click="onCreate"
          :disabled="creating"
          class="project-action primary"
          type="button"
        >
          {{ creating ? '创建中...' : '创建' }}
        </button>
        <button
          @click="showCreate = false"
          class="project-action"
          type="button"
        >
          取消
        </button>
      </div>
    </Transition>

    <Transition name="fade">
      <span v-if="statusMsg" class="project-status">{{ statusMsg }}</span>
    </Transition>
  </div>
</template>
