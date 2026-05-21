<script setup lang="ts">
import { computed } from 'vue'
import { useAsyncAction } from '@/composables/useAsyncAction'

const props = withDefaults(defineProps<{
  /** 点击时执行的（可能异步）函数。返回 Promise 时按钮自动进入 busy 状态。 */
  action?: () => unknown | Promise<unknown>
  /** 显式忙碌覆盖；用于父组件已自己管理 loading 时直接传入 */
  busy?: boolean
  disabled?: boolean
  type?: 'button' | 'submit' | 'reset'
  /** Tailwind/原子类风格的样式继承；不传则保留外层传入的 class */
  variant?: '' | 'primary' | 'ghost' | 'danger'
  /** 不让 button 占满，给一个语义化 size hook */
  size?: '' | 'sm' | 'md' | 'lg'
}>(), {
  busy: false,
  disabled: false,
  type: 'button',
  variant: '',
  size: '',
})

const emit = defineEmits<{
  (e: 'click', ev: MouseEvent): void
  (e: 'error', err: unknown): void
  (e: 'success', result: unknown): void
}>()

const action = useAsyncAction()

const isBusy = computed(() => props.busy || action.busy.value)
const flashAttr = computed(() => action.flash.value || undefined)

async function onClick(ev: MouseEvent) {
  emit('click', ev)
  if (!props.action) return
  if (isBusy.value || props.disabled) return
  try {
    const result = await action.run(props.action)
    emit('success', result)
  } catch (err) {
    emit('error', err)
  }
}

const classes = computed(() => {
  const list = ['nw-async-btn']
  if (props.variant) list.push(`v-${props.variant}`)
  if (props.size) list.push(`s-${props.size}`)
  return list.join(' ')
})
</script>

<template>
  <button
    :type="type"
    :class="classes"
    :disabled="disabled || isBusy"
    :data-busy="isBusy ? 'true' : undefined"
    :data-flash="flashAttr"
    :aria-busy="isBusy ? 'true' : undefined"
    @click="onClick"
  >
    <slot />
  </button>
</template>

<style scoped>
.nw-async-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 7px 14px;
  font-size: 13px;
  border-radius: 6px;
  border: 1px solid var(--color-control-border);
  background: white;
  color: var(--color-ink);
  cursor: pointer;
}
.nw-async-btn:hover:not(:disabled) { border-color: var(--color-leather-light); }
.nw-async-btn:disabled { opacity: 0.5; }
.nw-async-btn.v-primary { background: var(--color-leather); color: var(--color-parchment); border-color: var(--color-leather); font-weight: 600; }
.nw-async-btn.v-primary:hover:not(:disabled) { background: var(--color-leather-dark); border-color: var(--color-leather-dark); }
.nw-async-btn.v-ghost { background: transparent; }
.nw-async-btn.v-danger { color: var(--color-error); border-color: #fecaca; }
.nw-async-btn.v-danger:hover:not(:disabled) { background: var(--color-error); color: white; }
.nw-async-btn.s-sm { padding: 4px 10px; font-size: 12px; }
.nw-async-btn.s-lg { padding: 10px 18px; font-size: 14px; }
</style>
