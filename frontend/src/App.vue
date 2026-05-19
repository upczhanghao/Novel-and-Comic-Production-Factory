<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import ProjectBar from '@/components/ProjectBar.vue'
import AppIcon from '@/components/AppIcon.vue'

const route = useRoute()
const mobileMenuOpen = ref(false)

const navLinks = [
  { to: '/', label: '创作工坊', icon: 'workshop' },
  { to: '/config', label: '模型配置', icon: 'settings' },
  { to: '/presets', label: '提示词方案', icon: 'presets' },
  { to: '/instructions', label: '指令配置', icon: 'instructions' },
  { to: '/styles', label: '文风与DNA', icon: 'styles' },
  { to: '/knowledge', label: '知识库', icon: 'knowledge' },
  { to: '/consistency', label: '一致性检查', icon: 'check' },
  { to: '/brainstorm', label: '创意讨论', icon: 'brainstorm' },
  { to: '/manju', label: '漫剧制作', icon: 'manju' },
  { to: '/images', label: '图片生成', icon: 'images' },
  { to: '/profile', label: '用户画像', icon: 'profile' },
  { to: '/files', label: '文件管理', icon: 'files' },
  { to: '/logs', label: '运行日志', icon: 'logs' },
  { to: '/reader', label: '小说阅读', icon: 'reader' },
]

const navGroups = [
  {
    title: '创作',
    items: navLinks.filter((link) => ['/', '/brainstorm', '/manju', '/images', '/reader'].includes(link.to)),
  },
  {
    title: '资产',
    items: navLinks.filter((link) => ['/presets', '/instructions', '/styles', '/knowledge', '/profile'].includes(link.to)),
  },
  {
    title: '系统',
    items: navLinks.filter((link) => ['/config', '/consistency', '/files', '/logs'].includes(link.to)),
  },
]

const bottomLinks = navLinks.filter((link) => ['/', '/manju', '/images', '/styles'].includes(link.to))
const currentNav = computed(() => navLinks.find((link) => link.to === route.path) ?? navLinks[0])
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
        <div class="text-xs text-[var(--color-ink-light)]">工作流状态</div>
        <div class="mt-2 text-sm font-semibold text-[var(--color-ink)]">小说 / 漫剧 / 图片</div>
        <div class="mt-3 h-1.5 rounded-full bg-white/10 overflow-hidden">
          <div class="h-full w-2/3 rounded-full bg-[var(--color-leather-light)]"></div>
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
        <nav
          v-if="mobileMenuOpen"
          class="mobile-drawer"
        >
          <div v-for="group in navGroups" :key="group.title" class="space-y-2">
            <div class="nav-section-title">{{ group.title }}</div>
            <div class="grid grid-cols-2 gap-2">
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
        <button class="bottom-link" @click="mobileMenuOpen = !mobileMenuOpen" type="button">
          <span><AppIcon name="menu" size="18" /></span>
          <span>更多</span>
        </button>
      </nav>
    </div>

    <div v-if="mobileMenuOpen" class="drawer-backdrop" @click="mobileMenuOpen = false"></div>
  </div>
</template>
