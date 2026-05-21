import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

// A14: 路由 meta 是导航相关元信息的唯一数据源。
// sidebar / mobile drawer / bottom nav / command palette 都派生自此处。
export interface NavMeta {
  title: string
  icon?: string
  group?: 'create' | 'asset' | 'system'
  level?: 'beginner' | 'advanced'
  hidden?: boolean
  bottomNav?: boolean
  // A11: 路由是否需要激活项目；缺省视为 true（保守），显式 false 才放行
  requiresProject?: boolean
}

declare module 'vue-router' {
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  interface RouteMeta extends NavMeta {}
}

export const navRoutes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'workshop',
    component: () => import('@/views/WorkshopView.vue'),
    meta: { title: '创作工坊', icon: 'workshop', group: 'create', level: 'beginner', bottomNav: true },
  },
  {
    path: '/brainstorm',
    name: 'brainstorm',
    component: () => import('@/views/BrainstormView.vue'),
    meta: { title: '创意讨论', icon: 'brainstorm', group: 'create', level: 'beginner' },
  },
  {
    path: '/manju',
    name: 'manju',
    component: () => import('@/views/ManjuView.vue'),
    meta: { title: '漫剧制作', icon: 'manju', group: 'create', level: 'beginner', bottomNav: true },
  },
  {
    path: '/images',
    name: 'images',
    component: () => import('@/views/ImageView.vue'),
    meta: { title: '图片生成', icon: 'images', group: 'create', level: 'beginner', bottomNav: true },
  },
  {
    path: '/reader',
    name: 'reader',
    component: () => import('@/views/ReaderView.vue'),
    meta: { title: '小说阅读', icon: 'reader', group: 'create', level: 'beginner' },
  },
  {
    path: '/presets',
    name: 'presets',
    component: () => import('@/views/PresetsView.vue'),
    meta: { title: '提示词方案', icon: 'presets', group: 'asset', level: 'advanced', requiresProject: false },
  },
  {
    path: '/instructions',
    name: 'instructions',
    component: () => import('@/views/InstructionConfigView.vue'),
    meta: { title: '指令配置', icon: 'instructions', group: 'asset', level: 'advanced', requiresProject: false },
  },
  {
    path: '/styles',
    name: 'styles',
    component: () => import('@/views/StylesView.vue'),
    meta: { title: '文风与DNA', icon: 'styles', group: 'asset', level: 'advanced', bottomNav: true, requiresProject: false },
  },
  {
    path: '/knowledge',
    name: 'knowledge',
    component: () => import('@/views/KnowledgeView.vue'),
    meta: { title: '知识库', icon: 'knowledge', group: 'asset', level: 'advanced', requiresProject: false },
  },
  {
    path: '/profile',
    name: 'profile',
    component: () => import('@/views/ProfileView.vue'),
    meta: { title: '用户画像', icon: 'profile', group: 'asset', level: 'advanced', requiresProject: false },
  },
  {
    path: '/config',
    name: 'config',
    component: () => import('@/views/ConfigView.vue'),
    meta: { title: '模型配置', icon: 'settings', group: 'system', level: 'beginner', requiresProject: false },
  },
  {
    path: '/consistency',
    name: 'consistency',
    component: () => import('@/views/ConsistencyView.vue'),
    meta: { title: '一致性检查', icon: 'check', group: 'system', level: 'advanced' },
  },
  {
    path: '/security',
    name: 'security',
    component: () => import('@/views/SecurityView.vue'),
    meta: { title: '安全与限流', icon: 'check', group: 'system', level: 'advanced', requiresProject: false },
  },
  {
    path: '/files',
    name: 'files',
    component: () => import('@/views/FilesView.vue'),
    meta: { title: '文件管理', icon: 'files', group: 'system', level: 'advanced', requiresProject: false },
  },
  {
    path: '/logs',
    name: 'logs',
    component: () => import('@/views/LogsView.vue'),
    meta: { title: '运行日志', icon: 'logs', group: 'system', level: 'advanced', requiresProject: false },
  },
  {
    path: '/no-project',
    name: 'no-project',
    component: () => import('@/views/NoProjectView.vue'),
    meta: { title: '请选择项目', hidden: true, requiresProject: false },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes: navRoutes,
})

router.afterEach((to) => {
  document.title = `${to.meta.title ?? 'Storia'} — Storia`
})

// A11: 项目守卫 — 路由 meta.requiresProject !== false 时要求 hasActiveProject
let projectLoaded = false
router.beforeEach(async (to) => {
  if (to.meta.requiresProject === false) return true
  // 懒加载，避免 router 模块顶层依赖 pinia
  const { useProjectStore } = await import('@/stores/project')
  const store = useProjectStore()
  if (!projectLoaded) {
    try { await store.loadActive() } catch { /* ignore */ }
    projectLoaded = true
  }
  if (!store.hasActiveProject) {
    return { path: '/no-project', query: { to: to.fullPath } }
  }
  return true
})

export default router

export const GROUP_TITLES: Record<NonNullable<NavMeta['group']>, string> = {
  create: '创作',
  asset: '资产',
  system: '系统',
}
