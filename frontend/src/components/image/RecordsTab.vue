<script setup lang="ts">
import { computed, ref } from 'vue'
import RecordCard, { type ImageRecord } from './RecordCard.vue'
import { applyRecordFilters } from '@/composables/useImageFilters'

const props = defineProps<{
  records: ImageRecord[]
  selected: string[]
  busy?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:selected', v: string[]): void
  (e: 'view', r: ImageRecord): void
  (e: 'retry', r: ImageRecord): void
  (e: 'delete', r: ImageRecord): void
  (e: 'copyPrompt', r: ImageRecord): void
  (e: 'copyParams', r: ImageRecord): void
  (e: 'batchRetry', rs: ImageRecord[]): void
  (e: 'batchDelete', rs: ImageRecord[]): void
}>()

const sourceType = ref('all')
const chapter = ref('')
const keyword = ref('')
const configName = ref('all')
const dateFrom = ref('')

const sourceTypes = computed(() => {
  const set = new Set<string>()
  props.records.forEach((r) => set.add(r.source_type || 'custom'))
  return Array.from(set)
})

const configNames = computed(() => {
  const set = new Set<string>()
  props.records.forEach((r) => { if (r.config_name) set.add(r.config_name) })
  return Array.from(set)
})

const filtered = computed(() =>
  applyRecordFilters(props.records, {
    sourceType: sourceType.value,
    chapter: chapter.value,
    keyword: keyword.value,
    configName: configName.value,
    dateFrom: dateFrom.value,
  }),
)

const selectedRecords = computed(() => props.records.filter((r) => props.selected.includes(r.id)))
const allFilteredSelected = computed(
  () => filtered.value.length > 0 && filtered.value.every((r) => props.selected.includes(r.id)),
)

function toggleOne() { /* handled via select event */ }

function onSelect(r: ImageRecord) {
  const next = props.selected.includes(r.id)
    ? props.selected.filter((x) => x !== r.id)
    : [...props.selected, r.id]
  emit('update:selected', next)
}

function toggleAll() {
  if (allFilteredSelected.value) {
    const ids = new Set(filtered.value.map((r) => r.id))
    emit('update:selected', props.selected.filter((x) => !ids.has(x)))
  } else {
    const set = new Set(props.selected)
    filtered.value.forEach((r) => set.add(r.id))
    emit('update:selected', Array.from(set))
  }
}

function clearFilters() {
  sourceType.value = 'all'
  chapter.value = ''
  keyword.value = ''
  configName.value = 'all'
  dateFrom.value = ''
}
</script>

<template>
  <div class="rt-root">
    <div class="rt-filters">
      <select v-model="sourceType" class="rt-input">
        <option value="all">全部来源</option>
        <option v-for="t in sourceTypes" :key="t" :value="t">{{ t }}</option>
      </select>
      <select v-model="configName" class="rt-input">
        <option value="all">全部配置</option>
        <option v-for="c in configNames" :key="c" :value="c">{{ c }}</option>
      </select>
      <input v-model="chapter" placeholder="章节号 (e.g. 1)" class="rt-input narrow" />
      <input v-model="dateFrom" type="date" class="rt-input" />
      <input v-model="keyword" placeholder="搜索提示词 / 文件名…" class="rt-input grow" />
      <button class="rt-btn" type="button" @click="clearFilters">重置</button>
    </div>

    <div class="rt-bar">
      <span class="rt-count">{{ selected.length }} / {{ filtered.length }} 已选 · 共 {{ records.length }} 张</span>
      <button class="rt-btn" type="button" @click="toggleAll">
        {{ allFilteredSelected ? '取消全选' : '全选可见' }}
      </button>
      <button class="rt-btn" type="button" :disabled="!selected.length" @click="emit('update:selected', [])">清空</button>
      <button
        class="rt-btn primary"
        type="button"
        :disabled="!selected.length || busy"
        @click="emit('batchRetry', selectedRecords)"
      >批量重试</button>
      <button
        class="rt-btn danger"
        type="button"
        :disabled="!selected.length"
        @click="emit('batchDelete', selectedRecords)"
      >批量删除</button>
    </div>

    <div v-if="!filtered.length" class="rt-empty">
      {{ records.length ? '当前过滤条件下没有图片' : '暂无生成记录，先生成一张试试。' }}
    </div>
    <div v-else class="rt-grid">
      <RecordCard
        v-for="r in filtered"
        :key="r.id"
        :record="r"
        :selected="selected.includes(r.id)"
        @select="onSelect(r)"
        @view="emit('view', r)"
        @retry="emit('retry', r)"
        @delete="emit('delete', r)"
        @copyPrompt="emit('copyPrompt', r)"
        @copyParams="emit('copyParams', r)"
      />
    </div>
  </div>
</template>

<style scoped>
.rt-root { display: flex; flex-direction: column; gap: 10px; }
.rt-filters { display: flex; flex-wrap: wrap; gap: 6px; }
.rt-input { padding: 5px 8px; font-size: 12px; border-radius: 6px; border: 1px solid var(--color-control-border); background: white; }
.rt-input.narrow { width: 90px; }
.rt-input.grow { flex: 1; min-width: 140px; }
.rt-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; padding: 8px 10px; background: var(--color-surface-muted); border: 1px solid var(--color-control-border); border-radius: 8px; }
.rt-count { font-size: 12px; color: var(--color-ink-light); margin-right: auto; }
.rt-btn { padding: 4px 10px; font-size: 12px; border-radius: 6px; border: 1px solid var(--color-control-border); background: white; cursor: pointer; }
.rt-btn:hover:not(:disabled) { border-color: var(--color-leather-light); }
.rt-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.rt-btn.primary { background: var(--color-ink); color: white; border-color: var(--color-ink); }
.rt-btn.danger { color: var(--color-error); border-color: #fecaca; }
.rt-btn.danger:hover:not(:disabled) { background: var(--color-error); color: white; }
.rt-empty { font-size: 13px; color: var(--color-ink-light); text-align: center; padding: 32px; border: 1px dashed var(--color-control-border); border-radius: 8px; }
.rt-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 10px; max-height: calc(100vh - 380px); min-height: 240px; overflow: auto; padding: 2px; }
@media (max-width: 768px) {
  .rt-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
