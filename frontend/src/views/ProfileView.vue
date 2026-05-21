<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { configApi, xpPresetsApi } from '@/api/client'
import { useFeedbackStore } from '@/stores/feedback'
import { confirmDialog } from '@/stores/confirm'

const route = useRoute()
type Tab = 'profile' | 'snippets'
const activeTab = ref<Tab>(route.query.tab === 'snippets' ? 'snippets' : 'profile')

// ── 用户画像 ──────────────────────────────────────────────────────────
const userProfile = ref('')
const profileEnabled = ref(true)
const profileSaving = ref(false)
const profileMsg = ref('')

const feedback = useFeedbackStore()

async function loadProfile() {
  try {
    const res = await configApi.getUserProfile()
    userProfile.value = res.data.profile || ''
    profileEnabled.value = res.data.enabled !== false
  } catch { /* ignore */ }
}

async function saveProfile() {
  profileSaving.value = true
  try {
    await configApi.saveUserProfile(userProfile.value, profileEnabled.value)
    profileMsg.value = '✅ 画像已保存'
  } catch (e: unknown) {
    profileMsg.value = `❌ ${(e as Error).message}`
  }
  profileSaving.value = false
  setTimeout(() => { profileMsg.value = '' }, 3000)
}

// ── 命名片段 (xp_presets) ─────────────────────────────────────────────
type Snippet = { name: string; content: string }
const snippets = ref<Snippet[]>([])
const editing = ref<Snippet | null>(null)
const editName = ref('')
const editContent = ref('')
const editorOpen = ref(false)
const snippetSaving = ref(false)
const search = ref('')

async function loadSnippets() {
  try {
    const res = await xpPresetsApi.list()
    snippets.value = res.data.presets
  } catch (e: unknown) {
    feedback.error('加载命名片段失败', (e as Error).message)
  }
}

function startCreate() {
  editing.value = null
  editName.value = ''
  editContent.value = ''
  editorOpen.value = true
}

function startEdit(s: Snippet) {
  editing.value = s
  editName.value = s.name
  editContent.value = s.content
  editorOpen.value = true
}

function cancelEdit() {
  editing.value = null
  editName.value = ''
  editContent.value = ''
  editorOpen.value = false
}

async function saveSnippet() {
  const name = editName.value.trim()
  const content = editContent.value.trim()
  if (!name || !content) return
  snippetSaving.value = true
  try {
    if (editing.value) {
      await xpPresetsApi.update(editing.value.name, { name, content })
      feedback.success(`已更新「${name}」`)
    } else {
      await xpPresetsApi.create(name, content)
      feedback.success(`已创建「${name}」`)
    }
    await loadSnippets()
    cancelEdit()
  } catch (e: unknown) {
    feedback.error('保存失败', (e as Error).message)
  } finally {
    snippetSaving.value = false
  }
}

async function deleteSnippet(name: string) {
  if (!(await confirmDialog(`确认删除命名片段「${name}」？`))) return
  try {
    await xpPresetsApi.delete(name)
    feedback.success(`已删除「${name}」`)
    await loadSnippets()
  } catch (e: unknown) {
    feedback.error('删除失败', (e as Error).message)
  }
}

onMounted(() => {
  loadProfile()
  loadSnippets()
})
</script>

<template>
  <div class="module-page compact space-y-5">
    <h2 class="text-2xl font-bold" style="color: var(--color-ink)">👤 用户画像</h2>

    <div class="module-toolbar">
      <div>
        <div class="module-kicker">User Profile</div>
        <div class="module-subtitle">维护创作偏好与可复用命名片段，供生成流程自动参考。全局生效，所有项目共用。</div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="flex border-b border-[var(--color-parchment-darker)]">
      <button
        @click="activeTab = 'profile'" type="button"
        class="px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors"
        :class="activeTab === 'profile' ? 'border-[var(--color-leather)] text-[var(--color-leather)]' : 'border-transparent text-[var(--color-ink-light)] hover:text-[var(--color-ink)]'"
      >内容偏好</button>
      <button
        @click="activeTab = 'snippets'" type="button"
        class="px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors"
        :class="activeTab === 'snippets' ? 'border-[var(--color-leather)] text-[var(--color-leather)]' : 'border-transparent text-[var(--color-ink-light)] hover:text-[var(--color-ink)]'"
      >命名片段 <span class="text-xs opacity-70">({{ snippets.length }})</span></button>
    </div>

    <!-- Tab: 内容偏好 -->
    <template v-if="activeTab === 'profile'">
      <div class="module-panel overflow-hidden">
        <div class="module-panel-header">
          <div>
            <h3 class="module-panel-title">内容偏好</h3>
            <p class="text-xs text-[var(--color-ink-light)] mt-1">记录你的内容偏好（角色类型、XP倾向、关系模式等）。生成架构/角色/剧情/蓝图/细纲时自动参考。</p>
          </div>
          <label class="inline-flex items-center gap-2 cursor-pointer shrink-0 ml-4">
            <input type="checkbox" v-model="profileEnabled" class="rounded border-[var(--color-parchment-darker)]" />
            <span class="text-sm" :class="profileEnabled ? 'text-green-700 font-medium' : 'text-[var(--color-ink-light)]'">{{ profileEnabled ? '已启用' : '已禁用' }}</span>
          </label>
        </div>
        <div class="p-4 space-y-3">
          <textarea
            v-model="userProfile"
            rows="12"
            class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm font-mono resize-y"
            placeholder="例如：
