<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { usageApi } from '@/api/client'
import { useFeedbackStore } from '@/stores/feedback'

interface BucketSnap {
  name: string
  calls_60s: number
  prompt_tokens_60s: number
  completion_tokens_60s: number
  calls_1h: number
  prompt_tokens_1h: number
  completion_tokens_1h: number
  today_calls: number
  today_prompt_tokens: number
  today_completion_tokens: number
  total_calls: number
  total_prompt_tokens: number
  total_completion_tokens: number
}
interface StatsResponse {
  now: number
  today: string
  total: BucketSnap
  by_dim: { kind: BucketSnap[]; provider: BucketSnap[]; config: BucketSnap[]; model: BucketSnap[] }
}
interface HistoryItem {
  ts: number
  iso: string
  kind: string
  provider: string
  config_name: string
  model: string
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  elapsed_ms: number
  source: string
  note?: string
}

const feedback = useFeedbackStore()
const POLL_MS = 3000

const stats = ref<StatsResponse | null>(null)
const history = ref<HistoryItem[]>([])
const lastErr = ref('')
let timer: number | null = null

const todayTokens = computed(() => {
  const t = stats.value?.total
  if (!t) return 0
  return (t.today_prompt_tokens || 0) + (t.today_completion_tokens || 0)
})
const lifetimeTokens = computed(() => {
  const t = stats.value?.total
  if (!t) return 0
  return (t.total_prompt_tokens || 0) + (t.total_completion_tokens || 0)
})
const tokens60s = computed(() => {
  const t = stats.value?.total
  if (!t) return 0
  return (t.prompt_tokens_60s || 0) + (t.completion_tokens_60s || 0)
})

function fmtNum(n: number | undefined): string {
  if (!n) return '0'
  if (n < 1000) return String(n)
  if (n < 1_000_000) return (n / 1000).toFixed(1) + 'K'
  return (n / 1_000_000).toFixed(2) + 'M'
}

async function refresh() {
  try {
    const [s, h] = await Promise.all([usageApi.getStats(), usageApi.getHistory(50)])
    stats.value = s.data
    history.value = h.data?.items || []
    lastErr.value = ''
  } catch (e) {
    lastErr.value = (e as Error).message || String(e)
  }
}

onMounted(() => {
  refresh()
  timer = window.setInterval(refresh, POLL_MS)
})
onBeforeUnmount(() => {
  if (timer != null) {
    clearInterval(timer)
    timer = null
  }
})
</script>

