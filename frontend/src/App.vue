<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import ProjectBar from '@/components/ProjectBar.vue'
import AppIcon from '@/components/AppIcon.vue'
import OnboardingWizard from '@/components/OnboardingWizard.vue'
import FeedbackCenter from '@/components/FeedbackCenter.vue'
import TaskBar from '@/components/TaskBar.vue'
import CommandPalette from '@/components/CommandPalette.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import ConfigHealthIndicator from '@/components/ConfigHealthIndicator.vue'
import { useUIStore } from '@/stores/ui'
import { useFeedbackStore } from '@/stores/feedback'
import { useProjectStore } from '@/stores/project'
import { navRoutes, GROUP_TITLES, type NavMeta } from '@/router'

const route = useRoute()
const ui = useUIStore()
const feedback = useFeedbackStore()
const projectStore = useProjectStore()
const mobileMenuOpen = ref(false)
const showOnboarding = ref(false)
const collapsedGroups = ref<Record<string, boolean>>({})

onMounted(() => {
  if (!ui.onboardingDone) showOnboarding.value = true
})

// A14: 全部导航从 router meta 派生
interface NavLink { to: string; label: string; icon: string; level: 'beginner' | 'advanced'; group: NonNullable<NavMeta['group']>; bottomNav: boolean }
const allNavLinks = computed<NavLink[]>(() => navRoutes
  .filter((r) => !r.meta?.hidden && r.meta?.group && r.meta?.icon)
  .map((r) => ({
    to: r.path,
    label: (r.meta as NavMeta).title,
    icon: (r.meta as NavMeta).icon!,
    level: (r.meta as NavMeta).level ?? 'advanced',
    group: (r.meta as NavMeta).group!,
    bottomNav: Boolean((r.meta as NavMeta).bottomNav),
  })))

const navLinks = computed(() => ui.isBeginner ? allNavLinks.value.filter((l) => l.level === 'beginner') : allNavLinks.value)

const navGroups = computed(() => (Object.keys(GROUP_TITLES) as (keyof typeof GROUP_TITLES)[])
  .map((key) => ({ key, title: GROUP_TITLES[key], items: navLinks.value.filter((l) => l.group === key) }))
  .filter((g) => g.items.length > 0))

const bottomLinks = computed(() => navLinks.value.filter((l) => l.bottomNav))
const currentNav = computed(() => allNavLinks.value.find((l) => l.to === route.path) ?? allNavLinks.value[0])

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
        <div class="brand-mark">S</div>
        <div class="min-w-0">
          <h1>Storia</h1>
          <p>小说 · 漫剧 · 图片一站式生产</p>
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
        <div class="mt-2"><ConfigHealthIndicator /></div>
      </div>
    </aside>

    <div class="studio-workspace">
      <header class="mobile-topbar">
        <div class="brand-mark small">S</div>
        <div class="min-w-0">
          <div class="text-sm font-semibold text-[var(--color-ink)] truncate">{{ currentNav.label }}</div>
          <div class="text-[10px] uppercase tracking-[0.18em] text-[var(--color-ink-light)]">Storia</div>
        </div>
        <button class="mobile-search-btn" @click="openSearch" type="button" aria-label="搜索">
          <AppIcon name="search" size="18" />
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
            <component :is="Component" :key="route.path + '@' + projectStore.activeProject" />
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
    <ConfirmDialog />
  </div>
</template>

<style scoped>
.sidebar-search { display: flex; align-items: center; gap: 8px; margin: 0 12px 8px; padding: 8px 10px; background: var(--color-surface-muted); border: 1px solid var(--color-control-border); border-radius: 8px; color: var(--color-ink-light); font-size: 12px; cursor: pointer; transition: background 0.15s, color 0.15s; }
.sidebar-search:hover { background: var(--color-parchment-dark); color: var(--color-ink); }
.ss-icon { font-size: 11px; }
.ss-label { flex: 1; text-align: left; }
.ss-kbd { font-family: var(--font-mono); font-size: 10px; padding: 1px 4px; background: var(--color-parchment-darker); border-radius: 3px; color: var(--color-ink-light); }
.mode-toggle { margin-top: 8px; display: inline-flex; background: #fff; border-radius: 999px; padding: 2px; border: 1px solid #d4d4d8; cursor: pointer; transition: border-color 0.15s, box-shadow 0.15s; }
.mode-toggle:hover { border-color: var(--color-leather-light); box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12); }
.mode-toggle span { padding: 4px 12px; border-radius: 999px; font-size: 11px; color: var(--color-ink-light); transition: all 0.15s; }
.mode-toggle span.active { background: var(--color-gold); color: white; }
.mobile-search-btn { background: transparent; border: 1px solid var(--color-control-border); border-radius: 8px; padding: 6px; margin-right: 6px; }
.m-toggle { display: flex; justify-content: space-between; width: 100%; background: transparent; border: 0; padding: 6px 4px; cursor: pointer; }
.m-arrow { font-size: 10px; opacity: 0.5; }
.mobile-mode-btn { width: 100%; margin-top: 12px; padding: 10px; background: var(--color-surface-muted); border: 1px solid var(--color-control-border); border-radius: 8px; font-size: 13px; cursor: pointer; }
</style>