- 女角色偏好自愿而非强迫
- 喜欢年上姐姐型角色，温柔包容
- 催眠后角色保留意识但无法抗拒
- 偏好角色之间先有情感基础再发展肉体关系
- 不喜欢纯粹的暴力强制
- 官能场景偏好支配/服从的权力差但基于信任"
          />
          <div class="flex items-center justify-between">
            <span v-if="profileMsg" class="text-xs" :class="profileMsg.startsWith('✅') ? 'text-green-600' : 'text-red-500'">{{ profileMsg }}</span>
            <span v-else class="text-xs text-[var(--color-ink-light)]">修改后点击保存，将在下次生成架构/角色/剧情/蓝图/细纲时生效</span>
            <button @click="saveProfile" :disabled="profileSaving"
              class="px-4 py-2 rounded-md text-sm font-semibold text-white disabled:opacity-40 transition-colors"
              style="background-color: var(--color-leather)"
              type="button">
              {{ profileSaving ? '保存中...' : '保存画像' }}
            </button>
          </div>
        </div>
      </div>

      <div class="module-panel overflow-hidden">
        <div class="module-panel-header">
          <div>
            <h3 class="module-panel-title">自动采集</h3>
            <p class="text-xs text-[var(--color-ink-light)] mt-1">在创意讨论、修订建议、润色建议中表达偏好时，系统会自动检测并提示你是否加入画像。</p>
          </div>
        </div>
        <div class="p-4">
          <div class="text-sm text-[var(--color-ink-light)] space-y-2">
            <p>采集来源：</p>
            <ul class="list-disc list-inside space-y-1 text-xs">
              <li><strong>创意讨论</strong> — 发送消息时自动提取偏好信号</li>
              <li><strong>修订建议</strong> — 提交架构/角色/剧情修订时自动提取</li>
              <li><strong>润色建议</strong> — 提交润色请求时自动提取</li>
            </ul>
            <p class="text-xs">检测到偏好后会弹出确认条，点击"加入画像"才会写入，不会自动添加。</p>
          </div>
        </div>
      </div>
    </template>

    <!-- Tab: 命名片段 -->
    <template v-else>
      <div class="module-panel overflow-hidden">
        <div class="module-panel-header">
          <div>
            <h3 class="module-panel-title">命名片段</h3>
            <p class="text-xs text-[var(--color-ink-light)] mt-1">
              可复用的命名内容片段（如 XP 类型、核心玩法、套路模板）。在工坊「基础参数」中以勾选方式注入「XP类型/核心玩法」字段。
            </p>
          </div>
          <button @click="startCreate" type="button"
            class="px-3 py-1.5 rounded-md text-sm font-semibold text-white shrink-0"
            style="background-color: var(--color-leather)">+ 新建片段</button>
        </div>
        <div class="p-4 space-y-3">
          <input v-model="search" placeholder="搜索片段…" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm" />

          <div v-if="editorOpen" class="rounded-md border border-blue-200 bg-blue-50/30 p-3 space-y-2">
            <div class="flex items-center justify-between">
              <span class="text-sm font-medium">{{ editing ? `编辑：${editing.name}` : '新建命名片段' }}</span>
              <button @click="cancelEdit" type="button" class="text-xs text-gray-500 hover:text-gray-700">取消</button>
            </div>
            <input v-model="editName" placeholder="片段名称，如：催眠、NTR、时间停止…"
              class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-1.5 text-sm" />
            <textarea v-model="editContent" rows="4" placeholder="详细描述该片段的定义、卖点、关键元素…"
              class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm resize-y" />
            <div class="flex justify-end">
              <button @click="saveSnippet" :disabled="snippetSaving || !editName.trim() || !editContent.trim()"
                class="px-4 py-1.5 rounded-md text-sm font-semibold text-white disabled:opacity-40"
                style="background-color: var(--color-leather)" type="button">
                {{ snippetSaving ? '保存中…' : (editing ? '更新' : '保存') }}
              </button>
            </div>
          </div>

          <div v-if="!snippets.length" class="py-8 text-center text-sm text-[var(--color-ink-light)]">
            还没有命名片段，点击右上角「+ 新建片段」创建。
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="s in snippets.filter(p => !search.trim() || p.name.toLowerCase().includes(search.trim().toLowerCase()) || p.content.toLowerCase().includes(search.trim().toLowerCase()))"
              :key="s.name"
              class="rounded-md border border-[var(--color-parchment-darker)] bg-white p-3"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="flex-1 min-w-0">
                  <div class="font-medium text-sm">{{ s.name }}</div>
                  <pre class="text-xs text-[var(--color-ink-light)] mt-1 whitespace-pre-wrap break-words line-clamp-3">{{ s.content }}</pre>
                </div>
                <div class="flex gap-2 shrink-0">
                  <button @click="startEdit(s)" type="button" class="text-xs text-blue-600 hover:underline">编辑</button>
                  <button @click="deleteSnippet(s.name)" type="button" class="text-xs text-red-600 hover:underline">删除</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