<template>
  <div class="space-y-4">
    <header class="flex items-center justify-between flex-wrap gap-2">
      <div>
        <h2 class="text-2xl font-bold" style="color: var(--color-ink)">📊 Token 用量</h2>
        <p class="text-xs text-[var(--color-ink-light)]">每 3 秒自动刷新；历史落盘 usage_history.jsonl，重启自动重建当日累计。</p>
      </div>
      <div class="text-xs text-[var(--color-ink-light)]" v-if="stats">
        当前日期：{{ stats.today }} · 服务器时间戳 {{ stats.now }}
      </div>
    </header>

    <div v-if="lastErr" class="iv-config-hint warn">轮询失败：{{ lastErr }}</div>

    <!-- KPI 卡 -->
    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
      <div class="module-panel p-4 space-y-1">
        <div class="text-xs text-[var(--color-ink-light)]">今日 tokens</div>
        <div class="text-2xl font-bold" style="color: var(--color-ink)">{{ fmtNum(todayTokens) }}</div>
        <div class="text-[11px] text-[var(--color-ink-light)]">
          P {{ fmtNum(stats?.total.today_prompt_tokens) }} · C {{ fmtNum(stats?.total.today_completion_tokens) }} · {{ stats?.total.today_calls || 0 }} 次
        </div>
      </div>
      <div class="module-panel p-4 space-y-1">
        <div class="text-xs text-[var(--color-ink-light)]">最近 60s tokens</div>
        <div class="text-2xl font-bold" style="color: var(--color-ink)">{{ fmtNum(tokens60s) }}</div>
        <div class="text-[11px] text-[var(--color-ink-light)]">
          {{ stats?.total.calls_60s || 0 }} 次调用
        </div>
      </div>
      <div class="module-panel p-4 space-y-1">
        <div class="text-xs text-[var(--color-ink-light)]">最近 1 小时</div>
        <div class="text-2xl font-bold" style="color: var(--color-ink)">{{ fmtNum((stats?.total.prompt_tokens_1h || 0) + (stats?.total.completion_tokens_1h || 0)) }}</div>
        <div class="text-[11px] text-[var(--color-ink-light)]">
          {{ stats?.total.calls_1h || 0 }} 次调用
        </div>
      </div>
      <div class="module-panel p-4 space-y-1">
        <div class="text-xs text-[var(--color-ink-light)]">累计 (lifetime)</div>
        <div class="text-2xl font-bold" style="color: var(--color-ink)">{{ fmtNum(lifetimeTokens) }}</div>
        <div class="text-[11px] text-[var(--color-ink-light)]">
          {{ stats?.total.total_calls || 0 }} 次调用
        </div>
      </div>
    </div>

    <!-- 维度聚合表 -->
    <section v-for="dim in (['kind','config','model','provider'] as const)" :key="dim" class="module-panel p-4 space-y-2">
      <div class="flex items-center justify-between">
        <h3 class="text-sm font-semibold" style="color: var(--color-ink)">
          按 {{ dim === 'kind' ? '调用类型' : dim === 'config' ? '配置' : dim === 'model' ? '模型' : '厂商' }}
        </h3>
        <div class="text-xs text-[var(--color-ink-light)]">
          {{ stats?.by_dim[dim].length || 0 }} 项
        </div>
      </div>
      <div class="data-table-shell">
        <table class="min-w-[820px] w-full text-xs">
          <thead class="bg-[var(--color-parchment)] sticky top-0">
            <tr>
              <th class="p-2 text-left">名称</th>
              <th class="p-2 text-right">今日次数</th>
              <th class="p-2 text-right">今日 prompt</th>
              <th class="p-2 text-right">今日 completion</th>
              <th class="p-2 text-right">60s tokens</th>
              <th class="p-2 text-right">1h tokens</th>
              <th class="p-2 text-right">累计 tokens</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in stats?.by_dim[dim] || []" :key="row.name" class="border-t border-[var(--color-parchment)]">
              <td class="p-2 break-all">{{ row.name }}</td>
              <td class="p-2 text-right">{{ row.today_calls }}</td>
              <td class="p-2 text-right">{{ fmtNum(row.today_prompt_tokens) }}</td>
              <td class="p-2 text-right">{{ fmtNum(row.today_completion_tokens) }}</td>
              <td class="p-2 text-right">{{ fmtNum((row.prompt_tokens_60s || 0) + (row.completion_tokens_60s || 0)) }}</td>
              <td class="p-2 text-right">{{ fmtNum((row.prompt_tokens_1h || 0) + (row.completion_tokens_1h || 0)) }}</td>
              <td class="p-2 text-right">{{ fmtNum((row.total_prompt_tokens || 0) + (row.total_completion_tokens || 0)) }}</td>
            </tr>
            <tr v-if="!(stats?.by_dim[dim] || []).length">
              <td class="p-2 text-[var(--color-ink-light)] italic" colspan="7">暂无数据</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- 最近调用流水 -->
    <section class="module-panel p-4 space-y-2">
      <h3 class="text-sm font-semibold" style="color: var(--color-ink)">最近调用（{{ history.length }} 条）</h3>
      <div class="data-table-shell max-h-[420px]">
        <table class="min-w-[1020px] w-full text-xs">
          <thead class="bg-[var(--color-parchment)] sticky top-0">
            <tr>
              <th class="p-2 text-left">时间</th>
              <th class="p-2 text-left">类型</th>
              <th class="p-2 text-left">配置</th>
              <th class="p-2 text-left">模型</th>
              <th class="p-2 text-right">prompt</th>
              <th class="p-2 text-right">completion</th>
              <th class="p-2 text-right">total</th>
              <th class="p-2 text-right">耗时</th>
              <th class="p-2 text-left">来源</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, i) in history" :key="i" class="border-t border-[var(--color-parchment)]">
              <td class="p-2 whitespace-nowrap font-mono text-[10px]">{{ row.iso?.replace('T', ' ') }}</td>
              <td class="p-2">{{ row.kind }}</td>
              <td class="p-2 break-all">{{ row.config_name || '-' }}</td>
              <td class="p-2 break-all">{{ row.model || '-' }}</td>
              <td class="p-2 text-right">{{ fmtNum(row.prompt_tokens) }}</td>
              <td class="p-2 text-right">{{ fmtNum(row.completion_tokens) }}</td>
              <td class="p-2 text-right">{{ fmtNum(row.total_tokens) }}</td>
              <td class="p-2 text-right">{{ row.elapsed_ms ? (row.elapsed_ms / 1000).toFixed(1) + 's' : '-' }}</td>
              <td class="p-2">
                <span :class="['px-1.5 py-0.5 rounded text-[10px]', row.source === 'exact' ? 'bg-green-100 text-green-700' : row.source === 'estimated' ? 'bg-amber-100 text-amber-700' : 'bg-gray-100 text-gray-600']">
                  {{ row.source }}
                </span>
              </td>
            </tr>
            <tr v-if="!history.length">
              <td class="p-2 text-[var(--color-ink-light)] italic" colspan="9">暂无调用记录</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="text-[11px] text-[var(--color-ink-light)]">
        来源标注：<b>exact</b> 来自 LLM/图片 API 返回的 usage 字段（精确）；<b>estimated</b> 是按字符数估算（厂商未返回 usage 时的兜底，约 ±10-15% 误差）；<b>missing</b> 表示既无 usage 也未启用估算。
      </p>
    </section>
  </div>
</template>

<style scoped>
.iv-config-hint { display: flex; align-items: center; gap: 8px; padding: 6px 10px; font-size: 11px; color: var(--color-ink-light); background: var(--color-surface-muted); border-radius: 6px; border: 1px solid var(--color-control-border); }
.iv-config-hint.warn { background: #fffbeb; border-color: #fde68a; color: #78350f; }
</style>
