import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export type UIMode = 'beginner' | 'advanced'

export const useUIStore = defineStore('ui', () => {
  const mode = ref<UIMode>((localStorage.getItem('nw_ui_mode') as UIMode) || 'beginner')
  const onboardingDone = ref(localStorage.getItem('nw_onboarding_done') === '1')
  const commandPaletteOpen = ref(false)

  const isBeginner = computed(() => mode.value === 'beginner')

  function setMode(m: UIMode) {
    mode.value = m
    localStorage.setItem('nw_ui_mode', m)
  }

  function completeOnboarding() {
    onboardingDone.value = true
    localStorage.setItem('nw_onboarding_done', '1')
  }

  function resetOnboarding() {
    onboardingDone.value = false
    localStorage.removeItem('nw_onboarding_done')
  }

  return { mode, isBeginner, onboardingDone, commandPaletteOpen, setMode, completeOnboarding, resetOnboarding }
})
