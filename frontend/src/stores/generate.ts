import { defineStore } from 'pinia'
import { ref } from 'vue'
import { generateApi } from '@/api/client'
import { useProjectStore } from './project'

// M33: 与 generate 缓存关联的文件名（用于 FilesView 写入后判定是否需要刷新）
const TRACKED_FILES = [
  'Novel_architecture.txt',
  'Novel_directory.txt',
  'character_state.txt',
  'character_dynamics.json',
  'core_seed.txt',
  'world_building.txt',
  'plot_architecture.txt',
]

export const useGenerateStore = defineStore('generate', () => {
  const architectureContent = ref('')
  const blueprintContent = ref('')
  const characterDynamicsContent = ref('')
  const architectureExists = ref(false)
  const blueprintExists = ref(false)
  const characterDynamicsExists = ref(false)

  // 各独立文件内容
  const coreSeedContent = ref('')
  const worldBuildingContent = ref('')
  const plotArchitectureContent = ref('')
  const characterStateContent = ref('')

  async function loadStatus() {
    const projectStore = useProjectStore()
    const res = await generateApi.status(projectStore.filepath)
    architectureExists.value = res.data.architecture_exists
    blueprintExists.value = res.data.blueprint_exists
    architectureContent.value = res.data.architecture_content ?? ''
    blueprintContent.value = res.data.blueprint_content ?? ''
    characterDynamicsExists.value = res.data.character_dynamics_exists ?? false
    characterDynamicsContent.value = res.data.character_dynamics_content ?? ''
    coreSeedContent.value = res.data.core_seed_content ?? ''
    worldBuildingContent.value = res.data.world_building_content ?? ''
    plotArchitectureContent.value = res.data.plot_architecture_content ?? ''
    characterStateContent.value = res.data.character_state_content ?? ''
  }

  function $reset() {
    architectureContent.value = ''
    blueprintContent.value = ''
    characterDynamicsContent.value = ''
    architectureExists.value = false
    blueprintExists.value = false
    characterDynamicsExists.value = false
    coreSeedContent.value = ''
    worldBuildingContent.value = ''
    plotArchitectureContent.value = ''
    characterStateContent.value = ''
  }

  // M33: 当文件管理器写入了 generate 关心的文件，重新加载缓存
  async function invalidateForPath(path: string) {
    const base = path.split('/').pop() || path
    if (TRACKED_FILES.includes(base)) {
      try { await loadStatus() } catch { /* ignore */ }
    }
  }

  return {
    architectureContent,
    blueprintContent,
    characterDynamicsContent,
    architectureExists,
    blueprintExists,
    characterDynamicsExists,
    coreSeedContent,
    worldBuildingContent,
    plotArchitectureContent,
    characterStateContent,
    loadStatus,
    invalidateForPath,
    $reset,
  }
})
