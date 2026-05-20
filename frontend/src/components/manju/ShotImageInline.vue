<script setup lang="ts">
import { ref } from 'vue'

interface Shot {
  id: string
  chapter_num: number
  shot_no: number
  image_url?: string
  image_path?: string
  image_download_url?: string
  [k: string]: unknown
}

const props = defineProps<{
  shot: Shot
  imageConfigs: string[]
  imageConfig: string
  generating: boolean
}>()

const emit = defineEmits<{
  (e: 'generate', shot: Shot): void
  (e: 'update:imageConfig', v: string): void
  (e: 'preview', url: string): void
}>()

const localConfig = ref(props.imageConfig)
function onConfigChange(e: Event) {
  const v = (e.target as HTMLSelectElement).value
  localConfig.value = v
  emit('update:imageConfig', v)
}
</script>

<template>
  <div class="sg-root">
    <div class="sg-controls">
      <select :value="props.imageConfig" @change="onConfigChange" class="sg-select">
        <option v-for="c in props.imageConfigs" :key="c" :value="c">{{ c }}</option>
        <option v-if="!props.imageConfigs.length" value="" disabled>未配置图片模型</option>
      </select>
      <button
        class="sg-btn"
        :disabled="props.generating || !props.imageConfig"
        @click="emit('generate', props.shot)"
        type="button"
      >{{ props.generating ? '生成中…' : (props.shot.image_url ? '重新生图' : '生图') }}</button>
    </div>
    <div v-if="props.shot.image_url" class="sg-preview" @click="emit('preview', String(props.shot.image_url))">
      <img :src="String(props.shot.image_url)" alt="shot image" />
      <a v-if="props.shot.image_download_url" :href="String(props.shot.image_download_url)" download class="sg-dl" @click.stop>下载</a>
    </div>
    <div v-else class="sg-empty">尚未生成图片</div>
  </div>
</template>

<style scoped>
.sg-root { display: flex; flex-direction: column; gap: 6px; }
.sg-controls { display: flex; gap: 4px; }
.sg-select { flex: 1; min-width: 0; padding: 4px 6px; font-size: 11px; border: 1px solid var(--color-control-border); border-radius: 4px; }
.sg-btn { padding: 4px 10px; font-size: 11px; background: var(--color-ink); color: white; border: 0; border-radius: 4px; cursor: pointer; }
.sg-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.sg-preview { position: relative; border-radius: 6px; overflow: hidden; cursor: zoom-in; aspect-ratio: 9/16; background: var(--color-surface-muted); }
.sg-preview img { width: 100%; height: 100%; object-fit: cover; display: block; }
.sg-dl { position: absolute; right: 4px; bottom: 4px; background: rgba(0,0,0,0.6); color: white; font-size: 10px; padding: 2px 6px; border-radius: 4px; text-decoration: none; }
.sg-empty { padding: 24px 8px; text-align: center; font-size: 11px; color: var(--color-ink-light); background: var(--color-surface-muted); border-radius: 6px; }
</style>
