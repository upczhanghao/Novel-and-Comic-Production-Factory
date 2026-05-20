<script setup lang="ts">
import { ref } from 'vue'
import { postSSETracked } from '@/api/client'
import { useFeedbackStore } from '@/stores/feedback'
import type { useWorkshopState } from '@/composables/useWorkshopState'

const props = defineProps<{ state: ReturnType<typeof useWorkshopState> }>()
const feedback = useFeedbackStore()

const guidance = ref('')
const running = ref(false)
const progress = ref('')
const backup = ref('')
const handle = ref<{ abort: () => void } | null>(null)

const quickPrompts = [
  '加强对白和动作描写',
  '减少形容词和环境描写',
  '提高节奏，删减拖沓',
  '增加心理活动',
  '修正情节漏洞',
]

function pick(p: string) { guidance.value = guidance.value ? `${guidance.value}；${p}` : p }

function revise() {
  const s = props.state
  if (!s.chapter.value.result || !guidance.value.trim()) return
  backup.value = s.chapter.value.result
  running.value = true
  progress.value = ''
  handle.value = postSSETracked('/generate/expand', {
    llm_config_name: s.llmConfig.value, filepath: s.filepath.value,
    chapter_num: s.chapterNum.value,
    style_name: s.chStyle.value === '不使用文风' ? null : s.chStyle.value || null,
    narrative_style_name: s.chNarrativeStyle.value === '不使用文风' ? null : s.chNarrativeStyle.value || null,
    xp_type: s.xpType.value,
    polish_guidance: guidance.value,
    polish_mode: 'modify',
    include_outline: true,
    include_character_state: false,
    include_summary: false,
    include_world_building: false,
  }, {
    taskId: `revise-chapter-${s.chapterNum.value}-${Date.now()}`,
    taskLabel: `快速修订第 ${s.chapterNum.value} 章`,
    onProgress: (msg, _v, content) => { progress.value = msg; if (content) s.chapter.value.result = content },
    onResult: (content) => {
      const marker = '<!--EXPAND_JSON-->'
      if (content.startsWith(marker)) {
        try {
          const data = JSON.parse(content.slice(marker.length))
          s.chapter.value.result = data.expanded || content
          feedback.success(`第 ${s.chapterNum.value} 章已按修订指令重写`, { undoFn: undo })
        } catch { s.chapter.value.result = content }
      } else {
        s.chapter.value.result = content
        feedback.success(`第 ${s.chapterNum.value} 章已修订`, { undoFn: undo })
      }
    },
    onDone: () => { running.value = false; handle.value = null },
  })
}

function undo() {
  if (backup.value) {
    props.state.chapter.value.result = backup.value
    backup.value = ''
  }
}

function cancel() {
  handle.value?.abort()
  running.value = false
}
</script>

<template>
  <div v-if="props.state.chapter.value.result && !props.state.chapter.value.running" class="qr-root">
    <div class="qr-header">
      <strong>快速修订</strong>
      <span class="qr-hint">不必回到上一步，直接给出修订指令</span>
    </div>
    <div class="qr-prompts">
      <button v-for="p in quickPrompts" :key="p" class="qr-chip" @click="pick(p)" type="button">+ {{ p }}</button>
    </div>
    <textarea
      v-model="guidance"
      rows="2"
      placeholder="例如：把第二段对白改得更紧张；删掉一个不重要的次要角色…"
      class="qr-input"
    />
    <div class="qr-actions">
      <button class="btn-primary" :disabled="running || !guidance.trim()" @click="revise" type="button">
        {{ running ? '修订中…' : '应用修订' }}
      </button>
      <button v-if="running" class="qr-cancel" @click="cancel" type="button">取消</button>
      <button v-if="backup && !running" class="qr-cancel" @click="undo" type="button">撤销</button>
      <span v-if="running" class="qr-progress">{{ progress || '处理中…' }}</span>
    </div>
  </div>
</template>

<style scoped>
.qr-root { margin-top: 12px; padding: 12px 14px; border-radius: 10px; background: var(--color-surface-muted); border: 1px solid var(--color-control-border); }
.qr-header { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 8px; }
.qr-hint { font-size: 11px; color: var(--color-ink-light); }
.qr-prompts { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
.qr-chip { padding: 3px 10px; font-size: 11px; border-radius: 999px; border: 1px solid var(--color-control-border); background: white; color: var(--color-leather-light); cursor: pointer; }
.qr-chip:hover { background: var(--color-leather-light); color: white; }
.qr-input { width: 100%; padding: 8px 10px; resize: vertical; }
.qr-actions { display: flex; align-items: center; gap: 8px; margin-top: 6px; }
.btn-primary { padding: 6px 14px; border-radius: 6px; background: var(--color-ink); color: white; border: 0; font-size: 13px; }
.btn-primary:disabled { opacity: 0.5; }
.qr-cancel { padding: 6px 12px; border-radius: 6px; border: 1px solid var(--color-control-border); background: white; font-size: 13px; }
.qr-progress { font-size: 11px; color: var(--color-ink-light); }
</style>
