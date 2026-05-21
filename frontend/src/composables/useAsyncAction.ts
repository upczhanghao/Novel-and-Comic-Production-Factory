import { ref, type Ref } from 'vue'

export interface AsyncActionState {
  busy: Ref<boolean>
  flash: Ref<'' | 'ok' | 'err'>
  run: <T>(fn: () => Promise<T> | T) => Promise<T | undefined>
}

/**
 * 把同步 / 异步 click 处理器包成一个 busy + flash 反馈的 action：
 *   const save = useAsyncAction()
 *   <button :data-busy="save.busy.value" :data-flash="save.flash.value" @click="save.run(() => api.save(form))">
 * busy 在调用期间为 true（CSS 自动加 spinner + 锁住点击）；
 * flash 在结束后短暂显示 ok / err 脉冲（800ms，与 .css 动画时长一致）。
 */
export function useAsyncAction(opts: { flashMs?: number } = {}): AsyncActionState {
  const flashMs = opts.flashMs ?? 800
  const busy = ref(false)
  const flash = ref<'' | 'ok' | 'err'>('')
  let flashTimer: ReturnType<typeof setTimeout> | null = null

  function clearFlashTimer() {
    if (flashTimer) {
      clearTimeout(flashTimer)
      flashTimer = null
    }
  }

  async function run<T>(fn: () => Promise<T> | T): Promise<T | undefined> {
    if (busy.value) return
    clearFlashTimer()
    flash.value = ''
    busy.value = true
    try {
      const result = await fn()
      flash.value = 'ok'
      flashTimer = setTimeout(() => { flash.value = ''; flashTimer = null }, flashMs)
      return result
    } catch (e) {
      flash.value = 'err'
      flashTimer = setTimeout(() => { flash.value = ''; flashTimer = null }, flashMs)
      throw e
    } finally {
      busy.value = false
    }
  }

  return { busy, flash, run }
}
