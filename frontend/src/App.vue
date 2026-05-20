<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import ProjectBar from '@/components/ProjectBar.vue'
import AppIcon from '@/components/AppIcon.vue'
import OnboardingWizard from '@/components/OnboardingWizard.vue'
import FeedbackCenter from '@/components/FeedbackCenter.vue'
import TaskBar from '@/components/TaskBar.vue'
import CommandPalette from '@/components/CommandPalette.vue'
import { useUIStore } from '@/stores/ui'
import { useFeedbackStore } from '@/stores/feedback'
import { useTasksStore } from '@/stores/tasks'

const route = useRoute()
const ui = useUIStore()
const feedback = useFeedbackStore()
const tasks = useTasksStore()
const mobileMenuOpen = ref(false)
const showOnboarding = ref(false)
const collapsedGroups = ref<Record<string, boolean>>({})

// 暴露 store 给 api/client.ts 的 postSSETracked
;(window as unknown as Record<string, unknown>).__nwFeedback = feedback
;(window as unknown as Record<string, unknown>).__nwTasks = tasks

onMounted(() => {
  if (!ui.onboardingDone) showOnboarding.value = true
})

const allNavLinks = [
  { to: '/', label: '创作工坊', icon: 'workshop', level: 'beginner' },
  { to: '/manju', label: '漫剧制作', icon: 'manju', level: 'beginner' },
  { to: '/images', label: '图片生成', icon: 'images', level: 'beginner' },
  { to: '/reader', label: '小说阅读', icon: 'reader', level: 'beginner' },
  { to: '/brainstorm', label: '创意讨论', icon: 'brainstorm', level: 'beginner' },
  { to: '/config', label: '模型配置', icon: 'settings', level: 'beginner' },
  { to: '/presets', label: '提示词方案', icon: 'presets', level: 'advanced' },
  { to: '/instructions', label: '指令配置', icon: 'instructions', level: 'advanced' },
  { to: '/styles', label: '文风与DNA', icon: 'styles', level: 'advanced' },
  { to: '/knowledge', label: '知识库', icon: 'knowledge', level: 'advanced' },
  { to: '/consistency', label: '一致性检查', icon: 'check', level: 'advanced' },
  { to: '/profile', label: '用户画像', icon: 'profile', level: 'advanced' },
  { to: '/files', label: '文件管理', icon: 'files', level: 'advanced' },
  { to: '/logs', label: '运行日志', icon: 'logs', level: 'advanced' },
]

const navLinks = computed(() => ui.isBeginner ? allNavLinks.filter((l) => l.level === 'beginner') : allNavLinks)

const navGroups = computed(() => [
  { key: 'create', title: '创作', items: navLinks.value.filter((link) => ['/', '/brainstorm', '/manju', '/images', '/reader'].includes(link.to)) },
  { key: 'asset', title: '资产', items: navLinks.value.filter((link) => ['/presets', '/instructions', '/styles', '/knowledge', '/profile'].includes(link.to)) },
  { key: 'system', title: '系统', items: navLinks.value.filter((link) => ['/config', '/consistency', '/files', '/logs'].includes(link.to)) },
].filter((g) => g.items.length > 0))

const bottomLinks = computed(() => navLinks.value.filter((link) => ['/', '/manju', '/images', '/styles'].includes(link.to)))
const currentNav = computed(() => allNavLinks.find((link) => link.to === route.path) ?? allNavLinks[0])

function toggleGroup(key: string) {
  collapsedGroups.value[key] = !collapsedGroups.value[key]
}

function toggleMode() {
  ui.setMode(ui.isBeginner ? 'advanced' : 'beginner')
  feedback.info(`已切换到${ui.isBeginner ? '新手' : '高级'}模式`)
}

function openSearch() {
  ui.commandPaletteOpen = true
  mobileMenuOpen.value = false
}
</script>

