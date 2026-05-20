<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { configApi } from '@/api/client'
import { useFeedbackStore } from '@/stores/feedback'
import { validateProxy } from '@/composables/useConfigValidation'
import ConfigSectionHeader from './ConfigSectionHeader.vue'

const feedback = useFeedbackStore()
const proxyUrl = ref('')
const proxyPort = ref('')
const proxyEnabled = ref(false)
const proxySaving = ref(false)

const validation = computed(() => validateProxy({ proxy_url: proxyUrl.value, proxy_port: proxyPort.value }))

async function load() {
  try {
    const res = await configApi.getProxy()
    proxyUrl.value = res.data.proxy_url || ''
    proxyPort.value = res.data.proxy_port || ''
    proxyEnabled.value = res.data.enabled || false
  } catch { /* ignore */ }
}

async function save() {
  if (Object.keys(validation.value.errors).length) {
    feedback.warning('代理设置存在错误，请先修正')
    return
  }
  proxySaving.value = true
  try {
    await configApi.saveProxy({ proxy_url: proxyUrl.value, proxy_port: proxyPort.value, enabled: proxyEnabled.value })
    feedback.success('✅ 代理设置已保存')
  } catch (e) {
    feedback.error('代理保存失败', (e as Error).message)
  } finally {
    proxySaving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="config-section">
    <ConfigSectionHeader
      title="网络代理"
      subtitle="为 LLM / Embedding / Image 请求统一配置 HTTP 代理"
      icon="🌐"
      :defaults="[{ label: '状态', value: proxyEnabled ? '已启用' : '已禁用' }]"
      accent="#6b7280"
    />
    <div class="config-body">
      <div class="grid grid-cols-1 sm:grid-cols-[1fr_9rem_auto] gap-3 items-end">
        <div>
          <label class="cf-label">代理地址</label>
          <input v-model="proxyUrl" placeholder="例如：127.0.0.1 或 http://proxy.example.com" class="cf-input" />
          <div v-if="validation.warnings.proxy_url" class="cf-warn">{{ validation.warnings.proxy_url }}</div>
        </div>
        <div>
          <label class="cf-label">端口</label>
          <input v-model="proxyPort" placeholder="7890" class="cf-input" />
          <div v-if="validation.errors.proxy_port" class="cf-err">{{ validation.errors.proxy_port }}</div>
        </div>
        <label class="inline-flex items-center gap-2 cursor-pointer text-sm h-[38px] px-3 border border-[var(--color-parchment-darker)] rounded-md bg-white">
          <input type="checkbox" v-model="proxyEnabled" class="accent-[var(--color-leather)]" />
          <span :class="proxyEnabled ? 'text-green-700' : 'text-[var(--color-ink-light)]'">{{ proxyEnabled ? '已启用' : '已禁用' }}</span>
        </label>
      </div>
      <div class="flex justify-end mt-3">
        <button
          @click="save"
          :disabled="proxySaving || Object.keys(validation.errors).length > 0"
          class="px-4 py-2 rounded-md text-sm font-semibold text-white disabled:opacity-40"
          style="background-color: var(--color-leather)"
          type="button"
        >
          {{ proxySaving ? '保存中…' : '保存代理设置' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.config-section { display: flex; flex-direction: column; }
.config-body { padding: 14px 16px; background: white; border: 1px solid var(--color-control-border); border-top: none; border-radius: 0 0 10px 10px; }
.cf-label { display: block; font-size: 11px; color: var(--color-ink-light); margin-bottom: 4px; }
.cf-input { width: 100%; padding: 8px 10px; font-size: 13px; border: 1px solid var(--color-parchment-darker); border-radius: 6px; }
.cf-input:focus { outline: none; border-color: var(--color-leather-light); box-shadow: 0 0 0 2px rgba(150,110,80,0.12); }
.cf-err { font-size: 11px; color: var(--color-error); margin-top: 2px; }
.cf-warn { font-size: 11px; color: #92400e; margin-top: 2px; }
</style>
