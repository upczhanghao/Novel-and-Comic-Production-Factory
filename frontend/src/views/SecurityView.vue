<template>
  <div class="security-view">
    <header class="view-header">
      <h1>安全与限流</h1>
      <p class="muted">实时查看 API 请求量、限额命中与拒绝情况。改限额会立即生效，并写入 <code>rate_limits.json</code>。</p>
    </header>

    <section class="card">
      <div class="row">
        <label class="toggle">
          <input type="checkbox" :checked="config.enabled" @change="toggleEnabled(($event.target as HTMLInputElement).checked)" />
          <span>启用限流</span>
        </label>
        <button class="btn-ghost" @click="refresh" :disabled="loading">{{ loading ? '刷新中…' : '立即刷新' }}</button>
        <span class="muted small">窗口：最近 {{ stats.window_seconds ?? 60 }} 秒 · 每 {{ POLL_MS / 1000 }}s 自动刷新</span>
      </div>
    </section>

    <section class="card">
      <h2>每桶实时状态</h2>
      <table class="bucket-table">
        <thead>
          <tr>
            <th>桶</th>
            <th>每分钟限额</th>
            <th>近 60s 命中</th>
            <th>近 60s 拒绝</th>
            <th>累计命中</th>
            <th>累计拒绝</th>
            <th>路径前缀</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(b, name) in stats.buckets" :key="name">
            <td><strong>{{ name }}</strong></td>
            <td>
              <input
                v-if="editing[name] !== undefined"
                type="number"
                min="0"
                v-model.number="editing[name]"
                class="num"
              />
              <span v-else>{{ b.per_min }}</span>
            </td>
            <td>
              <span class="pill" :class="usageClass(b)">{{ b.hits_60s }}</span>
            </td>
            <td>
              <span class="pill" :class="b.rejects_60s > 0 ? 'danger' : ''">{{ b.rejects_60s }}</span>
            </td>
            <td>{{ b.total_hits }}</td>
            <td>{{ b.total_rejects }}</td>
            <td class="prefixes">
              <code v-for="p in b.path_prefixes" :key="p">{{ p }}</code>
            </td>
            <td>
              <template v-if="editing[name] !== undefined">
                <button class="btn-primary small" @click="saveBucket(String(name))">保存</button>
                <button class="btn-ghost small" @click="cancelEdit(String(name))">取消</button>
              </template>
              <template v-else>
                <button class="btn-ghost small" @click="startEdit(String(name), b.per_min)">改限额</button>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="card" v-if="stats.top_clients?.length">
      <h2>Top 客户端（近 60s）</h2>
      <table class="bucket-table">
        <thead>
          <tr>
            <th>客户端</th>
            <th>命中</th>
            <th>拒绝</th>
            <th>分桶明细</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in stats.top_clients" :key="c.client">
            <td><code>{{ c.client }}</code></td>
            <td>{{ c.hits_60s }}</td>
            <td><span class="pill" :class="c.rejects_60s > 0 ? 'danger' : ''">{{ c.rejects_60s }}</span></td>
            <td class="muted small">
              <span v-for="(detail, bk) in c.buckets" :key="bk">
                {{ bk }}: {{ detail.hits_60s }}/拒{{ detail.rejects_60s }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="card">
      <h2>豁免路径</h2>
      <ul class="muted">
        <li v-for="p in stats.exempt_path_prefixes" :key="p"><code>{{ p }}</code></li>
      </ul>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, reactive, ref } from 'vue'
import { securityApi } from '@/api/client'
import { useFeedbackStore } from '@/stores/feedback'

const POLL_MS = 3000
const feedback = useFeedbackStore()

const loading = ref(false)
const config = reactive<any>({ enabled: true, buckets: {}, exempt_path_prefixes: [] })
const stats = reactive<any>({ buckets: {}, top_clients: [], exempt_path_prefixes: [], window_seconds: 60 })
const editing = reactive<Record<string, number | undefined>>({})

let timer: number | undefined

async function refresh() {
  loading.value = true
  try {
    const res = await securityApi.getRateLimits()
    Object.assign(config, res.data.config)
    Object.assign(stats, res.data.stats)
  } catch (e: any) {
    feedback.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function toggleEnabled(value: boolean) {
  try {
    await securityApi.updateRateLimits({ enabled: value })
    feedback.success(value ? '已启用限流' : '已暂停限流')
    await refresh()
  } catch (e: any) {
    feedback.error(e.message || '更新失败')
  }
}

function startEdit(name: string, current: number) {
  editing[name] = current
}
function cancelEdit(name: string) {
  delete editing[name]
}
async function saveBucket(name: string) {
  const per_min = Number(editing[name])
  if (!Number.isFinite(per_min) || per_min < 0) {
    feedback.error('请输入非负整数')
    return
  }
  try {
    await securityApi.updateRateLimits({ buckets: { [name]: { per_min } } })
    feedback.success(`已更新 ${name} 限额为 ${per_min}/分钟`)
    delete editing[name]
    await refresh()
  } catch (e: any) {
    feedback.error(e.message || '更新失败')
  }
}

function usageClass(b: any): string {
  if (!b.per_min) return ''
  const ratio = b.hits_60s / b.per_min
  if (ratio >= 1) return 'danger'
  if (ratio >= 0.7) return 'warn'
  return ''
}

onMounted(() => {
  refresh()
  timer = window.setInterval(refresh, POLL_MS)
})
onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<style scoped>
.security-view { padding: 24px; max-width: 1200px; margin: 0 auto; }
.view-header h1 { margin: 0 0 4px; }
.muted { color: var(--text-muted, #94a3b8); }
.small { font-size: 12px; }
.card { background: var(--surface, #fff); border: 1px solid var(--border, #e2e8f0); border-radius: 12px; padding: 16px 20px; margin-top: 16px; }
.card h2 { margin: 0 0 12px; font-size: 16px; }
.row { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.toggle { display: inline-flex; gap: 8px; align-items: center; cursor: pointer; }
.bucket-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.bucket-table th, .bucket-table td { padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--border, #f1f5f9); vertical-align: top; }
.bucket-table th { font-weight: 600; color: var(--text-muted, #64748b); }
.prefixes code { display: inline-block; margin: 0 4px 4px 0; padding: 2px 6px; background: var(--surface-2, #f1f5f9); border-radius: 4px; font-size: 12px; }
.pill { display: inline-block; min-width: 32px; padding: 2px 8px; border-radius: 999px; background: var(--surface-2, #f1f5f9); text-align: center; font-variant-numeric: tabular-nums; }
.pill.warn { background: #fef3c7; color: #92400e; }
.pill.danger { background: #fee2e2; color: #991b1b; }
.num { width: 80px; padding: 4px 6px; border: 1px solid var(--border, #e2e8f0); border-radius: 6px; }
.btn-primary, .btn-ghost { padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 13px; }
.btn-primary { background: var(--brand, #3b82f6); color: #fff; border: 1px solid transparent; }
.btn-ghost { background: transparent; border: 1px solid var(--border, #e2e8f0); }
.btn-primary.small, .btn-ghost.small { padding: 4px 8px; font-size: 12px; margin-right: 4px; }
</style>