<template>
  <div class="studio-shell">
    <aside class="studio-sidebar">
      <div class="brand-block">
        <div class="brand-mark">N</div>
        <div class="min-w-0">
          <h1>NovelWriter</h1>
          <p>AI Production Studio</p>
        </div>
      </div>

      <button class="sidebar-search" @click="openSearch" type="button">
        <span class="ss-icon">🔍</span>
        <span class="ss-label">搜索 / 跳转</span>
        <kbd class="ss-kbd">⌘K</kbd>
      </button>

      <nav class="sidebar-scroll">
        <section v-for="group in navGroups" :key="group.title" class="nav-section">
          <div class="nav-section-title">{{ group.title }}</div>
          <router-link
            v-for="link in group.items"
            :key="link.to"
            :to="link.to"
            class="sidebar-link"
            :class="{ active: route.path === link.to }"
          >
            <span class="sidebar-icon"><AppIcon :name="link.icon" size="17" /></span>
            <span class="truncate">{{ link.label }}</span>
          </router-link>
        </section>
      </nav>

      <div class="sidebar-card">
        <div class="text-xs text-[var(--color-ink-light)]">界面模式</div>
        <button class="mode-toggle" @click="toggleMode" type="button">
          <span :class="{ active: ui.isBeginner }">新手</span>
          <span :class="{ active: !ui.isBeginner }">高级</span>
        </button>
        <div class="mt-2 text-[10px] text-[var(--color-ink-light)]">
          {{ ui.isBeginner ? '只显示核心模块，简化界面' : '展示全部模块与高级选项' }}
        </div>
      </div>
    </aside>

    <div class="studio-workspace">
      <header class="mobile-topbar">
        <div class="brand-mark small">N</div>
        <div class="min-w-0">
          <div class="text-sm font-semibold text-[var(--color-ink)] truncate">{{ currentNav.label }}</div>
          <div class="text-[10px] uppercase tracking-[0.18em] text-[var(--color-ink-light)]">NovelWriter</div>
        </div>
        <button class="mobile-search-btn" @click="openSearch" type="button" aria-label="搜索">
          <AppIcon name="presets" size="18" />
        </button>
        <button class="mobile-menu-button" @click="mobileMenuOpen = !mobileMenuOpen" type="button" aria-label="打开菜单">
          <AppIcon :name="mobileMenuOpen ? 'close' : 'menu'" size="20" />
        </button>
      </header>

      <div class="studio-command">
        <div class="page-identity">
          <div class="page-icon"><AppIcon :name="currentNav.icon" size="18" /></div>
          <div class="min-w-0">
            <h2>{{ currentNav.label }}</h2>
            <p>一站式 AI 小说与漫剧生产工作区</p>
          </div>
        </div>
        <ProjectBar />
      </div>

      <Transition name="slide">
        <nav v-if="mobileMenuOpen" class="mobile-drawer">
          <div v-for="group in navGroups" :key="group.title" class="space-y-2">
            <button class="nav-section-title m-toggle" @click="toggleGroup(group.key)" type="button">
              <span>{{ group.title }}</span>
              <span class="m-arrow">{{ collapsedGroups[group.key] ? '▸' : '▾' }}</span>
            </button>
            <div v-show="!collapsedGroups[group.key]" class="grid grid-cols-2 gap-2">
              <router-link
                v-for="link in group.items"
                :key="link.to"
                :to="link.to"
                class="mobile-drawer-link"
                :class="{ active: route.path === link.to }"
                @click="mobileMenuOpen = false"
              >
                <span><AppIcon :name="link.icon" size="17" /></span>
                <span>{{ link.label }}</span>
              </router-link>
            </div>
          </div>
          <button class="mobile-mode-btn" @click="toggleMode" type="button">
            切换到{{ ui.isBeginner ? '高级' : '新手' }}模式
          </button>
        </nav>
      </Transition>

      <main class="studio-content">
        <router-view v-slot="{ Component }">
          <keep-alive>
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </main>

      <nav class="mobile-bottom-nav">
        <router-link
          v-for="link in bottomLinks"
          :key="link.to"
          :to="link.to"
          class="bottom-link"
          :class="{ active: route.path === link.to }"
        >
          <span><AppIcon :name="link.icon" size="18" /></span>
          <span>{{ link.label }}</span>
        </router-link>
        <button class="bottom-link" @click="openSearch" type="button">
          <span>🔍</span>
          <span>搜索</span>
        </button>
        <button class="bottom-link" @click="mobileMenuOpen = !mobileMenuOpen" type="button">
          <span><AppIcon name="menu" size="18" /></span>
          <span>更多</span>
        </button>
      </nav>
    </div>

    <div v-if="mobileMenuOpen" class="drawer-backdrop" @click="mobileMenuOpen = false" />

    <OnboardingWizard :open="showOnboarding" @close="showOnboarding = false" />
    <FeedbackCenter />
    <TaskBar />
    <CommandPalette />
  </div>
</template>

<style scoped>
.sidebar-search { display: flex; align-items: center; gap: 8px; margin: 0 12px 8px; padding: 8px 10px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; color: rgba(255,255,255,0.6); font-size: 12px; cursor: pointer; transition: background 0.15s; }
.sidebar-search:hover { background: rgba(255,255,255,0.08); color: white; }
.ss-icon { font-size: 11px; }
.ss-label { flex: 1; text-align: left; }
.ss-kbd { font-family: var(--font-mono); font-size: 10px; padding: 1px 4px; background: rgba(255,255,255,0.08); border-radius: 3px; color: rgba(255,255,255,0.5); }
.mode-toggle { margin-top: 8px; display: inline-flex; background: rgba(255,255,255,0.06); border-radius: 999px; padding: 2px; border: 0; cursor: pointer; }
.mode-toggle span { padding: 4px 12px; border-radius: 999px; font-size: 11px; color: rgba(255,255,255,0.6); transition: all 0.15s; }
.mode-toggle span.active { background: var(--color-gold); color: white; }
.mobile-search-btn { background: transparent; border: 1px solid var(--color-control-border); border-radius: 8px; padding: 6px; margin-right: 6px; }
.m-toggle { display: flex; justify-content: space-between; width: 100%; background: transparent; border: 0; padding: 6px 4px; cursor: pointer; }
.m-arrow { font-size: 10px; opacity: 0.5; }
.mobile-mode-btn { width: 100%; margin-top: 12px; padding: 10px; background: var(--color-surface-muted); border: 1px solid var(--color-control-border); border-radius: 8px; font-size: 13px; cursor: pointer; }
</style>
